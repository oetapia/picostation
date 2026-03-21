#!/usr/bin/env python3
"""
Deploy to Raspberry Pi Pico
============================

Syncs production files to the Pico using mpremote, skipping unchanged files
by comparing file sizes.

Requirements:
    pip install mpremote

Usage:
    python deploy_to_pico.py [--dry-run] [--force] [--verbose] [--version {mini,full,auto}]

Options:
    --dry-run              Show what would be copied without actually copying
    --force                Copy all files regardless of changes
    --verbose              Show detailed output
    --version {mini,full,auto}
                           Which main to deploy (prompts if omitted)
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

    VERSION_MAIN = {
        'mini': 'main_mini.py',
        'full': 'main_full.py',
        'auto': 'main.py',
    }

    def __init__(self, dry_run=False, force=False, verbose=False, version='auto', clean=False):
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.version = version
        self.clean = clean
        # Maps local filename → remote filename for files that need renaming
        self.rename_map = {}
        if version in ('mini', 'full'):
            self.rename_map[self.VERSION_MAIN[version]] = 'main.py'
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
        include_files = list(self.INCLUDE_FILES)
        if self.version in ('mini', 'full'):
            include_files = [f for f in include_files if f != 'main.py']
            include_files.insert(0, self.VERSION_MAIN[self.version])
        for name in include_files:
            p = Path(name)
            if p.exists() and not self.should_exclude(p):
                files.append(p)
        skip_dirs = set()
        if self.version == 'mini':
            skip_dirs.add('icons_rgb565')
        for dirname in self.INCLUDE_DIRS:
            if dirname in skip_dirs:
                continue
            d = Path(dirname)
            if d.is_dir():
                for p in sorted(d.rglob('*')):
                    if p.is_file() and not self.should_exclude(p):
                        files.append(p)
        return files

    def wipe_pico(self) -> bool:
        """Delete all files and directories on the Pico, leaving a clean filesystem."""
        print("🗑  Wiping Pico filesystem...")
        if self.dry_run:
            self.log("DRY RUN — skipping wipe", 'warning')
            return True
        # Run a recursive delete on the Pico via a short exec snippet.
        # Skips /lib so third-party libraries are preserved.
        wipe_script = (
            "import os\n"
            "SKIP = {'/lib'}\n"
            "def _rm(p):\n"
            "    if p in SKIP:\n"
            "        return\n"
            "    try:\n"
            "        entries = os.listdir(p)\n"
            "    except OSError:\n"
            "        os.remove(p)\n"
            "        return\n"
            "    for e in entries:\n"
            "        _rm((p.rstrip('/') + '/' + e))\n"
            "    if p != '/':\n"
            "        os.rmdir(p)\n"
            "_rm('/')\n"
            "print('wipe done')\n"
        )
        stdout, stderr, returncode = self.run_mpremote(['exec', wipe_script])
        if returncode != 0 or 'wipe done' not in stdout:
            self.log(f"Wipe failed: {stderr.strip() or stdout.strip()}", 'error')
            return False
        print("✅ Pico filesystem wiped\n")
        return True

    def ensure_remote_dir(self, remote_dir: str):
        """Create directory on Pico (ignores error if it already exists)."""
        self.run_mpremote(['mkdir', f':{remote_dir}'])

    def copy_file(self, local_file: Path) -> bool:
        remote_name = self.rename_map.get(str(local_file), str(local_file))
        remote = f':{remote_name}'
        if self.dry_run:
            label = f"{local_file} → {remote_name}" if remote_name != str(local_file) else str(local_file)
            print(f"  would copy → {label}")
            return True
        parent = Path(remote_name).parent
        if str(parent) != '.':
            self.ensure_remote_dir(str(parent))
        _, stderr, returncode = self.run_mpremote(['cp', str(local_file), remote])
        if returncode != 0:
            self.log(f"Failed to copy {local_file}: {stderr.strip()}", 'error')
            return False
        return True

    def deploy(self) -> bool:
        version_label = {'mini': 'Mini (OLED)', 'full': 'Full (TFT)', 'auto': 'Auto-detect'}.get(self.version, self.version)
        print("=" * 55)
        print(f"🚀 PicoStation Deploy  [{version_label}]")
        print("=" * 55)
        if self.dry_run:
            self.log("DRY RUN — no files will be copied\n", 'warning')

        if not self.check_connection():
            return False

        if self.clean and not self.wipe_pico():
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
            remote_name = self.rename_map.get(str(local_file), str(local_file))
            remote_size = remote_files.get(remote_name)
            local_size = local_file.stat().st_size
            needs_copy = self.force or remote_size is None or remote_size != local_size

            if needs_copy:
                tag = "new" if remote_size is None else f"{remote_size}→{local_size}B"
                label = f"{local_file} → {remote_name}" if remote_name != str(local_file) else str(local_file)
                print(f"📤 {label}  ({tag})")
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


def prompt_version() -> str:
    print("Which version do you want to deploy?")
    print("  1) Full  — TFT arcade (main_full.py → main.py)")
    print("  2) Mini  — OLED apps  (main_mini.py → main.py)")
    print("  3) Auto  — hardware auto-detect (main.py as-is)")
    while True:
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == '1':
            return 'full'
        elif choice == '2':
            return 'mini'
        elif choice == '3':
            return 'auto'
        print("Please enter 1, 2, or 3.")


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
    parser.add_argument('--version', choices=['mini', 'full', 'auto'],
                        help='Which main to deploy (prompts if omitted)')
    parser.add_argument('--clean', action='store_true',
                        help='Wipe the Pico filesystem before deploying')
    args = parser.parse_args()

    version = args.version if args.version else prompt_version()

    deployer = PicoDeployer(dry_run=args.dry_run, force=args.force, verbose=args.verbose,
                            version=version, clean=args.clean)
    sys.exit(0 if deployer.deploy() else 1)


if __name__ == '__main__':
    main()
