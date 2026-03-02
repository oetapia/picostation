from machine import Pin
import time
import urequests
import json

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("WiFi modules not available")

# -------------------------
# Connect Wi-Fi
# -------------------------
connected = False
if WIFI_AVAILABLE:
    connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
    if connected:
        print("WiFi connected!")
    else:
        print("WiFi connection failed")

# -------------------------
# IR sensor setup
# -------------------------
ir_sensor = Pin(18, Pin.IN, Pin.PULL_UP)
print("IR break-beam monitoring started...")

# -------------------------
# Helper: publish log
# -------------------------
def log_event(beam_broken):
    if not connected:
        return

    payload = {
        "device_id": getattr(config, "DEVICE_ID", "pico-ir-01"),
        "beam_broken": beam_broken,
        "timestamp": time.time()
    }

    try:
        r = urequests.post(
            config.API_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        r.close()
        print("Logged:", payload)
    except Exception as e:
        print("Log failed:", e)

# -------------------------
# Main loop
# -------------------------
while True:
    if ir_sensor.value() == 0:
        print("Beam broken!")
        log_event(True)
        time.sleep(0.2)  # debounce
