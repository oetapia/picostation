# APP: RC6 SNIFF
import time
from machine import Pin
from oled_screen import OLEDScreen
from breadboard.leds import LEDs


class RC6Decoder:
    """RC-6 decoder for active-LOW demodulators (e.g. HW-477).

    Supports mode 0 (8-bit addr + 8-bit cmd) and
    mode 6 extended (16-bit customer code + 8-bit cmd, used by Xbox remotes).
    """
    T            = 444   # half-bit period in µs
    LEADER_MARK  = 2666  # 6T
    LEADER_SPACE = 889   # 2T
    TOL          = 0.45  # timing tolerance

    def __init__(self, pin_num):
        self._pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self._edges = []
        self._last_time = 0
        self._pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING,
                      handler=self._isr)
        self.mode     = None
        self.toggle   = None
        self.address  = None
        self.command  = None
        self.received = False
        self._decoded_at = 0

    def _isr(self, pin):
        now = time.ticks_us()
        self._edges.append((pin.value(), time.ticks_diff(now, self._last_time)))
        self._last_time = now

    @staticmethod
    def _near(val, target, tol):
        return abs(val - target) < target * tol

    def poll(self):
        """Call frequently from main loop. Returns True when a new frame is decoded."""
        if not self._edges:
            return False
        # Wait for end-of-frame silence (>5ms of no edges)
        if time.ticks_diff(time.ticks_us(), self._last_time) < 5000:
            return False
        # 200ms cooldown — absorbs the duplicate frame remotes often send
        if time.ticks_diff(time.ticks_us(), self._decoded_at) < 200_000:
            self._edges.clear()
            return False
        if len(self._edges) < 15:
            self._edges.clear()
            return False
        edges = self._edges[:]
        self._edges.clear()
        result = self._decode(edges)
        if result:
            self._decoded_at = time.ticks_us()
        return result

    def _decode(self, edges):
        T, TOL = self.T, self.TOL

        # edges[0]: idle gap (ignore)
        # edges[1]: HI ~2666µs — leader mark ends, pin goes HIGH
        # edges[2]: LO ~889µs  — leader space ends, pin goes LOW
        if len(edges) < 4:
            return False
        if not (edges[1][0] == 1 and self._near(edges[1][1], self.LEADER_MARK, TOL)):
            return False
        if not (edges[2][0] == 0 and self._near(edges[2][1], self.LEADER_SPACE, TOL)):
            return False

        # Expand each edge into T-unit half-bits.
        # Each entry (level, duration): pin was at (1-level) for 'duration' µs,
        # then transitioned to 'level'. Append the pre-transition level n times.
        half_bits = []
        for level, duration in edges[3:]:
            if self._near(duration, T, TOL):
                n = 1
            elif self._near(duration, 2 * T, TOL):
                n = 2
            elif self._near(duration, 3 * T, TOL):
                n = 3
            else:
                break
            half_bits.extend([1 - level] * n)

        # Manchester decode: bit 1 = mark-then-space = LOW-then-HIGH = [0, 1]
        #                    bit 0 = space-then-mark = HIGH-then-LOW  = [1, 0]
        # double=True uses 4 half-bits (toggle bit is encoded at 2T width)
        def read_bit(idx, double=False):
            w = 4 if double else 2
            if idx + w > len(half_bits):
                raise IndexError
            h = w // 2
            first  = half_bits[idx:idx + h]
            second = half_bits[idx + h:idx + w]
            if first == [0] * h and second == [1] * h:
                return 1, idx + w
            if first == [1] * h and second == [0] * h:
                return 0, idx + w
            raise ValueError

        try:
            idx = 0

            # Start bit (always 1)
            s, idx = read_bit(idx)
            if s != 1:
                return False

            # Mode: 3 bits
            m0, idx = read_bit(idx)
            m1, idx = read_bit(idx)
            m2, idx = read_bit(idx)
            mode = (m0 << 2) | (m1 << 1) | m2

            # Toggle: double-width bit
            toggle, idx = read_bit(idx, double=True)

            # Remaining data bits
            data_bits = []
            while idx + 1 < len(half_bits):
                b, idx = read_bit(idx)
                data_bits.append(b)

        except (IndexError, ValueError):
            return False

        if not data_bits:
            return False

        # Pack MSB-first into an integer
        value = 0
        for b in data_bits:
            value = (value << 1) | b

        n = len(data_bits)
        self.mode   = mode
        self.toggle = toggle

        if mode == 0 and n >= 16:
            self.address = (value >> 8) & 0xFF
            self.command = value & 0xFF
        elif mode == 6 and n >= 24:
            self.address = (value >> 8) & 0xFFFF
            self.command = value & 0xFF
        else:
            # Unknown mode — expose raw value
            self.address = (value >> 8) if n > 8 else 0
            self.command = value & 0xFF

        self.received = True
        return True


def run():
    oled = OLEDScreen()._display
    leds = LEDs()
    ir = RC6Decoder(pin_num=12)

    MAX_ROWS = 8   # 64px / 8px per glyph
    history  = []  # display strings, newest first

    def draw():
        oled.fill(0)
        if not history:
            oled.text("Waiting RC6...", 0, 0)
        else:
            for i, line in enumerate(history[:MAX_ROWS]):
                oled.text(line, 0, i * 8)
        oled.show()

    draw()
    print("RC6 sniffer ready on GP12. Press a button...")

    while True:
        if ir.poll():
            leds.blink('green', times=1, interval=0.05)

            m = ir.mode    if ir.mode    is not None else -1
            t = ir.toggle  if ir.toggle  is not None else -1
            a = ir.address if ir.address is not None else 0
            c = ir.command if ir.command is not None else 0

            # Serial: easy to copy-paste for building a JSON profile
            print("RC6 mode={} toggle={} addr=0x{:04X} cmd=0x{:02X}".format(m, t, a, c))

            # OLED: two compact lines per entry (fits 16 chars each at 8px)
            line1 = "M{} T{} A:{:04X}".format(m, t, a)
            line2 = "       C:{:02X}".format(c)
            history.insert(0, line2)
            history.insert(0, line1)
            if len(history) > MAX_ROWS:
                history = history[:MAX_ROWS]

            ir.received = False
            draw()

        time.sleep_ms(5)
