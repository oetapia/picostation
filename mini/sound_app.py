# APP: SOUND
"""
Sound App - Navigate sounds with UP/DOWN, play with CTRL, exit with UP+DOWN.
Also controllable via NEC (remote_tiny) and RC6 (remote_xbox_clone) IR remotes.
"""
from breadboard.buzzer import Buzzer
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from oled_screen import OLEDScreen
from mini.hw477_main import NECDecoder
from mini.rc6_sniffer import RC6Decoder
import ujson
import time


def _load_nec_profile(path):
    with open(path) as f:
        data = ujson.load(f)
    addr = int(data["address"], 16)
    cmds = {int(k, 16): v for k, v in data["commands"].items()}
    return addr, cmds


def _load_rc6_profile(path):
    with open(path) as f:
        data = ujson.load(f)
    cmds = {k.upper(): v for k, v in data["commands"].items()}
    return cmds

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

    try:
        nec_addr, nec_cmds = _load_nec_profile("ir_profiles/remote_tiny.json")
        nec_ir = NECDecoder(pin_num=12)
        print("IR NEC loaded: addr=0x{:02X} cmds={}".format(nec_addr, len(nec_cmds)))
    except OSError as e:
        nec_addr, nec_cmds, nec_ir = None, {}, None
        print("IR NEC not loaded:", e)

    try:
        rc6_cmds = _load_rc6_profile("ir_profiles/remote_xbox_clone.json")
        rc6_ir   = RC6Decoder(pin_num=12)
        print("IR RC6 loaded: cmds={}".format(len(rc6_cmds)))
    except OSError as e:
        rc6_cmds, rc6_ir = {}, None
        print("IR RC6 not loaded:", e)

    selected = 0
    leds.all_off()

    def draw():
        oled.fill(0)
        for i, s in enumerate(SOUNDS):
            prefix = ">" if i == selected else " "
            oled.text("{} {}".format(prefix, s['name']), 0, i * 10)
        oled.show()

    draw()

    def ir_action():
        """Return the action string from whichever IR remote fired, or None."""
        if nec_ir and nec_ir.poll():
            nec_ir.received = False
            if nec_ir.address == nec_addr:
                action = nec_cmds.get(nec_ir.command)
                print("NEC addr=0x{:02X} cmd=0x{:02X} -> {}".format(nec_ir.address, nec_ir.command, action))
                return action
        if rc6_ir and rc6_ir.poll():
            rc6_ir.received = False
            key = "{:04X}:{:02X}".format(rc6_ir.address or 0, rc6_ir.command or 0)
            action = rc6_cmds.get(key)
            print("RC6 key={} -> {}".format(key, action))
            return action
        return None

    try:
        while True:
            state = buttons.get_current_state()
            if state['up'] and state['down']:
                break

            action = None
            if buttons.was_pressed('up'):
                action = 'up'
            elif buttons.was_pressed('down'):
                action = 'down'
            elif buttons.was_pressed('ctrl'):
                action = 'select'
            else:
                action = ir_action()

            if action == 'up':
                selected = (selected - 1) % len(SOUNDS)
                draw()
            elif action == 'down':
                selected = (selected + 1) % len(SOUNDS)
                draw()
            elif action in ('select', 'enter', 'play'):
                sound = SOUNDS[selected]
                if sound['notes'] is None:
                    _play_sos(buzzer, leds)
                else:
                    _play_notes(buzzer, leds, sound['notes'], sound['led'])
                draw()
            elif action in ('menu', 'back'):
                break

            time.sleep(0.01)
    finally:
        buzzer.off()
        leds.all_off()
        buzzer.deinit()
