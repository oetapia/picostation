# Branch Sync Tool Documentation

## Overview

The `sync_branches.py` script automates syncing commits from the `main` branch to the `production-pico` branch, intelligently handling conflicts by removing non-production files.

## Why This Tool?

When developing on `main`, you might add:
- Development utilities (`sync_branches.py`, `deploy_to_pico.py`)
- Documentation files (`*.md`)
- Diagnostic scripts (`distance_sensor/`, `multiplexer/`)
- Unused/legacy modules

The `production-pico` branch should only contain files needed to run on the Raspberry Pi Pico. This tool automatically:
- Cherry-picks commits from main
- Identifies production vs non-production files
- Auto-resolves conflicts by removing non-production files
- Maintains clean git history

## Usage

### Basic Sync (Interactive)

```bash
python sync_branches.py
```

### Dry Run

```bash
python sync_branches.py --dry-run
```

### Sync Specific Commit

```bash
python sync_branches.py --commit abc1234
```

### Auto-Resolve Mode

```bash
python sync_branches.py --auto-resolve
```

## File Classification

### Production Files (Synced)

| Path | Purpose |
|------|---------|
| `main.py` | Entry point |
| `screen.py` | Auto-detect display (OLED/TFT) |
| `wifi.py` | WiFi connection |
| `vl53l0x_mp.py` | ToF distance sensor driver |
| `apps/` | TFT apps (snake, space_invaders, weather, volumio3) |
| `mini/` | OLED mini apps (weather, sensor, accel, led_test, sound, volumio, tof) |
| `breadboard/` | Hardware controls (buttons, leds, buzzer) |
| `oled_screen/` | SSD1306 OLED display driver |
| `tft_screen/` | ST7789 TFT display driver |
| `icons_16/` | 16x16 monochrome icons (OLED) |
| `icons_rgb565/` | RGB565 weather icons (TFT) |
| `lib/` | MicroPython libraries (ssd1306) |
| `.gitignore` | Git ignore rules |

> **Note:** `config.py` is gitignored — it contains WiFi credentials and must be managed manually on each device.

### Non-Production Files (Ignored)

| Path | Reason |
|------|--------|
| `controls.py` | Unused root-level duplicate |
| `distance_sensor/` | Diagnostic/dev scripts |
| `multiplexer/` | Diagnostic/dev scripts |
| `old/` | Archived legacy code |
| `venv/` | PC Python environment |
| `tft_screen/buttonTest.py` | Hardware test script |
| `oled_screen/display.py` | Unused alternative driver |
| `oled_screen/minimal.py` | Unused minimal driver |
| `sync_branches.py` | PC-side dev utility |
| `deploy_to_pico.py` | PC-side deploy utility |
| `*.md` | Documentation |

## Workflow

```bash
# 1. Develop on main
git checkout main
# ... make changes ...
git commit -m "Your change"

# 2. Preview what will sync
python sync_branches.py --dry-run

# 3. Sync to production-pico
python sync_branches.py

# 4. Deploy to the Pico
python deploy_to_pico.py

# 5. Push both branches
git push origin main
git push origin production-pico
```

## Conflict Resolution

### Automatic
Conflicts are auto-resolved when a non-production file was deleted on `production-pico` but modified on `main`. The script keeps it deleted.

### Manual
If a production file has a conflict you will see:

```
→ Conflict needs manual resolution: main.py
✗ Manual conflicts detected. Use --auto-resolve to force, or resolve manually.
```

Resolve manually, then re-run the sync.

## Troubleshooting

### "You have uncommitted changes"
```bash
git stash
python sync_branches.py
git stash pop
```

### "Failed to switch to production-pico"
```bash
git fetch origin production-pico
git checkout -b production-pico origin/production-pico
```

### "Cherry-pick failed"
```bash
git cherry-pick --abort
git diff  # inspect the conflict
```

## Git Aliases

Add to `~/.gitconfig`:

```ini
[alias]
    sync-prod = !python sync_branches.py
    sync-dry  = !python sync_branches.py --dry-run
```
