# APP: IR SENSOR
from machine import Pin
import time
import urequests
from oled_screen import OLEDScreen
from breadboard.leds import LEDs
import json


def run():
    try:
        import wifi
        import config
        WIFI_AVAILABLE = True
    except ImportError:
        WIFI_AVAILABLE = False
        print("WiFi modules not available")

    # -------------------------
    # OLED + LED setup
    # -------------------------
    oled = OLEDScreen()._display
    leds = LEDs()

    def show_status(beam_broken):
        oled.fill(0)
        oled.text("IR SENSOR", 0, 0)
        oled.text("BROKEN!" if beam_broken else "CLEAR", 0, 10)
        oled.text("WiFi:OK" if connected else "WiFi:--", 0, 20)
        oled.show()
        leds.set('red', beam_broken)
        leds.set('green', not beam_broken)

    # -------------------------
    # Connect Wi-Fi
    # -------------------------
    oled.fill(0)
    oled.text("Connecting...", 0, 10)
    oled.show()

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
    ir_sensor = Pin(15, Pin.IN, Pin.PULL_UP)
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
    prev_value = ir_sensor.value()
    show_status(prev_value == 0)

    while True:
        value = ir_sensor.value()
        if value != prev_value:
            if value == 0:
                print("Beam broken!")
                log_event(True)
            else:
                print("Beam clear")
                log_event(False)
            show_status(value == 0)
            prev_value = value
        time.sleep(0.05)
