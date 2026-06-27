import time
import network
import config


def connect_wifi(ssid=None, password=None):
    """Connect to WiFi. Returns wlan object (truthy) or None on failure.

    Accepts optional ssid/password for backwards compat with existing apps.
    Falls back to config.WIFI_SSID / config.WIFI_PASSWORD if not provided.
    """
    ssid = ssid or config.WIFI_SSID
    password = password or config.WIFI_PASSWORD

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f'Connecting to WiFi: {ssid}')
        wlan.connect(ssid, password)

        timeout = 10
        while timeout > 0:
            if wlan.isconnected():
                break
            print('Waiting for connection...')
            time.sleep(1)
            timeout -= 1

        if not wlan.isconnected():
            print('WiFi connection failed!')
            return None

    # Disable WiFi power management — prevents the CYW43 radio from sleeping
    # between packets, which otherwise causes 1-2s wake-up latency per request.
    wlan.config(pm=0xa11140)

    ip_info = wlan.ifconfig()
    print(f'Connected to WiFi. IP: {ip_info[0]}')
    return wlan
