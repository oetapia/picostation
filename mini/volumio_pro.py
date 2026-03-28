# APP: VOLUMIO PRO
"""
mini/volumio_pro.py — Volumio controller with Tidal similar-track queuing.

Buttons:
  UP   (GP21) → previous track   — green blink
  DOWN (GP22) → next track       — green blink
  CTRL (GP26) → play/pause       — green (playing) / red (paused)

IR remote:
  shuffle → fetch similar tracks from Tidal API and queue them
  repeat  → fetch album tracks from Tidal API and queue them

LEDs stay on to reflect playback state:
  green = playing
  red   = stopped / paused
"""

import time
import urequests
import ujson
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from mini.hw477_main import NECDecoder
import framebuf
import icons_16.icons as icons

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

BASE_URL     = "http://volumio.local/api/v1"
TIDAL_URL    = "http://volumio.local:4000/api/tidal"
POLL_INTERVAL = 5   # seconds between automatic status refreshes

IR_PIN       = 12
IR_PROFILE   = "ir_profiles/remote_tiny.json"


def _trunc(text, n):
    return text[:n] if len(text) <= n else text[:n - 1] + "~"


def _scroll(text, width, offset):
    """Return a window of `width` chars from `text`, scrolling by `offset`."""
    if len(text) <= width:
        return text
    padded = text + "   "
    loop = len(padded)
    start = offset % loop
    chunk = padded[start:start + width]
    if len(chunk) < width:
        chunk += padded[:width - len(chunk)]
    return chunk


def _extract_tidal_id(uri):
    """Pull the numeric track ID from a tidal://song/NNNN URI."""
    if not uri:
        return None
    parts = uri.split("/")
    return parts[-1] if parts[-1].isdigit() else None


class VolumioProMini:
    def __init__(self):
        self.oled     = OLEDScreen()._display   # raw SSD1306 driver
        self.controls = GameControls()
        self.leds     = LEDs()
        self.ir       = NECDecoder(pin_num=IR_PIN)

        self.title       = ""
        self.artist      = ""
        self.status      = "stop"
        self.volume      = 50
        self.uri         = ""          # current track URI (used to derive Tidal ID)
        self.last_poll   = 0
        self.connected   = False
        self.scroll_offset = 0

        # Load IR profile
        self.ir_addr, self.ir_cmds = self._load_ir_profile()

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

    def _load_ir_profile(self):
        try:
            with open(IR_PROFILE) as f:
                data = ujson.load(f)
            addr = int(data["address"], 16)
            cmds = {int(k, 16): v for k, v in data["commands"].items()}
            return addr, cmds
        except Exception as e:
            print("IR profile load error:", e)
            return None, {}

    # ------------------------------------------------------------------ utils

    def _msg(self, line1, line2=""):
        self.oled.fill(0)
        self.oled.text(_trunc(line1, 16), 0, 8)
        if line2:
            self.oled.text(_trunc(line2, 16), 0, 20)
        self.oled.show()

    def _update_leds(self):
        """Green when playing, red when paused/stopped."""
        pass

    def _flash(self, led_name):
        """Quick visual acknowledgement for track skip buttons."""
        led = getattr(self.leds, led_name)
        led.on()
        time.sleep(0.12)
        led.off()
        time.sleep(0.05)
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
            self.volume = d.get("volume", self.volume)
            self.uri    = d.get("uri", "")
            print("POLL: status={} vol={} title={}".format(
                self.status, self.volume, self.title))
        except Exception as e:
            print("POLL error:", e)
        self.last_poll = time.time()

    def _command(self, cmd, refresh=True):
        """Send a playback command; optionally refresh state afterwards."""
        url = BASE_URL + "/commands/?cmd=" + cmd
        print("CMD:", url)
        try:
            r = urequests.get(url)
            print("CMD response:", r.status_code)
            r.close()
        except Exception as e:
            print("CMD error:", e)
        if refresh:
            time.sleep(0.3)
            self._poll()
            self._update_leds()

    # ---------------------------------------------------------- tidal similar

    def _fetch_similar(self):
        """Fetch + cache similar tracks, then queue them via the proxy API."""
        track_id = _extract_tidal_id(self.uri)
        if not track_id:
            print("Similar: no Tidal ID in URI:", self.uri)
            self._msg("No Tidal ID")
            time.sleep(1.5)
            return

        self._msg("Finding similar", _trunc(self.title, 16))
        print("Similar: fetching for track_id=", track_id)

        # Step 1 — fetch & cache
        try:
            r = urequests.get(TIDAL_URL + "/similar-tracks?trackId=" + track_id)
            if r.status_code != 200:
                print("Similar: HTTP", r.status_code)
                self._msg("Tidal error", str(r.status_code))
                r.close()
                time.sleep(1.5)
                return
            r.close()
        except Exception as e:
            print("Similar fetch error:", e)
            self._msg("Tidal error")
            time.sleep(1.5)
            return

        # Step 2 — queue from cache
        self._msg("Queueing...", _trunc(self.title, 16))
        try:
            r = urequests.post(
                TIDAL_URL + "/queue-similar-tracks?trackId=" + track_id + "&service=tidal"
            )
            d = r.json()
            r.close()
            queued = d.get("queued", "?")
            errors = d.get("errors", 0)
            print("Similar: queued={} errors={}".format(queued, errors))
            self._msg("Queued similar", str(queued) + " tracks")
        except Exception as e:
            print("Queue error:", e)
            self._msg("Queue error")

        time.sleep(1.5)

    # ----------------------------------------------------------- tidal album

    def _fetch_album(self):
        """Fetch + cache album tracks, then queue them via the proxy API."""
        track_id = _extract_tidal_id(self.uri)
        if not track_id:
            print("Album: no Tidal ID in URI:", self.uri)
            self._msg("No Tidal ID")
            time.sleep(1.5)
            return

        self._msg("Fetching album", _trunc(self.title, 16))
        print("Album: fetching for track_id=", track_id)

        # Step 1 — fetch & cache
        try:
            r = urequests.get(TIDAL_URL + "/album-tracks?trackId=" + track_id)
            if r.status_code != 200:
                print("Album: HTTP", r.status_code)
                self._msg("Tidal error", str(r.status_code))
                r.close()
                time.sleep(1.5)
                return
            r.close()
        except Exception as e:
            print("Album fetch error:", e)
            self._msg("Tidal error")
            time.sleep(1.5)
            return

        # Step 2 — queue from cache
        self._msg("Queueing...", _trunc(self.title, 16))
        try:
            r = urequests.post(
                TIDAL_URL + "/queue-album-tracks?trackId=" + track_id + "&service=tidal"
            )
            d = r.json()
            r.close()
            queued = d.get("queued", "?")
            errors = d.get("errors", 0)
            print("Album: queued={} errors={}".format(queued, errors))
            self._msg("Queued album", str(queued) + " tracks")
        except Exception as e:
            print("Queue error:", e)
            self._msg("Queue error")

        time.sleep(1.5)

    # ------------------------------------------------------------------- ir

    def _handle_ir(self):
        """Dispatch an IR command to the Volumio API."""
        if not self.ir.poll():
            return
        self.ir.received = False

        print("IR: A={:02X} C={:02X} repeat={}".format(
            self.ir.address, self.ir.command, self.ir.repeat))

        if self.ir_addr is not None and self.ir.address != self.ir_addr:
            print("IR: address mismatch (expected {:02X})".format(self.ir_addr))
            return

        action = self.ir_cmds.get(self.ir.command)
        if action is None:
            print("IR: unmapped command {:02X}".format(self.ir.command))
            return

        print("IR: action =", action)

        if action == "play_pause":
            self._msg(action)
            self._command("toggle", refresh=False)
        elif action == "next":
            self._msg(action)
            self._flash("green")
            self._command("next", refresh=False)
        elif action == "prev":
            self._msg(action)
            self._flash("green")
            self._command("prev", refresh=False)
        elif action == "vol_up":
            self._command("volume&volume=plus", refresh=False)
        elif action == "vol_down":
            self._command("volume&volume=minus", refresh=False)
        elif action == "mute":
            self._command("volume&volume=mute", refresh=False)
        elif action == "shuffle":
            self._fetch_similar()
        elif action == "repeat":
            self._fetch_album()
        elif action == "power":
            self._msg("Shutting down...")
            self._command("shutdown", refresh=False)

        # Discard stale IR frames accumulated during the HTTP roundtrip
        dropped = len(self.ir._edges)
        self.ir._edges.clear()
        if dropped:
            print("IR: flushed {} stale edges".format(dropped))

    # ------------------------------------------------------------------ draw

    def draw(self):
        icon_data = icons.play if self.status == "play" else icons.pause
        size = 16
        bpr = 2
        buf = bytearray(bpr * size)
        for row in range(size):
            for col in range(size):
                if icon_data[row] & (1 << (size - 1 - col)):
                    buf[row * bpr + col // 8] |= (1 << (7 - (col % 8)))
        fb = framebuf.FrameBuffer(buf, size, size, framebuf.MONO_HLSB)

        self.oled.fill(0)
        self.oled.blit(fb, 0, 0)
        self.oled.text(_trunc(self.artist, 12), 18, 4)
        self.oled.text(_scroll(self.title, 16, self.scroll_offset), 0, 20)
        self.oled.show()

        self.scroll_offset += 1

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

            self._handle_ir()

            if time.time() - self.last_poll >= POLL_INTERVAL:
                self._poll()
                self._update_leds()

            self.draw()
            time.sleep(0.1)

        self.leds.all_off()


def run():
    VolumioProMini().run()
