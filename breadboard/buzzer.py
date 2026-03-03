from machine import Pin, PWM
import time


class Buzzer:
    def __init__(self, pin=20):
        self.pwm = PWM(Pin(pin))
        self.pwm.duty_u16(0)  # Start silent

    def tone(self, freq, duration=None):
        """Play a tone at given frequency (Hz). If duration given, blocks until done."""
        self.pwm.freq(freq)
        self.pwm.duty_u16(32768)  # 50% duty cycle
        if duration is not None:
            time.sleep(duration)
            self.off()

    def off(self):
        """Stop the buzzer."""
        self.pwm.duty_u16(0)

    def beep(self, freq=1000, duration=0.1, pause=0.05):
        """Single beep with optional pause after."""
        self.tone(freq, duration)
        if pause > 0:
            time.sleep(pause)

    def dot(self, freq=1000):
        """Morse code dot."""
        self.beep(freq, duration=0.1, pause=0.1)

    def dash(self, freq=1000):
        """Morse code dash."""
        self.beep(freq, duration=0.3, pause=0.1)

    def play_notes(self, notes):
        """Play a sequence of (freq, duration) tuples. Use freq=0 for silence."""
        for freq, duration in notes:
            if freq == 0:
                time.sleep(duration)
            else:
                self.tone(freq, duration)

    def deinit(self):
        """Release PWM resource."""
        self.pwm.deinit()
