"""
mini/volumio_mini.py — minimal Volumio controller for OLED + 3 buttons.

Buttons:
  UP   (GP21) → previous track   — green blink
  DOWN (GP22) → next track       — green blink
  CTRL (GP26) → play/pause       — green (playing) / red (paused)

LEDs stay on to reflect playback state:
  green = playing
  red   = stopped / paused
"""

import time
import urequests
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs

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
        self.leds     = LEDs()

        self.title     = ""
        self.artist    = ""
        self.status    = "stop"
        self.last_poll = 0
        self.connected = False

        self.leds.all_off()
        self._msg("Connecting...")

        if WIFI_AVAILABLE:
            self.connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if self.connected:
                self._poll()
                self._update_leds()
            else:
                self._msg("No WiFi")
                time.sleep(2)

    # ------------------------------------------------------------------ utils

    def _msg(self, line1, line2=""):
        self.oled.fill(0)
        self.oled.text(_trunc(line1, 16), 0, 8)
        if line2:
            self.oled.text(_trunc(line2, 16), 0, 20)
        self.oled.show()

    def _update_leds(self):
        """Green when playing, red when paused/stopped."""
        if self.status == "play":
            self.leds.on("green")
            self.leds.off("red")
        else:
            self.leds.off("green")
            self.leds.on("red")

    def _flash(self, led_name):
        """Quick visual acknowledgement for track skip buttons."""
        led = getattr(self.leds, led_name)
        led.on()
        time.sleep(0.12)
        led.off()
        time.sleep(0.05)
        # Restore steady state
        self._update_leds()

    # ------------------------------------------------------------------ api

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
        """Send a playback command then refresh state."""
        try:
            r = urequests.get(BASE_URL + "/commands/?cmd=" + cmd)
            r.close()
        except Exception as e:
            print("command error:", e)
        time.sleep(0.3)
        self._poll()
        self._update_leds()

    # ------------------------------------------------------------------ draw

    def draw(self):
        icon = ">" if self.status == "play" else "||"

        self.oled.fill(0)
        # Row 0 — status icon + artist
        self.oled.text(_trunc(icon + " " + self.artist, 16), 0, 0)
        # Row 2 — track title
        self.oled.text(_trunc(self.title, 16), 0, 16)
        self.oled.show()

    # ------------------------------------------------------------------- run

    def run(self):
        if not self.connected:
            self._msg("No WiFi", "Check config.py")
            time.sleep(3)
            self.leds.all_off()
            return

        self.draw()

        while True:
            if self.controls.was_pressed("up"):
                self._flash("green")
                self._command("prev")

            elif self.controls.was_pressed("down"):
                self._flash("green")
                self._command("next")

            elif self.controls.was_pressed("ctrl"):
                if self.status == "play":
                    self._command("pause")
                else:
                    self._command("play")

            # Periodic refresh
            if time.time() - self.last_poll >= POLL_INTERVAL:
                self._poll()
                self._update_leds()

            self.draw()
            time.sleep(0.1)

        self.leds.all_off()


def run():
    VolumioMini().run()
