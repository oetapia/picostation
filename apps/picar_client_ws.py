"""
apps/picar_client_ws.py — PiCar remote control over WebSocket (TFT).

Connects to picar's raw WS server (main_raw.py) using the same JSON
protocol: {"c":"m","v":50}, {"c":"s","v":90}, etc.

Lower latency than the REST-based picar_client.py — persistent connection,
no HTTP overhead per command.
"""

import time
import json
import machine
from screen import Screen
from lib.ws_client import WebSocketClient

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("WiFi modules not available")

led = machine.Pin("LED", machine.Pin.OUT)
led.off()

SPEED_STEP = 25
SERVO_STEP = 15
RECONNECT_INTERVAL = 5


class PicarWsApp:
    def __init__(self):
        picar_ip = getattr(config, "PICAR_IP", None) if WIFI_AVAILABLE else None
        picar_port = getattr(config, "PICAR_PORT", 5000) if WIFI_AVAILABLE else 5000
        if not picar_ip:
            picar_ip = "192.168.1.100"
        self.picar_ip = picar_ip
        self.picar_port = picar_port

        self.ws = None
        self.motor_speed = 0
        self.servo_angle = 90
        self.gear = 0
        self.lights = "off"

        # Sensors
        self.tof_left = None
        self.tof_right = None
        self.ultrasonic_cm = None
        self.tilt_pitch = 0
        self.tilt_roll = 0

        self.last_sensor_update = 0
        self.sensor_update_interval = 1
        self.last_reconnect = 0

        self.connected = False
        self.wifi_connected = False
        self.error_message = ""
        self.needs_redraw = True

        if WIFI_AVAILABLE:
            self.wifi_connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if self.wifi_connected:
                self._connect_ws()
        else:
            self.error_message = "WiFi not available"

    def _connect_ws(self):
        try:
            self.ws = WebSocketClient(self.picar_ip, self.picar_port, timeout=3)
            self.ws.connect()
            self.connected = True
            self.error_message = ""
            self._fetch_status()
            self.needs_redraw = True
        except Exception as e:
            self.connected = False
            self.ws = None
            self.error_message = f"WS: {str(e)[:20]}"
            self.needs_redraw = True

    def _send(self, cmd_dict):
        if not self.connected or not self.ws:
            return None
        try:
            self.ws.send(json.dumps(cmd_dict))
            resp = self.ws.recv(timeout=1)
            if resp is None:
                self._disconnect()
                return None
            return json.loads(resp)
        except Exception as e:
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
        self.error_message = "Disconnected"
        self.needs_redraw = True

    def _fetch_status(self):
        resp = self._send({"c": "st"})
        if resp and resp.get("ok"):
            st = resp.get("st", {})
            self.motor_speed = st.get("m", 0)
            self.servo_angle = st.get("s", 90)
            self.gear = st.get("g", 0)
            self.lights = st.get("l", "off")
            self.needs_redraw = True

    def _fetch_sensors(self):
        resp = self._send({"c": "sns"})
        if resp and resp.get("ok"):
            sns = resp.get("sns", {})
            tof = sns.get("tof", {})
            self.tof_left = tof.get("l")
            self.tof_right = tof.get("r")
            ultra = sns.get("ultra", {})
            self.ultrasonic_cm = ultra.get("d")
            accel = sns.get("accel", {})
            self.tilt_pitch = accel.get("p", 0)
            self.tilt_roll = accel.get("r", 0)
            self.needs_redraw = True

    def set_motor(self, speed):
        speed = max(-100, min(100, int(speed)))
        resp = self._send({"c": "m", "v": speed})
        if resp and resp.get("ok"):
            self.motor_speed = resp.get("m", speed)
            self._auto_light(self.motor_speed)
            self.needs_redraw = True

    def brake(self):
        resp = self._send({"c": "b"})
        if resp and resp.get("ok"):
            self.motor_speed = 0
            self._auto_light(0)
            self.needs_redraw = True

    def set_servo(self, angle):
        angle = max(0, min(180, int(angle)))
        resp = self._send({"c": "s", "v": angle})
        if resp and resp.get("ok"):
            self.servo_angle = resp.get("s", angle)
            self.needs_redraw = True

    def toggle_gear(self):
        resp = self._send({"c": "g", "v": "toggle"})
        if resp and resp.get("ok"):
            self.gear = resp.get("g", 0)
            self.needs_redraw = True

    def _auto_light(self, speed):
        if speed > 0:
            target = "front"
        elif speed < 0:
            target = "back"
        else:
            target = "off"
        if target != self.lights:
            resp = self._send({"c": "l", "v": target})
            if resp and resp.get("ok"):
                self.lights = resp.get("l", target)

    # ========== Input ==========
    def handle_input(self):
        if Screen.Up():
            self.set_motor(min(100, self.motor_speed + SPEED_STEP))
            Screen.Sleep(0.2)

        elif Screen.Down():
            self.set_motor(max(-100, self.motor_speed - SPEED_STEP))
            Screen.Sleep(0.2)

        elif Screen.Left():
            self.set_servo(max(0, self.servo_angle - SERVO_STEP))
            Screen.Sleep(0.15)

        elif Screen.Right():
            self.set_servo(min(180, self.servo_angle + SERVO_STEP))
            Screen.Sleep(0.15)

        elif Screen.ButtonB():
            self.set_motor(75)
            Screen.Sleep(0.2)

        elif Screen.ButtonY():
            self.set_motor(-75)
            Screen.Sleep(0.2)

        elif Screen.ButtonA() or Screen.Center():
            self.brake()
            Screen.Sleep(0.2)

        elif Screen.ButtonX():
            self.brake()
            return "exit"

        return None

    def update(self):
        now = time.time()

        # Reconnect if disconnected
        if not self.connected and self.wifi_connected:
            if now - self.last_reconnect >= RECONNECT_INTERVAL:
                self.last_reconnect = now
                self._connect_ws()

        # Periodic sensor fetch
        if self.connected and now - self.last_sensor_update >= self.sensor_update_interval:
            self._fetch_sensors()
            self.last_sensor_update = now

    # ========== Drawing ==========
    def draw(self):
        if not self.needs_redraw:
            return

        Screen.Clear()

        if not self.wifi_connected:
            Screen.Write("PICAR WS", 70, 20, Screen.YELLOW)
            Screen.Write("Not Connected", 60, 100, Screen.RED)
            Screen.Write(self.error_message, 20, 120, Screen.RED)
            Screen.Write("X: Back to Menu", 50, 200, Screen.CYAN)
            self.needs_redraw = False
            return

        # Header
        conn_color = Screen.GREEN if self.connected else Screen.RED
        conn_text = "WS" if self.connected else "OFFLINE"
        Screen.Write("PICAR", 60, 10, Screen.YELLOW)
        Screen.Write(conn_text, 140, 10, conn_color)
        Screen.DrawLine(10, 25, 230, 25, Screen.YELLOW)

        # Motor speed
        motor_color = Screen.GREEN if self.motor_speed > 0 else (Screen.RED if self.motor_speed < 0 else Screen.WHITE)
        Screen.Write("Motor:", 10, 35, Screen.WHITE)
        Screen.Write(f"{self.motor_speed:+d}", 80, 35, motor_color)
        Screen.DrawRect(140, 37, 90, 8, Screen.WHITE)
        bar_len = int(abs(self.motor_speed) * 0.45)
        if self.motor_speed > 0:
            Screen.DrawRect(185, 37, bar_len, 8, Screen.GREEN, filled=True)
        elif self.motor_speed < 0:
            Screen.DrawRect(185 - bar_len, 37, bar_len, 8, Screen.RED, filled=True)

        # Servo angle
        Screen.Write("Steer:", 10, 55, Screen.WHITE)
        offset = self.servo_angle - 90
        steer_text = f"{offset:+d}" if offset != 0 else "centre"
        Screen.Write(steer_text, 80, 55, Screen.CYAN)

        # Gear + Lights
        gear_str = "LOW" if self.gear else "OFF"
        Screen.Write(f"Gear: {gear_str}", 10, 75, Screen.WHITE)
        light_color = Screen.YELLOW if self.lights != "off" else Screen.GRAY
        Screen.Write(f"Lights: {self.lights}", 120, 75, light_color)

        # Sensors
        Screen.DrawLine(10, 95, 230, 95, Screen.CYAN)
        Screen.Write("SENSORS", 90, 100, Screen.CYAN)

        Screen.Write("ToF L:", 10, 120, Screen.WHITE)
        Screen.Write(self._fmt_cm(self.tof_left), 70, 120, Screen.GREEN)
        Screen.Write("R:", 130, 120, Screen.WHITE)
        Screen.Write(self._fmt_cm(self.tof_right), 160, 120, Screen.GREEN)

        Screen.Write("Rear:", 10, 140, Screen.WHITE)
        rear_color = Screen.RED if self.ultrasonic_cm and self.ultrasonic_cm < 30 else Screen.GREEN
        Screen.Write(self._fmt_cm(self.ultrasonic_cm), 70, 140, rear_color)

        Screen.Write("Tilt:", 10, 160, Screen.WHITE)
        Screen.Write(f"P{self.tilt_pitch:+.0f} R{self.tilt_roll:+.0f}", 70, 160, Screen.WHITE)

        if self.error_message:
            Screen.Write(self.error_message, 10, 180, Screen.RED)

        # Controls
        Screen.DrawLine(10, 195, 230, 195, Screen.CYAN)
        Screen.Write("UP/DN: speed", 10, 205, Screen.CYAN)
        Screen.Write("L/R: steer", 130, 205, Screen.CYAN)
        Screen.Write("B: fwd  Y: rev", 10, 215, Screen.CYAN)
        Screen.Write("A: brake", 140, 215, Screen.CYAN)
        Screen.Write("X: Menu (stops)", 70, 225, Screen.CYAN)

        self.needs_redraw = False

    def _fmt_cm(self, value):
        if value is None:
            return "---"
        return f"{value:.0f}cm"

    def run(self):
        self.needs_redraw = True
        while True:
            result = self.handle_input()
            if result == "exit":
                return
            self.update()
            self.draw()
            Screen.Sleep(0.05)


def launch_picar_ws():
    app = PicarWsApp()
    app.run()
