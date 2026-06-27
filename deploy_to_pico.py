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
                             [--version {tft,mini}] [--remote REMOTE ...]
                             [--app NAME ...] [--dir NAME ...]
                             [--clean | --no-clean]

Options:
    --dry-run              Show what would be copied without actually copying
    --force                Copy all files regardless of changes
    --verbose              Show detailed output
    --version {tft,mini}   Which main to deploy (prompts if omitted)
                           tft  → deploys main.py as-is (TFT, full apps)
                           mini → deploys main_mini.py renamed to main.py
    --remote REMOTE        IR profile(s) to deploy, e.g. --remote tiny xbox
                           Matches by substring against filenames in ir_profiles/.
                           Implies --dir ir_profiles. Omit to deploy all profiles
                           (only when ir_profiles/ is otherwise included).
    --app NAME             Include only these files from apps/ and mini/
                           (substring match, e.g. --app snake space).
                           If omitted, you'll be prompted. Pass '--app' alone
                           to include no apps.
    --dir NAME             Include only these optional top-level directories
                           (e.g. --dir icons_rgb565 breadboard ir_profiles).
                           Same prompt/empty rules as --app.
    --clean / --no-clean   Wipe the Pico filesystem before deploying, or
                           explicitly skip wiping. If neither is passed,
                           you'll be prompted.

Version-incompatible directories are auto-excluded:
    tft   →  skips mini/
    mini  →  skips icons_rgb565/
"""

import subprocess
import sys
import argparse
from pathlib import Path


class PicoDeployer:
    """Deploy files to Raspberry Pi Pico using mpremote."""

    # Individual root-level files to deploy
    # config.py is gitignored (holds WiFi creds) but is deployed from the
    # local working copy if present.
    INCLUDE_FILES = [
        'main.py',
        'screen.py',
        'wifi.py',
        'vl53l0x_mp.py',
        'config.py',
    ]

    # Directories to deploy recursively
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

    # tft uses main.py as-is (no rename); mini renames main_mini.py → main.py.
    VERSION_MAIN = {
        'mini': 'main_mini.py',
        'tft': 'main.py',
    }

    # Top-level dirs the user can opt out of via the interactive prompt.
    OPTIONAL_DIRS = ['icons_16', 'icons_rgb565', 'breadboard', 'ir_profiles']

    # Dirs that are incompatible with a given hardware version and should be
    # auto-excluded regardless of user selection.
    INCOMPATIBLE_DIRS = {
        'tft': {'mini'},
        'mini': {'icons_rgb565'},
    }

    def __init__(self, dry_run=False, force=False, verbose=False, version='tft',
                 clean=False, remotes=None, excluded_files=None, excluded_dirs=None):
        self.dry_run = dry_run
        self.force = force
        self.verbose = verbose
        self.version = version
        self.clean = clean
        self.remotes = remotes  # list of profile substrings, or None for all
        # Relative paths like "apps/weather.py" the user opted to skip.
        self.excluded_files = set(excluded_files or [])
        # Top-level dir names like "icons_rgb565" the user opted to skip.
        # Auto-excluded incompatible dirs are merged in here so all skip logic
        # has a single source of truth.
        self.excluded_dirs = set(excluded_dirs or []) | self.INCOMPATIBLE_DIRS.get(version, set())
        # Maps local filename → remote filename for files that need renaming
        self.rename_map = {}
        if version == 'mini':
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
        if self.version == 'mini':
            include_files = [f for f in include_files if f != 'main.py']
            include_files.insert(0, self.VERSION_MAIN[self.version])
        main_src = self.VERSION_MAIN[self.version]
        if not Path(main_src).exists():
            # Fail loudly instead of silently producing a deploy with no main.
            raise FileNotFoundError(
                f"Required main source '{main_src}' for --version {self.version} "
                f"is missing from the repo."
            )
        for name in include_files:
            p = Path(name)
            if p.exists() and not self.should_exclude(p):
                files.append(p)
        for dirname in self.INCLUDE_DIRS:
            if dirname in self.excluded_dirs:
                continue
            d = Path(dirname)
            if d.is_dir():
                for p in sorted(d.rglob('*')):
                    if not p.is_file() or self.should_exclude(p):
                        continue
                    if dirname == 'ir_profiles' and self.remotes is not None:
                        if not any(r in p.name for r in self.remotes):
                            continue
                    if str(p) in self.excluded_files:
                        continue
                    files.append(p)
        return files

    def wipe_pico(self) -> bool:
        """Delete all files and directories on the Pico, leaving a clean filesystem."""
        print("🗑  Wiping Pico filesystem...")
        if self.dry_run:
            self.log("DRY RUN — skipping wipe", 'warning')
            return True
        # Run a recursive delete on the Pico via a short exec snippet.
        # Skips /lib (third-party libraries) and /config.py (credentials).
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

    def prune_remote_excluded(self, remote_files: dict):
        """Remove excluded files/dirs from the Pico (used when not wiping)."""
        for path in sorted(self.excluded_files):
            if path in remote_files:
                print(f"🗑  removing {path}  (excluded)")
                if not self.dry_run:
                    _, stderr, returncode = self.run_mpremote(['rm', f':{path}'])
                    if returncode != 0:
                        self.log(f"Failed to remove {path}: {stderr.strip()}", 'error')
        for dirname in sorted(self.excluded_dirs):
            for path in sorted(remote_files):
                if path == dirname or path.startswith(dirname + '/'):
                    print(f"🗑  removing {path}  (in excluded dir {dirname})")
                    if not self.dry_run:
                        _, stderr, returncode = self.run_mpremote(['rm', f':{path}'])
                        if returncode != 0:
                            self.log(f"Failed to remove {path}: {stderr.strip()}", 'error')

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
        version_label = {'mini': 'Mini (OLED)', 'tft': 'TFT (Full)'}.get(self.version, self.version)
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

        if not self.clean and (self.excluded_files or self.excluded_dirs):
            self.prune_remote_excluded(remote_files)

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
        else:
            print("✅ Pico is already up to date.")
        return True


def prompt_version() -> str:
    print("Which version do you want to deploy?")
    print("  1) TFT   — TFT arcade, full apps  (main.py as-is)")
    print("  2) Mini  — OLED apps              (main_mini.py → main.py)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == '1':
            return 'tft'
        elif choice == '2':
            return 'mini'
        print("Please enter 1 or 2.")


def prompt_include(label: str, items: list) -> set:
    """Multi-select prompt that returns the set of items to INCLUDE.

    Enter = include none. 'all' = include everything. Numbers select items.
    """
    if not items:
        return set()
    print(f"\n{label}")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item}")
    raw = input("Enter numbers to INCLUDE (e.g. '2 5'), 'all' for all, "
                "or press Enter for none: ").strip().lower()
    if not raw:
        return set()
    if raw == 'all':
        return set(items)
    included = set()
    for tok in raw.replace(',', ' ').split():
        try:
            idx = int(tok)
        except ValueError:
            continue
        if 1 <= idx <= len(items):
            included.add(items[idx - 1])
    return included


def prompt_yes_no(question: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    raw = input(question + suffix).strip().lower()
    if not raw:
        return default
    return raw in ('y', 'yes')


def list_app_files(dirname: str) -> list:
    """Return sorted .py filenames in dirname/ excluding __init__.py."""
    d = Path(dirname)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.glob('*.py') if p.name != '__init__.py')


def resolve_app_includes(include_substrings: list, dirnames: list) -> set:
    """Expand --app substrings into the set of file paths to INCLUDE."""
    if not include_substrings:
        return set()
    included = set()
    for dirname in dirnames:
        for name in list_app_files(dirname):
            if any(s in name for s in include_substrings):
                included.add(f"{dirname}/{name}")
    return included


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
    parser.add_argument('--version', choices=['tft', 'mini'],
                        help='Which main to deploy (prompts if omitted)')
    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument('--clean', dest='clean', action='store_true', default=None,
                             help='Wipe the Pico filesystem before deploying')
    clean_group.add_argument('--no-clean', dest='clean', action='store_false',
                             help='Skip the wipe (incremental deploy)')
    parser.add_argument('--remote', nargs='+', metavar='REMOTE',
                        help='IR profile(s) to deploy, matched by substring '
                             '(e.g. --remote tiny xbox). Omit to deploy all.')
    parser.add_argument('--app', nargs='*', metavar='NAME', default=None,
                        help='Include only these files from apps/ and mini/ by '
                             "substring (e.g. --app snake space). Use '--app' "
                             'alone to include no apps. Omit to be prompted.')
    parser.add_argument('--dir', nargs='*', metavar='NAME', default=None,
                        help='Include only these optional top-level directories '
                             '(e.g. --dir icons_rgb565). Same rules as --app.')
    args = parser.parse_args()

    version = args.version if args.version else prompt_version()
    incompatible = PicoDeployer.INCOMPATIBLE_DIRS.get(version, set())

    # Apps prompt covers apps/ + mini/, minus any version-incompatible ones.
    app_dirs = [d for d in ['apps', 'mini']
                if d not in incompatible and Path(d).is_dir()]
    optional_dirs = [d for d in PicoDeployer.OPTIONAL_DIRS
                     if d not in incompatible and Path(d).is_dir()]

    # Resolve app file selection.
    if args.app is None:
        included_app_files = set()
        for dirname in app_dirs:
            items = list_app_files(dirname)
            picked = prompt_include(
                f"Files in {dirname}/ — pick which to INCLUDE:", items)
            included_app_files.update(f"{dirname}/{name}" for name in picked)
    else:
        included_app_files = resolve_app_includes(args.app, app_dirs)

    # Resolve optional-dir selection.
    if args.dir is None:
        included_optional_dirs = prompt_include(
            "Optional top-level directories — pick which to INCLUDE:", optional_dirs)
    else:
        included_optional_dirs = {d for d in optional_dirs
                                  if any(s in d for s in args.dir)}

    # --remote implies ir_profiles is wanted; force-include so the flag
    # doesn't silently no-op when ir_profiles is otherwise opted out.
    if args.remote and 'ir_profiles' in optional_dirs:
        included_optional_dirs.add('ir_profiles')

    # Convert includes → excludes for the deployer. Anything in app_dirs not
    # selected is excluded; same for optional_dirs. Incompatible dirs are
    # added by PicoDeployer itself.
    excluded_files = set()
    for dirname in app_dirs:
        for name in list_app_files(dirname):
            path = f"{dirname}/{name}"
            if path not in included_app_files:
                excluded_files.add(path)
    excluded_dirs = set(optional_dirs) - included_optional_dirs

    if args.clean is None:
        clean = prompt_yes_no("\nWipe the Pico filesystem before deploying?", default=True)
    else:
        clean = args.clean

    deployer = PicoDeployer(dry_run=args.dry_run, force=args.force, verbose=args.verbose,
                            version=version, clean=clean, remotes=args.remote,
                            excluded_files=excluded_files, excluded_dirs=excluded_dirs)
    sys.exit(0 if deployer.deploy() else 1)


if __name__ == '__main__':
    main()
