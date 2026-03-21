#!/usr/bin/env python3
"""
Deploy to Raspberry Pi Pico
============================

Syncs production files to the Pico using mpremote, skipping unchanged files
by comparing file sizes.

Requirements:
    pip install mpremote

Usage:
    python deploy_to_pico.py [--dry-run] [--force] [--verbose]

Options:
    --dry-run    Show what would be copied without actually copying
    --force      Copy all files regardless of changes
    --verbose    Show detailed output
"""

import subprocess
import sys
import argparse
from pathlib import Path


class PicoDeployer:
    """Deploy files to Raspberry Pi Pico using mpremote."""

    # Individual root-level files to deploy
    INCLUDE_FILES = [
        'main.py',
        'screen.py',
        'wifi.py',
        'vl53l0x_mp.py',
        # config.py is gitignored — create it manually on the Pico
    ]

    # Directories to deploy recursively
    INCLUDE_DIRS = [
        'apps',
        'mini',
        'breadboard',
        'oled_screen',
        'tft_screen',
        'icons_16',
        'icons_rgb565',
        'lib',
    ]

    # Patterns to skip inside included directories
    EXCLUDE_PATTERNS = [
        '__pycache__',
        '.pyc',
        '.DS_Store',
        '.git',
    ]

    def __init__(self, dry_run=False, force=False, verbose=False):
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.stats = {'copied': 0, 'skipped': 0, 'errors': 0, 'total': 0}

    def log(self, message, level='info'):
        prefix = {'info': '  ', 'success': '✅', 'skip': '⏭ ',
                  'error': '❌', 'warning': '⚠️ '}.get(level, '  ')
        print(f"{prefix} {message}")

    def run_mpremote(self, args: list) -> tuple:
        """Run an mpremote command. args is a list of arguments (no 'mpremote' prefix)."""
        try:
            result = subprocess.run(
                ['mpremote'] + args,
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout, result.stderr, result.returncode
        except FileNotFoundError:
            print("❌ mpremote not found. Install with: pip install mpremote")
            sys.exit(1)

    def check_connection(self) -> bool:
        """Verify the Pico is connected by listing root."""
        print("🔌 Checking Pico connection...")
        _, stderr, returncode = self.run_mpremote(['ls', ':'])
        if returncode != 0:
            print(f"❌ Could not connect to Pico. Is it plugged in?\n   {stderr.strip()}")
            return False
        print("✅ Pico connected\n")
        return True

    def list_pico_files(self, remote_path: str) -> dict:
        """Return {relative_path: size} for all files under remote_path on the Pico."""
        stdout, _, returncode = self.run_mpremote(['ls', f':{remote_path}'])
        files = {}
        if returncode != 0:
            return files
        for line in stdout.strip().splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0] != 'dir':
                try:
                    size = int(parts[0])
                    name = parts[1]
                    files[f"{remote_path}/{name}".lstrip('/')] = size
                except ValueError:
                    pass
        return files

    def should_exclude(self, filepath: Path) -> bool:
        return any(p in str(filepath) for p in self.EXCLUDE_PATTERNS)

    def get_local_files(self) -> list:
        """Collect all local files to deploy."""
        files = []
        for name in self.INCLUDE_FILES:
            p = Path(name)
            if p.exists() and not self.should_exclude(p):
                files.append(p)
        for dirname in self.INCLUDE_DIRS:
            d = Path(dirname)
            if d.is_dir():
                for p in sorted(d.rglob('*')):
                    if p.is_file() and not self.should_exclude(p):
                        files.append(p)
        return files

    def ensure_remote_dir(self, remote_dir: str):
        """Create directory on Pico (ignores error if it already exists)."""
        self.run_mpremote(['mkdir', f':{remote_dir}'])

    def copy_file(self, local_file: Path) -> bool:
        remote = f':{local_file}'
        if self.dry_run:
            print(f"  would copy → {local_file}")
            return True
        parent = local_file.parent
        if str(parent) != '.':
            self.ensure_remote_dir(str(parent))
        _, stderr, returncode = self.run_mpremote(['cp', str(local_file), remote])
        if returncode != 0:
            self.log(f"Failed to copy {local_file}: {stderr.strip()}", 'error')
            return False
        return True

    def deploy(self) -> bool:
        print("=" * 55)
        print("🚀 PicoStation Deploy")
        print("=" * 55)
        if self.dry_run:
            self.log("DRY RUN — no files will be copied\n", 'warning')

        if not self.check_connection():
            return False

        local_files = self.get_local_files()
        print(f"📋 {len(local_files)} local files found\n")

        # Build remote file index
        remote_files = {}
        for item in self.run_mpremote(['ls', ':'])[0].strip().splitlines():
            parts = item.strip().split(None, 1)
            if len(parts) == 2 and parts[0] != 'dir':
                try:
                    remote_files[parts[1]] = int(parts[0])
                except ValueError:
                    pass
        for dirname in self.INCLUDE_DIRS:
            remote_files.update(self.list_pico_files(dirname))

        print("-" * 55)
        for local_file in local_files:
            self.stats['total'] += 1
            remote_size = remote_files.get(str(local_file))
            local_size = local_file.stat().st_size
            needs_copy = self.force or remote_size is None or remote_size != local_size

            if needs_copy:
                tag = "new" if remote_size is None else f"{remote_size}→{local_size}B"
                print(f"📤 {local_file}  ({tag})")
                if self.copy_file(local_file):
                    self.stats['copied'] += 1
                else:
                    self.stats['errors'] += 1
            else:
                if self.verbose:
                    print(f"⏭  {local_file}  (unchanged)")
                self.stats['skipped'] += 1

        print("-" * 55)
        print(f"\n📊 {self.stats['copied']} copied, "
              f"{self.stats['skipped']} skipped, "
              f"{self.stats['errors']} errors  "
              f"(of {self.stats['total']} total)\n")

        if self.stats['errors']:
            self.log("Deployment finished with errors", 'warning')
            return False

        if self.stats['copied']:
            print("✅ Done! Reset the Pico to run main.py.")
        else:
            print("✅ Pico is already up to date.")
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Deploy PicoStation files to Raspberry Pi Pico via mpremote'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be copied without copying')
    parser.add_argument('--force', action='store_true',
                        help='Copy all files regardless of changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show skipped files too')
    args = parser.parse_args()

    deployer = PicoDeployer(dry_run=args.dry_run, force=args.force, verbose=args.verbose)
    sys.exit(0 if deployer.deploy() else 1)


if __name__ == '__main__':
    main()
