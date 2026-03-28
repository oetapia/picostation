# APP: SERVO
import time
from machine import Pin, PWM
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls

SERVO_PIN = 5
ANGLE_MIN = 0
ANGLE_MAX = 180
ANGLE_STEP = 5
ANGLE_CENTER = 90


def angle_to_duty(angle):
    # 500us to 2500us pulse over 20000us period (50Hz) — matches source/servo.py
    pulse_width = 500 + (angle / 180.0) * 2000
    return int((pulse_width / 20000.0) * 65535)


def run():
    oled = OLEDScreen()._display
    controls = GameControls()

    servo = PWM(Pin(SERVO_PIN))
    servo.freq(50)

    # Reset to center on startup
    angle = ANGLE_CENTER
    oled.fill(0)
    oled.text("SERVO CTRL", 0, 0)
    oled.text("Resetting...", 0, 12)
    oled.show()
    servo.duty_u16(angle_to_duty(angle))
    time.sleep(0.5)

    def draw(a):
        oled.fill(0)
        oled.text("SERVO CTRL", 0, 0)
        oled.text("Angle: {:3d} deg".format(a), 0, 8)
        # Position bar
        bar_x, bar_y, bar_w, bar_h = 8, 19, 112, 5
        oled.rect(bar_x, bar_y, bar_w, bar_h, 1)
        fill_w = int((a / 180.0) * (bar_w - 2))
        if fill_w > 0:
            oled.fill_rect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, 1)
        oled.show()

    draw(angle)

    try:
        while True:
            if controls.was_pressed("up"):
                # UP = move left (decrease angle)
                angle = max(ANGLE_MIN, angle - ANGLE_STEP)
                servo.duty_u16(angle_to_duty(angle))
                draw(angle)
            elif controls.was_pressed("down"):
                # DOWN = move right (increase angle)
                angle = min(ANGLE_MAX, angle + ANGLE_STEP)
                servo.duty_u16(angle_to_duty(angle))
                draw(angle)
            elif controls.was_pressed("ctrl"):
                break
            time.sleep(0.02)
    finally:
        servo.deinit()
