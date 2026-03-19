from machine import SoftI2C, Pin
import time

PCA9548A_ADDR = 0x70  # default (A0=A1=A2=GND)

def mux_select(i2c, channel):
    """Enable one channel (0-7), or pass None to disable all."""
    mask = (1 << channel) if channel is not None else 0
    i2c.writeto(PCA9548A_ADDR, bytes([mask]))

i2c = SoftI2C(sda=Pin(10, pull=Pin.PULL_UP), scl=Pin(11, pull=Pin.PULL_UP), freq=50_000)

# --- Detect multiplexer ---
devices = i2c.scan()
print("I2C scan:", [hex(d) for d in devices])

if PCA9548A_ADDR not in devices:
    print(f"PCA9548A NOT found (expected {hex(PCA9548A_ADDR)})")
    print("Check wiring or address pins (A0/A1/A2)")
    raise SystemExit

print(f"PCA9548A detected at {hex(PCA9548A_ADDR)}")
time.sleep_ms(50)

# --- Scan all 8 channels ---
for ch in range(8):
    mux_select(i2c, ch)
    all_devices = i2c.scan()
    found = [hex(d) for d in all_devices if d != PCA9548A_ADDR]
    print(f"  Channel {ch}: {found if found else 'empty'} (raw: {[hex(d) for d in all_devices]})")

mux_select(i2c, None)  # disable all channels
