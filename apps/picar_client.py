# APP: PICAR
import urequests
import time
import machine
from screen import Screen

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("WiFi modules not available")

led = machine.Pin("LED", machine.Pin.OUT)
led.off()


class PicarApp:
    def __init__(self):
        picar_ip = getattr(config, "car_ip", None) if WIFI_AVAILABLE else None
        if not picar_ip:
            picar_ip = "192.168.178.59"
        self.base_url = f"http://{picar_ip}:5000"

        self.motor_speed = 0
        self.servo_angle = 90
        self.lights = "off"
        self._last_light_target = ""

        # Sensor cache
        self.tof_left = None
        self.tof_right = None
        self.ultrasonic_cm = None
        self.tilt_pitch = 0
        self.tilt_roll = 0

        self.connected = False
        self.error_message = ""
        self.needs_redraw = True

        self._last_input_ms = 0
        self._input_cooldown_ms = 150

        self.prev_state = None

        if WIFI_AVAILABLE:
            self.connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if self.connected:
                self.fetch_status()
        else:
            self.error_message = "WiFi not available"

    # ========== HTTP helpers ==========
    def _get(self, path):
        url = f"{self.base_url}{path}"
        try:
            response = urequests.get(url, timeout=2)
        except TypeError:
            # urequests build without timeout kwarg
            response = urequests.get(url)
        try:
            data = response.json()
        finally:
            response.close()
        return data

    # ========== Picar API ==========
    def fetch_status(self):
        try:
            result = self._get("/api/status")
            self.motor_speed = result.get("motor_speed", self.motor_speed)
            self.servo_angle = result.get("servo_angle", self.servo_angle)
            self.error_message = ""
            self.needs_redraw = True
        except Exception as e:
            print("Status error:", e)
            self.error_message = "Status failed"
            self.needs_redraw = True

    def set_motor(self, speed):
        speed = max(-100, min(100, int(speed)))
        try:
            self._get(f"/api/motor/{speed}")
            self.motor_speed = speed
            self.error_message = ""
            self.needs_redraw = True
            self._auto_light(speed)
        except Exception as e:
            print("Motor error:", e)
            self.error_message = "Motor failed"
            self.needs_redraw = True

    def set_servo(self, angle):
        angle = max(0, min(180, int(angle)))
        try:
            self._get(f"/api/servo/{angle}")
            self.servo_angle = angle
            self.error_message = ""
            self.needs_redraw = True
        except Exception as e:
            print("Servo error:", e)
            self.error_message = "Servo failed"
            self.needs_redraw = True

    def _auto_light(self, speed):
        if speed > 0:
            target = "front"
        elif speed < 0:
            target = "back"
        else:
            target = "off"
        if target != self._last_light_target:
            try:
                self._get(f"/api/lights/{target}")
                self.lights = target
                self._last_light_target = target
            except Exception as e:
                print("Auto light error:", e)

    def fetch_sensors(self):
        try:
            tof = self._get("/api/tof")
            if tof.get("success"):
                self.tof_left = tof.get("left_distance_cm")
                self.tof_right = tof.get("right_distance_cm")
        except Exception as e:
            print("ToF error:", e)
            self.tof_left = None
            self.tof_right = None

        try:
            us = self._get("/api/ultrasonic")
            if us.get("success") and us.get("in_range"):
                self.ultrasonic_cm = us.get("distance_cm")
            else:
                self.ultrasonic_cm = None
        except Exception as e:
            print("Ultrasonic error:", e)
            self.ultrasonic_cm = None

        try:
            acc = self._get("/api/accelerometer")
            if acc.get("success"):
                tilt = acc.get("tilt", {})
                self.tilt_pitch = tilt.get("pitch", 0)
                self.tilt_roll = tilt.get("roll", 0)
        except Exception as e:
            print("Accel error:", e)

        self.needs_redraw = True

    # ========== Input ==========
    def handle_input(self):
        # X always exits immediately, no debounce
        if Screen.ButtonX():
            self.set_motor(0)
            return "exit"

        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_input_ms) < self._input_cooldown_ms:
            return None

        acted = True
        if Screen.Up():
            self.set_motor(min(100, self.motor_speed + 25))
        elif Screen.Down():
            self.set_motor(max(-100, self.motor_speed - 25))
        elif Screen.Left():
            self.set_servo(max(0, self.servo_angle - 15))
        elif Screen.Right():
            self.set_servo(min(180, self.servo_angle + 15))
        elif Screen.Center():
            self.fetch_sensors()
        elif Screen.ButtonB():
            self.set_motor(0)
        elif Screen.ButtonY():
            self.set_servo(90)
        else:
            acted = False

        if acted:
            self._last_input_ms = now
        return None

    # ========== Drawing ==========
    def draw(self):
        if not self.needs_redraw:
            return

        Screen.BeginDraw()
        Screen.Clear()

        if not self.connected:
            Screen.Write("PICAR REMOTE", 60, 20, Screen.YELLOW)
            Screen.Write("Not Connected", 60, 100, Screen.RED)
            Screen.Write(self.error_message, 20, 120, Screen.RED)
            Screen.Write("X: Back to Menu", 50, 200, Screen.CYAN)
            Screen.EndDraw()
            self.needs_redraw = False
            return

        # Header
        Screen.Write("PICAR REMOTE", 60, 10, Screen.YELLOW)
        Screen.DrawLine(10, 25, 230, 25, Screen.YELLOW)

        # Motor speed
        motor_color = Screen.GREEN if self.motor_speed > 0 else (Screen.RED if self.motor_speed < 0 else Screen.WHITE)
        Screen.Write("Motor:", 10, 35, Screen.WHITE)
        Screen.Write(f"{self.motor_speed:+d}", 80, 35, motor_color)
        # Speed bar (centered at x=140, width 90, height 8)
        Screen.DrawRect(140, 37, 90, 8, Screen.WHITE)
        bar_len = int(abs(self.motor_speed) * 0.45)  # half-width per side
        if self.motor_speed > 0:
            Screen.DrawRect(185, 37, bar_len, 8, Screen.GREEN, filled=True)
        elif self.motor_speed < 0:
            Screen.DrawRect(185 - bar_len, 37, bar_len, 8, Screen.RED, filled=True)

        # Servo angle
        Screen.Write("Steer:", 10, 55, Screen.WHITE)
        offset = self.servo_angle - 90
        steer_text = f"{offset:+d}" if offset != 0 else "centre"
        Screen.Write(steer_text, 80, 55, Screen.CYAN)

        # Lights
        Screen.Write("Lights:", 10, 75, Screen.WHITE)
        light_color = Screen.YELLOW if self.lights != "off" else Screen.GRAY
        Screen.Write(self.lights, 80, 75, light_color)

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
        Screen.Write("B: stop", 10, 215, Screen.CYAN)
        Screen.Write("Y: center", 80, 215, Screen.CYAN)

        Screen.EndDraw()
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
            self.draw()
            Screen.Sleep(0.05)


def launch_picar():
    app = PicarApp()
    app.run()


run = launch_picar
