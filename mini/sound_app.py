"""
Sound App - Navigate sounds with UP/DOWN, play with CTRL, exit with UP+DOWN.
"""
from breadboard.buzzer import Buzzer
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from oled_screen import OLEDScreen
import time

# Morse timing
_DOT  = 0.10
_DASH = 0.30
_SYM  = 0.10  # gap between symbols
_LET  = 0.30  # gap between letters
_FREQ = 1000

# (freq_hz, duration_s)  —  freq=0 is silence
WAH_WAH = [
    (466, 0.20), (0, 0.04),
    (440, 0.20), (0, 0.04),
    (415, 0.20), (0, 0.04),
    (392, 0.50),
]

VICTORY = [
    (659, 0.09), (0, 0.03),   # E5
    (659, 0.09), (0, 0.03),   # E5
    (659, 0.09), (0, 0.03),   # E5
    (523, 0.06), (0, 0.02),   # C5
    (659, 0.12), (0, 0.03),   # E5
    (784, 0.26), (0, 0.05),   # G5
    (392, 0.35),              # G4
]

SOUNDS = [
    {"name": "SOS",     "notes": None,    "led": "green"},
    {"name": "WAH WAH", "notes": WAH_WAH, "led": "red"},
    {"name": "VICTORY", "notes": VICTORY, "led": "green"},
]


def _play_sos(buzzer, leds):
    def dot():
        leds.on('green')
        buzzer.tone(_FREQ, _DOT)
        leds.off('green')
        time.sleep(_SYM)

    def dash():
        leds.on('green')
        buzzer.tone(_FREQ, _DASH)
        leds.off('green')
        time.sleep(_SYM)

    for _ in range(3): dot()
    leds.on('red');  time.sleep(_LET);  leds.off('red')
    for _ in range(3): dash()
    leds.on('red');  time.sleep(_LET);  leds.off('red')
    for _ in range(3): dot()


def _play_notes(buzzer, leds, notes, led):
    for freq, dur in notes:
        if freq == 0:
            time.sleep(dur)
        else:
            leds.on(led)
            buzzer.tone(freq, dur)
            leds.off(led)


def run():
    buzzer  = Buzzer()
    buttons = GameControls()
    leds    = LEDs()
    oled    = OLEDScreen()._display

    selected = 0
    leds.all_off()

    def draw():
        oled.fill(0)
        for i, s in enumerate(SOUNDS):
            prefix = ">" if i == selected else " "
            oled.text(f"{prefix} {s['name']}", 0, i * 10)
        oled.show()

    draw()

    try:
        while True:
            state = buttons.get_current_state()

            if state['up'] and state['down']:
                break

            if buttons.was_pressed('up'):
                selected = (selected - 1) % len(SOUNDS)
                draw()
            elif buttons.was_pressed('down'):
                selected = (selected + 1) % len(SOUNDS)
                draw()
            elif buttons.was_pressed('ctrl'):
                sound = SOUNDS[selected]
                if sound['notes'] is None:
                    _play_sos(buzzer, leds)
                else:
                    _play_notes(buzzer, leds, sound['notes'], sound['led'])
                draw()

            time.sleep(0.01)
    finally:
        buzzer.off()
        leds.all_off()
        buzzer.deinit()
