# Building a Minimal Mini App — Volumio Example

This guide explains how to strip the full PicoStation down to a single-purpose device using the OLED mini pattern. The example builds a dedicated **Volumio music controller**: three buttons to control playback, one OLED to show the current track.

---

## The Mini Pattern

The full PicoStation has a menu, multiple apps, and two display modes. For a dedicated device you usually want:

- A single app that runs immediately on boot
- The smallest possible button set
- No menu overhead

The OLED mini apps in `mini/` already follow this pattern. Each one is a self-contained class with a `run()` loop. You can adapt any of them — or write a new one — and boot straight into it by calling it from `main.py`.

---

## Hardware for the Volumio Controller

You only need three components beyond the Pico itself:

| Part | Notes |
|------|-------|
| SSD1306 OLED (128×32) | Connected over I2C |
| 3× momentary push buttons | One per action |
| Breadboard + jumper wires | |

### Wiring

**OLED**

| OLED pin | Pico pin | GPIO |
|----------|----------|------|
| SDA      | Pin 24   | GP18 |
| SCL      | Pin 25   | GP19 |
| GND      | Pin 38   | —    |
| VCC      | Pin 36   | 3.3V |

**Buttons**

Wire each button between its GPIO pin and GND. The firmware enables the internal pull-up resistors, so no external resistor is needed.

| Button   | GPIO | Action          |
|----------|------|-----------------|
| PREV     | GP21 | Previous track  |
| NEXT     | GP22 | Next track      |
| PLAY     | GP26 | Toggle play/pause |

This reuses the same three GPIO pins defined in `breadboard/buttons.py` (`up`, `down`, `ctrl`) so no pin changes are required.

---

## How the Existing Code Maps to This

`breadboard/buttons.py` already exposes exactly three buttons via `GameControls`:

```python
self.up   = Pin(21, Pin.IN, Pin.PULL_UP)   # → PREV
self.down = Pin(22, Pin.IN, Pin.PULL_UP)   # → NEXT
self.ctrl = Pin(26, Pin.IN, Pin.PULL_UP)   # → PLAY/PAUSE
```

`was_pressed("up")`, `was_pressed("down")`, and `was_pressed("ctrl")` already include 100 ms debounce, so you do not need to add any.

---

## The App Code

Create `mini/volumio_mini.py`:

```python
"""
mini/volumio_mini.py — minimal Volumio controller for OLED + 3 buttons.

Buttons:
  UP   (GP21) → previous track
  DOWN (GP22) → next track
  CTRL (GP26) → play / pause toggle
"""

import time
import urequests
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

BASE_URL = "http://volumio.local/api/v1"
POLL_INTERVAL = 5   # seconds between automatic status refreshes


def _trunc(text, n):
    return text[:n] if len(text) <= n else text[:n - 1] + "~"


class VolumioMini:
    def __init__(self):
        self.oled     = OLEDScreen()._display   # raw SSD1306 driver
        self.controls = GameControls()

        self.title    = ""
        self.artist   = ""
        self.status   = "stop"
        self.last_poll = 0

        self._msg("Connecting...")
        if WIFI_AVAILABLE:
            ok = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if ok:
                self._poll()
            else:
                self._msg("No WiFi")
                time.sleep(3)

    # ------------------------------------------------------------------ utils

    def _msg(self, text):
        self.oled.fill(0)
        self.oled.text(_trunc(text, 16), 0, 12)
        self.oled.show()

    def _poll(self):
        """Fetch current playback state from Volumio."""
        try:
            r = urequests.get(BASE_URL + "/getState")
            d = r.json()
            r.close()
            self.title  = d.get("title",  "Unknown")
            self.artist = d.get("artist", "")
            self.status = d.get("status", "stop")
        except Exception as e:
            print("poll error:", e)
        self.last_poll = time.time()

    def _command(self, cmd):
        """Send a playback command and refresh state."""
        try:
            r = urequests.get(BASE_URL + f"/commands/?cmd={cmd}")
            r.close()
        except Exception as e:
            print("command error:", e)
        time.sleep(0.3)
        self._poll()

    # ------------------------------------------------------------------ draw

    def draw(self):
        self.oled.fill(0)

        # Row 0 — play/pause indicator + artist
        icon = ">" if self.status == "play" else "||"
        self.oled.text(_trunc(f"{icon} {self.artist}", 16), 0, 0)

        # Row 1 — (empty row for spacing at 8px font)

        # Row 2 — track title (scrolling would need a loop; trunc is fine here)
        self.oled.text(_trunc(self.title, 16), 0, 16)

        self.oled.show()

    # ------------------------------------------------------------------- run

    def run(self):
        while True:
            # Buttons
            if self.controls.was_pressed("up"):
                self._command("prev")

            elif self.controls.was_pressed("down"):
                self._command("next")

            elif self.controls.was_pressed("ctrl"):
                if self.status == "play":
                    self._command("pause")
                else:
                    self._command("play")

            # Periodic refresh
            if time.time() - self.last_poll >= POLL_INTERVAL:
                self._poll()

            self.draw()
            time.sleep(0.1)


def run():
    VolumioMini().run()
```

---

## Boot Directly Into the App

To skip the menu and launch the Volumio controller on startup, replace the contents of `main.py` with:

```python
from mini.volumio_mini import run
run()
```

Or, to keep the rest of the project intact and only change the OLED boot path, edit the `main()` function in the existing `main.py`:

```python
def main():
    if Screen.width == 128:   # OLED detected
        from mini.volumio_mini import run
        run()
        return
    # ... rest of main unchanged
```

---

## Volumio API Reference

The controller uses Volumio's REST API, which is available at `http://volumio.local/api/v1` when Volumio is running on the same network.

| Endpoint | Method | Action |
|----------|--------|--------|
| `/getState` | GET | Returns JSON with `title`, `artist`, `album`, `status`, `bitrate` |
| `/commands/?cmd=play` | GET | Start playback |
| `/commands/?cmd=pause` | GET | Pause playback |
| `/commands/?cmd=prev` | GET | Previous track |
| `/commands/?cmd=next` | GET | Next track |
| `/commands/?cmd=volume&volume=plus` | GET | Volume up |
| `/commands/?cmd=volume&volume=minus` | GET | Volume down |

---

## Adapting This Pattern to Other Apps

The same three-file structure works for any dedicated mini app:

```
mini/your_app.py      ← the app class + run() function
main.py               ← calls run() on boot
breadboard/buttons.py ← already wired to GP21 / GP22 / GP26
```

The key rules:

- Keep a single `run()` loop; never block with `while True` inside a helper.
- Use `was_pressed()` for edge-triggered input (fires once per press).
- Poll external services on a timer (`time.time() - last_poll >= interval`), not on every iteration.
- Keep OLED text to 16 characters per row (128 px ÷ 8 px/char) and 4 rows (32 px ÷ 8 px/row).
