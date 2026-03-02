import network
import time
import machine
import config

# Initialize LED
led = machine.Pin("LED", machine.Pin.OUT)
time.sleep(2)
led.off()  # Make sure the LED is off initially

def lights(duration):
    led.on()
    time.sleep(duration)
    led.off()

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    lights(1)
    lights(1)

    timeout = 10
    start_time = time.time()
    while not wlan.isconnected():
        if time.time() - start_time > timeout:
            print('Failed to connect to Wi-Fi.')
            lights(2)
            return None  # ✅ Return None instead of False
        lights(1)
        lights(1)
        time.sleep(1)

    print('Connected to Wi-Fi:', wlan.ifconfig())
    lights(3)
    return wlan  # ✅ Return the wlan object instead of True
