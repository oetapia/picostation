from machine import SoftI2C, Pin

i2c = SoftI2C(sda=Pin(10), scl=Pin(11), freq=100_000)

devices = i2c.scan()
if devices:
    print("Found:", [hex(d) for d in devices])
else:
    print("No devices found")
