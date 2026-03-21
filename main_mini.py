import time
import framebuf
import machine
import icons_16.icons as icons
from screen import Screen
from breadboard.buttons import GameControls

# Initialize LED
led = machine.Pin("LED", machine.Pin.OUT)
led.off()

oled = Screen._display

# Splash screen
icon_data = icons.ghost
size = 16
bpr = 2
buf = bytearray(bpr * size)
for row in range(size):
    for col in range(size):
        if icon_data[row] & (1 << (size - 1 - col)):
            buf[row * bpr + col // 8] |= (1 << (7 - (col % 8)))
fb = framebuf.FrameBuffer(buf, size, size, framebuf.MONO_HLSB)

x = (128 - 56) // 2  # 36
oled.fill(0)
oled.blit(fb, x, 8)
oled.text("mini", x + 24, 12)
oled.show()
time.sleep(3)

# App selection menu
controls = GameControls()

APPS = ["WEATHER", "IR SENSOR", "ACCEL", "LED TEST", "SOUND", "VOLUMIO", "TOF"]
selected = 0
scroll_start = 0
VISIBLE = 4


def draw_menu():
    oled.fill(0)
    for row, idx in enumerate(range(scroll_start, scroll_start + VISIBLE)):
        if idx >= len(APPS):
            break
        prefix = ">" if idx == selected else " "
        oled.text(f"{prefix} {APPS[idx]}", 0, row * 8)
    oled.show()


draw_menu()

while True:
    if controls.was_pressed("up"):
        selected = (selected - 1) % len(APPS)
        if selected < scroll_start:
            scroll_start = selected
        elif selected == len(APPS) - 1:
            scroll_start = max(0, len(APPS) - VISIBLE)
        draw_menu()
    elif controls.was_pressed("down"):
        selected = (selected + 1) % len(APPS)
        if selected >= scroll_start + VISIBLE:
            scroll_start = selected - VISIBLE + 1
        elif selected == 0:
            scroll_start = 0
        draw_menu()
    elif controls.was_pressed("ctrl"):
        break
    time.sleep(0.05)

if selected == 0:
    from mini.weather import MiniWeather
    MiniWeather().run()
elif selected == 1:
    from mini.sensor_main import run as run_sensor
    run_sensor()
elif selected == 2:
    from mini.accel_main import run as run_accel
    run_accel()
elif selected == 3:
    from mini.led_test import run as run_led_test
    run_led_test()
elif selected == 4:
    from mini.sound_app import run as run_sound
    run_sound()
elif selected == 5:
    from mini.volumio_mini import run as run_volumio
    run_volumio()
else:
    from mini.tof_main import run as run_tof
    run_tof()
