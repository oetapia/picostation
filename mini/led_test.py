import time
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs


def run():
    oled = OLEDScreen()._display
    controls = GameControls()
    leds = LEDs()

    def draw(state):
        oled.fill(0)
        oled.text("LED TEST", 0, 0)
        oled.text("UP   = green", 0, 12)
        oled.text("DOWN = red", 0, 22)
        oled.show()

    draw(None)

    while True:
        up = controls.is_pressed(controls.up)
        down = controls.is_pressed(controls.down)
        leds.set('green', up)
        leds.set('red', down)
        time.sleep(0.02)
