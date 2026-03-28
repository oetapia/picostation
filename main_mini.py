import time
import framebuf
import machine
import ujson
import os
import icons_16.icons as icons
from screen import Screen
from breadboard.buttons import GameControls
from mini.hw477_main import NECDecoder
from mini.rc6_sniffer import RC6Decoder

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

# App selection menu — auto-discovered from # APP: headers in mini/*.py
def _discover_apps():
    apps = []
    try:
        for fname in sorted(os.listdir("mini")):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            try:
                with open("mini/" + fname) as fp:
                    line = fp.readline().strip()
                if line.startswith("# APP:"):
                    apps.append((line[6:].strip(), fname[:-3]))
            except OSError:
                pass
    except OSError:
        pass
    return apps  # [(label, module_stem), ...]

APPS = _discover_apps()
controls = GameControls()
selected = 0
scroll_start = 0
VISIBLE = 4

# IR remote setup — graceful if profiles are missing
try:
    with open("ir_profiles/remote_tiny.json") as f:
        _d = ujson.load(f)
    _nec_addr = int(_d["address"], 16)
    _nec_cmds = {int(k, 16): v for k, v in _d["commands"].items()}
    _nec_ir   = NECDecoder(pin_num=12)
    print("IR NEC loaded: addr=0x{:02X} cmds={}".format(_nec_addr, len(_nec_cmds)))
except OSError as e:
    _nec_addr, _nec_cmds, _nec_ir = None, {}, None
    print("IR NEC not loaded:", e)

try:
    with open("ir_profiles/remote_xbox_clone.json") as f:
        _d = ujson.load(f)
    _rc6_cmds = {k.upper(): v for k, v in _d["commands"].items()}
    _rc6_ir   = RC6Decoder(pin_num=12)
    print("IR RC6 loaded: cmds={}".format(len(_rc6_cmds)))
except OSError as e:
    _rc6_cmds, _rc6_ir = {}, None
    print("IR RC6 not loaded:", e)

# Both decoders share GP12 — RC6 init overwrites NEC's IRQ handler.
# Disable NEC to avoid its dead ISR causing confusion.
# Deploy with --remote tiny OR --remote xbox to avoid this.
if _nec_ir and _rc6_ir:
    print("IR WARNING: NEC and RC6 share GP12 — NEC disabled. Use --remote to deploy one profile only.")
    _nec_ir = None


def _ir_action():
    if _rc6_ir:
        n = len(_rc6_ir._edges)
        if n > 0:
            silence = time.ticks_diff(time.ticks_us(), _rc6_ir._last_time)
            print("RC6 buf={} silence={}us".format(n, silence))
    if _nec_ir and _nec_ir.poll():
        _nec_ir.received = False
        if _nec_ir.address == _nec_addr:
            action = _nec_cmds.get(_nec_ir.command)
            print("IR NEC addr=0x{:02X} cmd=0x{:02X} -> {}".format(_nec_ir.address, _nec_ir.command, action))
            return action
    if _rc6_ir and _rc6_ir.poll():
        _rc6_ir.received = False
        key = "{:04X}:{:02X}".format(_rc6_ir.address or 0, _rc6_ir.command or 0)
        action = _rc6_cmds.get(key)
        print("IR RC6 key={} -> {}".format(key, action))
        return action
    return None


def draw_menu():
    oled.fill(0)
    for row, idx in enumerate(range(scroll_start, scroll_start + VISIBLE)):
        if idx >= len(APPS):
            break
        prefix = ">" if idx == selected else " "
        oled.text("{} {}".format(prefix, APPS[idx][0]), 0, row * 8)
    oled.show()


while True:
    draw_menu()

    while True:
        action = None
        if controls.was_pressed("up"):
            action = "up"
        elif controls.was_pressed("down"):
            action = "down"
        elif controls.was_pressed("ctrl"):
            action = "select"
        else:
            action = _ir_action()

        if action == "up":
            selected = (selected - 1) % len(APPS)
            if selected < scroll_start:
                scroll_start = selected
            elif selected == len(APPS) - 1:
                scroll_start = max(0, len(APPS) - VISIBLE)
            draw_menu()
        elif action == "down":
            selected = (selected + 1) % len(APPS)
            if selected >= scroll_start + VISIBLE:
                scroll_start = selected - VISIBLE + 1
            elif selected == 0:
                scroll_start = 0
            draw_menu()
        elif action in ("select", "enter", "play"):
            break
        time.sleep(0.05)

    _, stem = APPS[selected]
    mod = __import__("mini." + stem, None, None, ["run"])
    mod.run()
