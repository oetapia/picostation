# APP: HW477 IR RX
import time
from machine import Pin
from oled_screen import OLEDScreen
from breadboard.leds import LEDs


# NEC protocol decoder
# HW-477 output is active-LOW: idles HIGH, pulses LOW when receiving IR
class NECDecoder:
    # Pulse width thresholds in microseconds
    LEADER_PULSE  = 9000
    LEADER_SPACE  = 4500
    REPEAT_SPACE  = 2250
    BIT_PULSE     =  560
    BIT_ONE_SPACE = 1690
    BIT_ZRO_SPACE =  560
    TOLERANCE     = 0.35  # 35%

    def __init__(self, pin_num):
        self._pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self._edges = []
        self._last_time = 0
        self._pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
                      handler=self._isr)
        self.address = None
        self.command = None
        self.repeat  = False
        self.received = False

    def _isr(self, pin):
        now = time.ticks_us()
        self._edges.append((pin.value(), time.ticks_diff(now, self._last_time)))
        self._last_time = now

    @staticmethod
    def _near(val, target, tol):
        return abs(val - target) < target * tol

    def poll(self):
        """Call frequently from main loop. Returns True if a new code arrived."""
        if len(self._edges) < 68:
            # Check for timeout — reset if we've been waiting too long mid-frame
            if self._edges and time.ticks_diff(time.ticks_us(), self._last_time) > 15000:
                self._edges.clear()
            return False

        edges = self._edges[:68]
        self._edges = self._edges[68:]

        T = self.TOLERANCE

        # edges[0] = (level after first falling edge, gap since last edge — ignore)
        # edges[1] = rising after leader pulse  → duration of leader LOW
        # edges[2] = falling after leader space → duration of leader HIGH space
        try:
            leader_pulse = edges[1][1]
            leader_space = edges[2][1]
        except IndexError:
            return False

        if not self._near(leader_pulse, self.LEADER_PULSE, T):
            return False

        if self._near(leader_space, self.REPEAT_SPACE, T):
            self.repeat   = True
            self.received = True
            return True

        if not self._near(leader_space, self.LEADER_SPACE, T):
            return False

        # Decode 32 bits: address, ~address, command, ~command
        bits = []
        # Each bit = falling edge (pulse) + rising edge (space)
        # edges[3..] carry the 32 data bits, each consuming 2 edges
        for i in range(32):
            idx = 3 + i * 2
            if idx + 1 >= len(edges):
                return False
            space = edges[idx + 1][1]
            if self._near(space, self.BIT_ONE_SPACE, T):
                bits.append(1)
            elif self._near(space, self.BIT_ZRO_SPACE, T):
                bits.append(0)
            else:
                return False

        def bits_to_byte(b):
            val = 0
            for bit in b:
                val = (val >> 1) | (bit << 7)
            return val

        addr     = bits_to_byte(bits[0:8])
        addr_inv = bits_to_byte(bits[8:16])
        cmd      = bits_to_byte(bits[16:24])
        cmd_inv  = bits_to_byte(bits[24:32])

        if (addr ^ addr_inv) != 0xFF or (cmd ^ cmd_inv) != 0xFF:
            return False  # checksum mismatch

        self.address  = addr
        self.command  = cmd
        self.repeat   = False
        self.received = True
        return True


def run_sniffer(pin_num=12):
    """Raw pulse sniffer — prints edge durations to serial for protocol identification."""
    pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
    edges = []
    last_us = [0]

    def _isr(p):
        now = time.ticks_us()
        edges.append((p.value(), time.ticks_diff(now, last_us[0])))
        last_us[0] = now

    pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_isr)
    print("IR sniffer ready on GP{}. Press a button on the remote...".format(pin_num))

    while True:
        time.sleep_ms(20)
        if not edges:
            continue
        # Check if the frame has ended (no new edge for > 15ms)
        if time.ticks_diff(time.ticks_us(), last_us[0]) < 15000:
            continue

        frame = edges[:]
        edges.clear()
        print("--- frame ({} edges) ---".format(len(frame)))
        for i, (level, width) in enumerate(frame):
            print("  [{}] {} {}us".format(i, "LO" if level == 0 else "HI", width))



def run():
    oled = OLEDScreen()._display
    leds = LEDs()

    ir = NECDecoder(pin_num=12)

    MAX_ROWS = 7  # 64px / 8px per line — but first row reserved for "Waiting..."
    history = []  # list of strings, newest first

    def draw():
        oled.fill(0)
        if not history:
            oled.text("Waiting...", 0, 0)
        else:
            for i, line in enumerate(history[:MAX_ROWS]):
                oled.text(line, 0, i * 8)
        oled.show()

    draw()

    while True:
        if ir.poll():
            leds.blink('green', times=1, interval=0.05)
            if ir.repeat:
                # Mark last entry as repeated instead of adding a duplicate
                if history:
                    history[0] = history[0].rstrip("*") + "*"
            else:
                entry = "A:{:02X} C:{:02X}".format(ir.address, ir.command)
                history.insert(0, entry)
                if len(history) > MAX_ROWS:
                    history.pop()
            ir.received = False
            draw()

        time.sleep(0.01)
