import network
import time
import machine
import config


# Initialize LED
led = machine.Pin("LED", machine.Pin.OUT)
time.sleep(2)
led.off()  # Make sure the LED is off initially


def lights(duration):
    led.on()  # Turn on the LED when a connection is accepted
    time.sleep(duration)
    led.off()  # Turn on the LED when a connection is accepte

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    lights(1)
    lights(1)

    # Wait for connection or timeout after a certain period
    timeout = 10  # Timeout period in seconds
    start_time = time.time()
    while not wlan.isconnected():
        if time.time() - start_time > timeout:
            print('Failed to connect to Wi-Fi.')
            lights(2)  # Indicate connection failure
            return False
        lights(1)
        lights(1)
        time.sleep(1)  # Add a small delay to avoid excessive CPU usage

    print('Connected to Wi-Fi:', wlan.ifconfig())
    lights(3)
    return True




#connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)





