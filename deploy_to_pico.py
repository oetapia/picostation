#!/usr/bin/env python3
"""
Deploy to Raspberry Pi Pico
============================

Syncs production files to the Pico using mpremote, skipping unchanged files
by comparing file sizes.

Supports mode selection:
    - full:  TFT arcade (main_full.py → main.py)
    - mini:  OLED apps  (main_mini.py → main.py)
    - auto:  hardware auto-detect (main.py as-is)
    - raw:   Raw WebSocket server (main_raw.py → main.py)

Requirements:
    pip install mpremote

Usage:
    python deploy_to_pico.py [--dry-run] [--force] [--verbose] [--mode {mini,full,auto,raw}] [--remote REMOTE ...]

Options:
    --dry-run              Show what would be copied without actually copying
    --force                Copy all files regardless of changes
    --verbose              Show detailed output
    --mode {mini,full,auto,raw}
                           Which main to deploy (prompts if omitted)
    --remote REMOTE        IR profile(s) to deploy, e.g. --remote tiny xbox
                           Matches by substring against filenames in ir_profiles/.
                           Omit to deploy all profiles.
    --clean                Wipe the Pico filesystem before deploying
"""

import subprocess
import sys
import json
import argparse
from pathlib import Path


class PicoDeployer:
    """Deploy files to Raspberry Pi Pico using mpremote."""

    # Load configuration from pico_files.json (shared with sync_branches.py)
    _config_path = Path(__file__).parent / 'pico_files.json'
    if _config_path.exists():
        with open(_config_path) as _f:
            _PICO_FILES = json.load(_f)
        INCLUDE_FILES = _PICO_FILES['include_files']
        INCLUDE_DIRS = _PICO_FILES['include_dirs']
    else:
        INCLUDE_FILES = [
            'main.py',
            'screen.py',
            'wifi.py',
            'vl53l0x_mp.py',
        ]
        INCLUDE_DIRS = [
            'apps',
            'mini',
            'ir_profiles',
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

    # Mode configuration — maps mode name to deploy behavior
    MODE_CONFIG = {
        'full': {
            'main_file': 'main_full.py',
            'description': 'TFT Arcade — full-screen apps with gamepad',
            'skip_files': ['main_mini.py', 'main_raw.py'],
            'skip_dirs': [],
        },
        'mini': {
            'main_file': 'main_mini.py',
            'description': 'OLED Mini — compact apps with breadboard controls',
            'skip_files': ['main_full.py', 'main_raw.py'],
            'skip_dirs': ['icons_rgb565'],
        },
        'auto': {
            'main_file': 'main.py',
            'description': 'Auto-detect — picks TFT or OLED at boot',
            'skip_files': ['main_mini.py', 'main_full.py', 'main_raw.py'],
            'skip_dirs': [],
        },
        'raw': {
            'main_file': 'main_raw.py',
            'description': 'Raw WebSocket — lowest latency, web-connected apps',
            'skip_files': ['main_mini.py', 'main_full.py'],
            'skip_dirs': ['apps', 'mini', 'ir_profiles', 'icons_rgb565', 'tft_screen'],
        },
    }

    def __init__(self, dry_run=False, force=False, verbose=False, mode=None, clean=False, remotes=None):
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.mode = mode
        self.clean = clean
        self.remotes = remotes
        self.rename_map = {}
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

    def select_mode(self):
        """Interactive mode selection if not specified via CLI."""
        if self.mode:
            return self.mode

        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║   Select Deploy Mode for PicoStation             ║")
        print("╠══════════════════════════════════════════════════╣")
        print("║                                                  ║")
        print("║  1. Full (TFT Arcade)                            ║")
        print("║     Full-screen apps with gamepad controls       ║")
        print("║     Best for: games, weather, volumio            ║")
        print("║                                                  ║")
        print("║  2. Mini (OLED)                                  ║")
        print("║     Compact apps with breadboard buttons         ║")
        print("║     Best for: small display, IR remote           ║")
        print("║                                                  ║")
        print("║  3. Auto-detect                                  ║")
        print("║     Picks TFT or OLED at boot                    ║")
        print("║     Best for: flexible hardware setups           ║")
        print("║                                                  ║")
        print("║  4. Raw WebSocket                                ║")
        print("║     Lowest latency, web-connected                ║")
        print("║     Best for: phone/tablet control, dashboards   ║")
        print("║                                                  ║")
        print("╚══════════════════════════════════════════════════╝")
        print()

        while True:
            choice = input("Select mode [1=Full, 2=Mini, 3=Auto, 4=Raw] (default: 3): ").strip()
            if choice in ('', '3'):
                self.mode = 'auto'
                break
            elif choice == '1':
                self.mode = 'full'
                break
            elif choice == '2':
                self.mode = 'mini'
                break
            elif choice == '4':
                self.mode = 'raw'
                break
            else:
                print("  Invalid choice. Enter 1, 2, 3, or 4.")

        config = self.MODE_CONFIG[self.mode]
        print(f"\n  → Mode: {config['description']}")
        print(f"  → Main file on Pico: main.py ← {config['main_file']}")
        print()
        return self.mode

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
        """Collect all local files to deploy based on selected mode."""
        config = self.MODE_CONFIG[self.mode]
        files = []

        # Build rename map
        self.rename_map = {}
        main_file = config['main_file']
        if main_file != 'main.py':
            self.rename_map[main_file] = 'main.py'

        # Determine which individual files to include
        skip_files = set(config.get('skip_files', []))
        include_files = list(self.INCLUDE_FILES)

        # For non-auto modes, swap the main file
        if main_file != 'main.py':
            include_files = [f for f in include_files if f != 'main.py']
            include_files.insert(0, main_file)

        # Remove files that should be skipped for this mode
        include_files = [f for f in include_files if f not in skip_files]

        for name in include_files:
            p = Path(name)
            if p.exists() and not self.should_exclude(p):
                files.append(p)

        # Determine which directories to include
        skip_dirs = set(config.get('skip_dirs', []))
        for dirname in self.INCLUDE_DIRS:
            if dirname in skip_dirs:
                continue
            d = Path(dirname)
            if d.is_dir():
                for p in sorted(d.rglob('*')):
                    if not p.is_file() or self.should_exclude(p):
                        continue
                    if dirname == 'ir_profiles' and self.remotes is not None:
                        if not any(r in p.name for r in self.remotes):
                            continue
                    files.append(p)

        return files

    def wipe_pico(self) -> bool:
        """Delete all files and directories on the Pico, leaving a clean filesystem."""
        print("🗑  Wiping Pico filesystem...")
        if self.dry_run:
            self.log("DRY RUN — skipping wipe", 'warning')
            return True
        wipe_script = (
            "import os\n"
            "SKIP = {'/lib', '/config.py'}\n"
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

    def prune_remote_profiles(self, remote_files: dict):
        """Remove ir_profiles/ files from the Pico that don't match --remote selection."""
        for remote_path in list(remote_files):
            if not remote_path.startswith('ir_profiles/'):
                continue
            fname = remote_path.split('/')[-1]
            if any(r in fname for r in self.remotes):
                continue
            print(f"🗑  removing {remote_path}  (not in --remote selection)")
            if not self.dry_run:
                _, stderr, returncode = self.run_mpremote(['rm', f':{remote_path}'])
                if returncode != 0:
                    self.log(f"Failed to remove {remote_path}: {stderr.strip()}", 'error')

    def deploy(self) -> bool:
        # Select mode (interactive if not specified)
        self.select_mode()

        config = self.MODE_CONFIG[self.mode]
        mode_label = config['description']

        print("=" * 55)
        print(f"🚀 PicoStation Deploy  [{mode_label}]")
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

        if self.remotes is not None:
            self.prune_remote_profiles(remote_files)

        print(f"\n📊 {self.stats['copied']} copied, "
              f"{self.stats['skipped']} skipped, "
              f"{self.stats['errors']} errors  "
              f"(of {self.stats['total']} total)\n")

        if self.stats['errors']:
            self.log("Deployment finished with errors", 'warning')
            return False

        if self.stats['copied']:
            print("✅ Done! Reset the Pico to run main.py.")
            if self.mode == 'raw':
                print("   Raw WebSocket server will start on boot.")
                print("   Connect with: ws://<pico-ip>:5000")
            print()
        else:
            print("✅ Pico is already up to date.")
        return True


def prompt_mode() -> str:
    """Standalone prompt for when --mode is not given (used by main())."""
    # The interactive prompt is handled inside PicoDeployer.select_mode()
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Deploy PicoStation files to Raspberry Pi Pico via mpremote',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Deploy Modes:
  full    TFT Arcade (main_full.py → main.py)
          Best for: games, weather, volumio on TFT screen

  mini    OLED Mini (main_mini.py → main.py)
          Best for: compact display, IR remote, breadboard

  auto    Auto-detect (main.py as-is)
          Best for: flexible setups that detect display at boot

  raw     Raw WebSocket (main_raw.py → main.py)
          Best for: phone/tablet control, web dashboards, low latency

Examples:
  python deploy_to_pico.py                    # Interactive mode selection
  python deploy_to_pico.py --mode raw         # Deploy raw WS (lowest latency)
  python deploy_to_pico.py --mode full        # Deploy TFT arcade mode
  python deploy_to_pico.py --mode mini        # Deploy OLED mini mode
  python deploy_to_pico.py --mode raw --force # Force full redeploy in raw mode
  python deploy_to_pico.py --mode raw --clean # Wipe + fresh deploy
  python deploy_to_pico.py --dry-run          # Preview what would be deployed
        """
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be copied without copying')
    parser.add_argument('--force', action='store_true',
                        help='Copy all files regardless of changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show skipped files too')
    parser.add_argument('--mode', choices=['mini', 'full', 'auto', 'raw'],
                        help='Deploy mode (prompts interactively if omitted)')
    parser.add_argument('--clean', action='store_true',
                        help='Wipe the Pico filesystem before deploying')
    parser.add_argument('--remote', nargs='+', metavar='REMOTE',
                        help='IR profile(s) to deploy, matched by substring '
                             '(e.g. --remote tiny xbox). Omit to deploy all.')
    args = parser.parse_args()

    deployer = PicoDeployer(dry_run=args.dry_run, force=args.force, verbose=args.verbose,
                            mode=args.mode, clean=args.clean, remotes=args.remote)
    sys.exit(0 if deployer.deploy() else 1)


if __name__ == '__main__':
    main()
