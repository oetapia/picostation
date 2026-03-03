from machine import Pin
import time


class LEDs:
    def __init__(self):
        self.green = Pin(17, Pin.OUT)
        self.red = Pin(13, Pin.OUT)

        # Start with both off
        self.green.off()
        self.red.off()

    def set(self, led_name, state):
        """Set a LED on (True) or off (False) by name"""
        getattr(self, led_name).value(1 if state else 0)

    def on(self, led_name):
        """Turn a LED on by name"""
        getattr(self, led_name).on()

    def off(self, led_name):
        """Turn a LED off by name"""
        getattr(self, led_name).off()

    def all_on(self):
        """Turn all LEDs on"""
        self.green.on()
        self.red.on()

    def all_off(self):
        """Turn all LEDs off"""
        self.green.off()
        self.red.off()

    def get_state(self):
        """Get current state of all LEDs"""
        return {
            'green': bool(self.green.value()),
            'red': bool(self.red.value()),
        }

    def blink(self, led_name, times=1, interval=0.2):
        """Blink a LED a given number of times"""
        led = getattr(self, led_name)
        for _ in range(times):
            led.on()
            time.sleep(interval)
            led.off()
            time.sleep(interval)
