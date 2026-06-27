# APP: PICAR REMOTE
"""
mini/picar_remote.py — PiCar remote control over WebSocket.

Connects to picar's raw WS server and sends commands using the same
protocol picar expects ({"c":"m","v":50}, {"c":"s","v":90}, etc.)

Buttons:
  UP   (GP21) → accelerate (increase speed)
  DOWN (GP22) → decelerate / reverse
  CTRL (GP26) → brake (emergency stop)

IR Remote (if configured):
  Maps to: speed up, speed down, left, right, brake, gear, lights

OLED shows: connection status, current speed, servo angle.
"""

import time
import json
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from lib.ws_client import WebSocketClient

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

try:
    from mini.hw477_main import NECDecoder
    import ujson
    IR_AVAILABLE = True
except ImportError:
    IR_AVAILABLE = False

IR_PIN = 12
IR_PROFILE = "ir_profiles/remote_tiny.json"

SPEED_STEP = 15
SERVO_STEP = 15
SERVO_CENTER = 90
SERVO_MIN = 45
SERVO_MAX = 135
RECONNECT_INTERVAL = 5


def _trunc(text, n):
    return text[:n] if len(text) <= n else text[:n - 1] + "~"


class PicarRemote:
    def __init__(self):
        self.oled = OLEDScreen()._display
        self.controls = GameControls()
        self.leds = LEDs()

        self.ws = None
        self.connected = False
        self.speed = 0
        self.servo = SERVO_CENTER
        self.gear = False
        self.lights = "off"
        self.last_reconnect = 0

        # IR
        self.ir = None
        self.ir_addr = None
        self.ir_cmds = {}
        if IR_AVAILABLE:
            try:
                self.ir = NECDecoder(pin_num=IR_PIN)
                self.ir_addr, self.ir_cmds = self._load_ir_profile()
            except Exception:
                self.ir = None

        self.leds.all_off()
        self._msg("PiCar Remote")
        time.sleep(1)

        # Connect WiFi
        if WIFI_AVAILABLE:
            self._msg("Connecting WiFi")
            wlan = wifi.connect_wifi()
            if wlan:
                self._connect_ws()
            else:
                self._msg("No WiFi")
                time.sleep(2)
        else:
            self._msg("No WiFi module")
            time.sleep(2)

    def _load_ir_profile(self):
        try:
            with open(IR_PROFILE) as f:
                data = ujson.load(f)
            addr = int(data["address"], 16)
            cmds = {int(k, 16): v for k, v in data["commands"].items()}
            return addr, cmds
        except Exception:
            return None, {}

    def _msg(self, line1, line2=""):
        self.oled.fill(0)
        self.oled.text(_trunc(line1, 16), 0, 8)
        if line2:
            self.oled.text(_trunc(line2, 16), 0, 20)
        self.oled.show()

    def _connect_ws(self):
        """Connect to picar's raw WebSocket server."""
        picar_ip = getattr(config, 'PICAR_IP', None)
        picar_port = getattr(config, 'PICAR_PORT', 5000)

        if not picar_ip:
            self._msg("No PICAR_IP", "in config.py")
            time.sleep(2)
            return

        self._msg("Connecting...", picar_ip)
        try:
            self.ws = WebSocketClient(picar_ip, picar_port, timeout=3)
            self.ws.connect()
            self.connected = True
            self.leds.on("green")
            self._msg("Connected!", picar_ip)
            time.sleep(0.5)
            self._request_status()
        except Exception as e:
            self.connected = False
            self.ws = None
            self.leds.on("red")
            self._msg("Failed", str(e)[:16])
            time.sleep(1)

    def _send(self, cmd_dict):
        """Send command to picar, handle disconnects."""
        if not self.connected or not self.ws:
            return None
        try:
            self.ws.send(json.dumps(cmd_dict))
            resp = self.ws.recv(timeout=1)
            if resp is None:
                self._disconnect()
                return None
            return json.loads(resp)
        except Exception:
            self._disconnect()
            return None

    def _disconnect(self):
        self.connected = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.speed = 0
        self.leds.off("green")
        self.leds.on("red")

    def _request_status(self):
        """Fetch picar's current state."""
        resp = self._send({"c": "st"})
        if resp and resp.get("ok"):
            st = resp.get("st", {})
            self.speed = st.get("m", 0)
            self.servo = st.get("s", SERVO_CENTER)
            self.gear = bool(st.get("g", 0))
            self.lights = st.get("l", "off")

    def _set_speed(self, speed):
        speed = max(-100, min(100, speed))
        resp = self._send({"c": "m", "v": speed})
        if resp and resp.get("ok"):
            self.speed = resp.get("m", speed)

    def _brake(self):
        resp = self._send({"c": "b"})
        if resp and resp.get("ok"):
            self.speed = 0

    def _set_servo(self, angle):
        angle = max(SERVO_MIN, min(SERVO_MAX, angle))
        resp = self._send({"c": "s", "v": angle})
        if resp and resp.get("ok"):
            self.servo = resp.get("s", angle)

    def _toggle_gear(self):
        resp = self._send({"c": "g", "v": "toggle"})
        if resp and resp.get("ok"):
            self.gear = bool(resp.get("g", 0))

    def _cycle_lights(self):
        cycle = {"off": "front", "front": "back", "back": "both", "both": "off"}
        next_state = cycle.get(self.lights, "front")
        resp = self._send({"c": "l", "v": next_state})
        if resp and resp.get("ok"):
            self.lights = resp.get("l", next_state)

    # ------------------------------------------------------------------ IR

    def _handle_ir(self):
        if not self.ir or not self.ir.poll():
            return
        self.ir.received = False

        if self.ir_addr is not None and self.ir.address != self.ir_addr:
            return

        action = self.ir_cmds.get(self.ir.command)
        if action is None:
            return

        if action == "vol_up":
            self._set_speed(self.speed + SPEED_STEP)
        elif action == "vol_down":
            self._set_speed(self.speed - SPEED_STEP)
        elif action == "prev":
            self._set_servo(self.servo - SERVO_STEP)
        elif action == "next":
            self._set_servo(self.servo + SERVO_STEP)
        elif action == "play_pause":
            self._brake()
        elif action == "mute":
            self._toggle_gear()
        elif action == "power":
            self._cycle_lights()

        self.ir._edges.clear()

    # ------------------------------------------------------------------ draw

    def draw(self):
        self.oled.fill(0)
        if not self.connected:
            self.oled.text("DISCONNECTED", 0, 0)
            self.oled.text("Reconnecting...", 0, 20)
        else:
            speed_bar = int(abs(self.speed) / 100 * 10)
            direction = "F" if self.speed > 0 else ("R" if self.speed < 0 else "-")
            self.oled.text(f"SPD:{self.speed:+4d} {direction}{'|'*speed_bar}", 0, 0)

            steer = self.servo - SERVO_CENTER
            steer_str = f"{'<'*max(0,-steer//15)}|{'>'*max(0,steer//15)}"
            gear_str = "LO" if self.gear else "--"
            self.oled.text(f"STR:{self.servo:3d} {steer_str}", 0, 12)
            self.oled.text(f"G:{gear_str} L:{self.lights[:3]}", 0, 24)
        self.oled.show()

    # ------------------------------------------------------------------- run

    def run(self):
        while True:
            # Reconnect logic
            if not self.connected:
                if time.time() - self.last_reconnect >= RECONNECT_INTERVAL:
                    self.last_reconnect = time.time()
                    self._connect_ws()

            # Physical buttons
            if self.controls.was_pressed("up"):
                self._set_speed(self.speed + SPEED_STEP)
            elif self.controls.was_pressed("down"):
                self._set_speed(self.speed - SPEED_STEP)
            elif self.controls.was_pressed("ctrl"):
                self._brake()

            # IR remote
            self._handle_ir()

            self.draw()
            time.sleep(0.05)


def run():
    PicarRemote().run()
