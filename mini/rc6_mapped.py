# APP: RC6 MAPPED
import time
import ujson
import os
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from mini.rc6_sniffer import RC6Decoder


PROFILES_DIR = "ir_profiles"


def load_profiles():
    names = []
    try:
        for f in sorted(os.listdir(PROFILES_DIR)):
            if not f.endswith(".json"):
                continue
            try:
                with open("{}/{}".format(PROFILES_DIR, f)) as fp:
                    data = ujson.load(fp)
                if data.get("protocol") == "rc6":
                    names.append(f)
            except (OSError, ValueError):
                pass
    except OSError:
        pass
    return names


def load_profile(filename):
    with open("{}/{}".format(PROFILES_DIR, filename)) as f:
        data = ujson.load(f)
    # Keys are "ADDR:CMD" strings (uppercase) → action label
    cmds = {k.upper(): v for k, v in data["commands"].items()}
    return data.get("name", filename), cmds


def run():
    oled = OLEDScreen()._display
    controls = GameControls()
    leds = LEDs()

    files = load_profiles()

    if not files:
        oled.fill(0)
        oled.text("No RC6 profiles", 0, 0)
        oled.text("in ir_profiles/", 0, 10)
        oled.show()
        return

    selected = 0

    def draw_menu():
        oled.fill(0)
        oled.text("Select remote:", 0, 0)
        VISIBLE = 6
        scroll = max(0, selected - VISIBLE + 1)
        for row, idx in enumerate(range(scroll, scroll + VISIBLE)):
            if idx >= len(files):
                break
            prefix = ">" if idx == selected else " "
            label = files[idx].replace(".json", "")
            oled.text("{} {}".format(prefix, label), 0, 8 + row * 8)
        oled.show()

    draw_menu()

    while True:
        if controls.was_pressed("up"):
            selected = (selected - 1) % len(files)
            draw_menu()
        elif controls.was_pressed("down"):
            selected = (selected + 1) % len(files)
            draw_menu()
        elif controls.was_pressed("ctrl"):
            break
        time.sleep(0.05)

    profile_name, commands = load_profile(files[selected])

    ir = RC6Decoder(pin_num=12)

    MAX_ROWS = 7
    history = []

    def draw():
        oled.fill(0)
        if not history:
            oled.text(profile_name, 0, 0)
            oled.text("Waiting...", 0, 12)
        else:
            for i, line in enumerate(history[:MAX_ROWS]):
                oled.text(line, 0, i * 8)
        oled.show()

    draw()

    while True:
        if ir.poll():
            leds.blink('green', times=1, interval=0.05)
            a = ir.address if ir.address is not None else 0
            c = ir.command if ir.command is not None else 0
            key = "{:04X}:{:02X}".format(a, c)
            label = commands.get(key, key)
            history.insert(0, label)
            if len(history) > MAX_ROWS:
                history.pop()
            ir.received = False
            draw()

        time.sleep_ms(5)
