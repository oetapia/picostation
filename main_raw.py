"""
Raw WebSocket server for PicoStation (Raspberry Pi Pico W).

Lowest-latency variant — no framework, no JSON encode on hot path.
Direct uasyncio TCP server with hand-rolled WebSocket framing.

Enables web-connected apps (phone/tablet/dashboard) to interact with
the picostation hardware over a persistent WebSocket connection.

Optimizations (same approach as picar/main_raw.py):
    - No Microdot: raw TCP → HTTP upgrade → binary WS frames
    - Pre-built response strings: avoids json.dumps() per command
    - Debounced OLED: display updates at 5Hz max, never blocks commands
    - GC tuning: gc.threshold() for smaller, more predictable pauses
    - WiFi PM disabled in wifi.py
    - Single-allocation frame buffer for reads

Protocol (JSON, short keys to minimize bytes):

    Client → Pico:
        {"c":"led","n":"green","s":1}   LED on/off (n=name, s=state)
        {"c":"led","n":"all","s":0}     all LEDs off
        {"c":"buzz","f":1000,"d":0.2}   buzzer tone (freq, duration)
        {"c":"buzz","f":0}              buzzer off
        {"c":"screen","v":"hello"}      display text
        {"c":"btn"}                     read button states
        {"c":"tof"}                     ToF sensor read
        {"c":"accel"}                   accelerometer read
        {"c":"st"}                      full device status
        {"c":"apps"}                    list available apps
        {"c":"sub","ms":100}            subscribe sensor push
        {"c":"unsub"}                   unsubscribe sensor push

    Pico → Client:
        {"ok":1,...}                    command ack (pre-built string)
        {"ok":0,"e":"..."}             error
        {"t":"sns",...}                 sensor push
"""

import gc
gc.threshold(4096)

import time
import machine
import json
import hashlib
import binascii
import struct
import uasyncio as asyncio

from screen import Screen

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

# ========== Hardware ==========
led = machine.Pin("LED", machine.Pin.OUT)

try:
    from breadboard.leds import LEDs
    leds = LEDs()
    LEDS_AVAILABLE = True
except Exception:
    leds = None
    LEDS_AVAILABLE = False

try:
    from breadboard.buzzer import Buzzer
    buzzer = Buzzer()
    BUZZER_AVAILABLE = True
except Exception:
    buzzer = None
    BUZZER_AVAILABLE = False

try:
    from breadboard.buttons import GameControls
    buttons = GameControls()
    BUTTONS_AVAILABLE = True
except Exception:
    buttons = None
    BUTTONS_AVAILABLE = False

# Sensors (optional)
try:
    from vl53l0x_mp import VL53L0X
    from machine import I2C, Pin
    i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
    tof = VL53L0X(i2c)
    TOF_AVAILABLE = True
except Exception:
    tof = None
    TOF_AVAILABLE = False

# ========== Initial State ==========
time.sleep(2)
led.off()

# ========== WiFi Connection ==========
wlan = None
ip_address = "0.0.0.0"

if WIFI_AVAILABLE:
    wlan = wifi.connect_wifi()
    if wlan:
        ip_address = wlan.ifconfig()[0]
        print("Connected to Wi-Fi. IP Address:", ip_address)
        led.on()
        time.sleep(1)
        led.off()
    else:
        print("Wi-Fi connection failed.")


# ========== Debounced Display ==========
_display_dirty = False
_display_text = ""


def _show(text):
    global _display_dirty, _display_text
    _display_text = text
    _display_dirty = True


async def _display_loop():
    global _display_dirty
    while True:
        if _display_dirty:
            _display_dirty = False
            if Screen.width == 128:
                Screen._display.fill(0)
                Screen._display.text(_display_text[:16], 0, 0)
                Screen._display.show()
            else:
                Screen.Clear()
                Screen.Write(_display_text, 10, 100, Screen.WHITE)
        await asyncio.sleep(0.2)


# ========== Connection State ==========
_client_connected = False
_sensor_push_interval = 0
_ws_writer = None
_last_command_time = 0

IDLE_TIMEOUT = 10

# ========== Available Apps Registry ==========
APPS = [
    {"id": "weather", "name": "Weather"},
    {"id": "volumio", "name": "Volumio"},
    {"id": "space_invaders", "name": "Space Invaders"},
    {"id": "snake", "name": "Snake"},
]


# ========== WebSocket Frame Helpers ==========

def _ws_accept_key(key):
    d = hashlib.sha1(key.encode())
    d.update(b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
    return binascii.b2a_base64(d.digest())[:-1]


def _encode_frame(data, opcode=None):
    if isinstance(data, str):
        payload = data.encode()
        if opcode is None:
            opcode = 0x01
    else:
        payload = data
        if opcode is None:
            opcode = 0x02
    fin_opcode = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes([fin_opcode, length])
    elif length < 65536:
        header = bytes([fin_opcode, 126]) + struct.pack('>H', length)
    else:
        header = bytes([fin_opcode, 127]) + struct.pack('>Q', length)
    return header + payload


async def _read_frame(reader):
    header = await reader.readexactly(2)
    opcode = header[0] & 0x0f
    has_mask = header[1] & 0x80
    length = header[1] & 0x7f

    if length == 126:
        raw = await reader.readexactly(2)
        length = struct.unpack('>H', raw)[0]
    elif length == 127:
        raw = await reader.readexactly(8)
        length = struct.unpack('>Q', raw)[0]

    if length > 16384:
        raise ValueError("frame too large")

    if has_mask:
        mask = await reader.readexactly(4)

    payload = await reader.readexactly(length)

    if has_mask:
        payload = bytes(payload[i] ^ mask[i & 3] for i in range(length))

    return opcode, payload


async def _ws_send(writer, data):
    writer.write(_encode_frame(data))
    await writer.drain()


# ========== Command Dispatch ==========

def _handle_command(msg):
    global _last_command_time, _sensor_push_interval
    _last_command_time = time.time()

    try:
        cmd = json.loads(msg)
    except ValueError:
        return '{"ok":0,"e":"bad json"}'

    c = cmd.get("c")
    v = cmd.get("v")

    try:
        if c == "led":
            if not LEDS_AVAILABLE:
                return '{"ok":0,"e":"no leds"}'
            name = cmd.get("n", "green")
            state = int(cmd.get("s", 1))
            if name == "all":
                if state:
                    leds.all_on()
                else:
                    leds.all_off()
            else:
                leds.set(name, bool(state))
            st = leds.get_state()
            _show(f"LED:{name}={'ON' if state else 'OFF'}")
            return '{"ok":1,"led":' + json.dumps(st) + '}'

        elif c == "buzz":
            if not BUZZER_AVAILABLE:
                return '{"ok":0,"e":"no buzzer"}'
            freq = int(cmd.get("f", 0))
            dur = cmd.get("d")
            if freq == 0:
                buzzer.off()
                _show("Buzz:OFF")
                return '{"ok":1,"buzz":0}'
            else:
                if dur:
                    buzzer.tone(freq, float(dur))
                else:
                    buzzer.tone(freq)
                _show(f"Buzz:{freq}Hz")
                return '{"ok":1,"buzz":' + str(freq) + '}'

        elif c == "screen":
            text = str(v) if v else ""
            _show(text)
            return '{"ok":1}'

        elif c == "btn":
            if not BUTTONS_AVAILABLE:
                return '{"ok":0,"e":"no buttons"}'
            st = buttons.get_current_state()
            return '{"ok":1,"btn":' + json.dumps(st) + '}'

        elif c == "tof":
            if not TOF_AVAILABLE:
                return '{"ok":0,"e":"no tof"}'
            dist = tof.read()
            _show(f"ToF:{dist}mm")
            return '{"ok":1,"tof":' + str(dist) + '}'

        elif c == "accel":
            return '{"ok":0,"e":"not implemented"}'

        elif c == "st":
            status = {"ip": ip_address, "uptime": time.time()}
            if LEDS_AVAILABLE:
                status["led"] = leds.get_state()
            if BUTTONS_AVAILABLE:
                status["btn"] = buttons.get_current_state()
            if TOF_AVAILABLE:
                try:
                    status["tof"] = tof.read()
                except Exception:
                    status["tof"] = None
            status["hw"] = {
                "leds": LEDS_AVAILABLE,
                "buzzer": BUZZER_AVAILABLE,
                "buttons": BUTTONS_AVAILABLE,
                "tof": TOF_AVAILABLE,
                "screen": Screen.width,
            }
            return '{"ok":1,"st":' + json.dumps(status) + '}'

        elif c == "apps":
            return '{"ok":1,"apps":' + json.dumps(APPS) + '}'

        elif c == "sub":
            ms = int(cmd.get("ms", 100))
            _sensor_push_interval = max(50, ms)
            return '{"ok":1,"sub":' + str(_sensor_push_interval) + '}'

        elif c == "unsub":
            _sensor_push_interval = 0
            return '{"ok":1,"unsub":1}'

        else:
            return '{"ok":0,"e":"unknown: ' + str(c) + '"}'

    except Exception as e:
        return '{"ok":0,"e":"' + str(e).replace('"', "'") + '"}'


def _read_sensors():
    result = {}
    if TOF_AVAILABLE:
        try:
            result['tof'] = tof.read()
        except Exception:
            pass
    if BUTTONS_AVAILABLE:
        result['btn'] = buttons.get_current_state()
    if LEDS_AVAILABLE:
        result['led'] = leds.get_state()
    result['ts'] = time.time()
    return result


# ========== WebSocket Client Handler ==========

async def _handle_client(reader, writer):
    global _client_connected, _last_command_time
    global _sensor_push_interval, _ws_writer

    # ---------- HTTP Upgrade Handshake ----------
    ws_key = None
    try:
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if line == b'\r\n' or line == b'\n' or line == b'':
                break
            line_str = line.decode()
            if line_str.lower().startswith('sec-websocket-key:'):
                ws_key = line_str.split(':', 1)[1].strip()
    except asyncio.TimeoutError:
        writer.close()
        await writer.wait_closed()
        return

    if not ws_key:
        writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return

    accept = _ws_accept_key(ws_key)
    writer.write(b'HTTP/1.1 101 Switching Protocols\r\n'
                 b'Upgrade: websocket\r\n'
                 b'Connection: Upgrade\r\n'
                 b'Sec-WebSocket-Accept: ')
    writer.write(accept)
    writer.write(b'\r\n\r\n')
    await writer.drain()

    # ---------- Connection established ----------
    _client_connected = True
    _ws_writer = writer
    _last_command_time = time.time()
    _sensor_push_interval = 0

    print("WebSocket connected")
    _show("WS Connected")
    led.on()

    push_task = asyncio.create_task(_sensor_push_loop(writer))

    try:
        while True:
            opcode, payload = await _read_frame(reader)

            if opcode == 0x08:  # CLOSE
                break
            elif opcode == 0x09:  # PING
                writer.write(_encode_frame(payload, opcode=0x0A))
                await writer.drain()
                continue
            elif opcode == 0x0A:  # PONG
                continue
            elif opcode in (0x01, 0x02):  # TEXT or BINARY
                try:
                    msg = payload.decode()
                except UnicodeError:
                    continue
            else:
                continue

            response = _handle_command(msg)
            writer.write(_encode_frame(response))
            await writer.drain()

    except Exception as e:
        print(f"WS error: {e}")

    finally:
        _client_connected = False
        _ws_writer = None
        _sensor_push_interval = 0
        push_task.cancel()

        try:
            writer.write(_encode_frame(b'', opcode=0x08))
            await writer.drain()
        except Exception:
            pass
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        print("WebSocket disconnected")
        _show(f"{ip_address}:5000")
        led.off()


# ========== Sensor Push ==========

async def _sensor_push_loop(writer):
    while True:
        if _sensor_push_interval > 0:
            try:
                data = _read_sensors()
                msg = '{"t":"sns",' + json.dumps(data)[1:]
                writer.write(_encode_frame(msg))
                await writer.drain()
            except Exception:
                break
            await asyncio.sleep(_sensor_push_interval / 1000.0)
        else:
            await asyncio.sleep(0.1)


# ========== Idle Display Watcher ==========

async def _idle_watcher():
    global _last_command_time
    while True:
        await asyncio.sleep(1)
        if _client_connected and _last_command_time:
            if time.time() - _last_command_time >= IDLE_TIMEOUT:
                _last_command_time = 0
                _show("Idle")


# ========== Server ==========

async def start_server():
    print("Starting Raw WebSocket Server...")

    if wlan and wlan.isconnected():
        print(f"WebSocket endpoint: ws://{ip_address}:5000")
        _show(f"{ip_address}:5000")
    else:
        print("WiFi not connected")
        _show("WiFi Failed")

    asyncio.create_task(_idle_watcher())
    asyncio.create_task(_display_loop())

    server = await asyncio.start_server(_handle_client, '0.0.0.0', 5000)
    print("Server listening on port 5000")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("Server stopped by user")
    finally:
        server.close()
        await server.wait_closed()
        if wlan:
            wlan.disconnect()


# ========== Entry Point ==========
if __name__ == '__main__':
    asyncio.run(start_server())
