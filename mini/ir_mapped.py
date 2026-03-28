# APP: IR MAPPED
import time
import ujson
import os
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls
from breadboard.leds import LEDs
from mini.hw477_main import NECDecoder


PROFILES_DIR = "ir_profiles"


def load_profiles():
    names = []
    try:
        for f in os.listdir(PROFILES_DIR):
            if f.endswith(".json"):
                names.append(f)
    except OSError:
        pass
    return sorted(names)


def load_profile(filename):
    with open("{}/{}".format(PROFILES_DIR, filename)) as f:
        data = ujson.load(f)
    # Normalise keys to lowercase int for fast lookup
    cmds = {}
    for k, v in data["commands"].items():
        cmds[int(k, 16)] = v
    return data.get("name", filename), int(data["address"], 16), cmds


def run():
    oled = OLEDScreen()._display
    controls = GameControls()
    leds = LEDs()

    # -------------------------
    # Profile selection menu
    # -------------------------
    files = load_profiles()

    if not files:
        oled.fill(0)
        oled.text("No profiles", 0, 0)
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

    profile_name, profile_addr, commands = load_profile(files[selected])

    # -------------------------
    # IR receive loop
    # -------------------------
    ir = NECDecoder(pin_num=12)

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
            if ir.repeat:
                if history:
                    history[0] = history[0].rstrip("*") + "*"
            else:
                if ir.address == profile_addr:
                    label = commands.get(ir.command,
                                         "C:{:02X}".format(ir.command))
                else:
                    label = "A:{:02X} C:{:02X}".format(ir.address, ir.command)
                history.insert(0, label)
                if len(history) > MAX_ROWS:
                    history.pop()
            ir.received = False
            draw()

        time.sleep(0.01)
