from machine import SoftI2C, Pin
import ssd1306

PCA9548A_ADDR = 0x70

i2c = SoftI2C(sda=Pin(10, pull=Pin.PULL_UP), scl=Pin(11, pull=Pin.PULL_UP), freq=50_000)

# Enable mux channel 3 (SD3/SC3)
i2c.writeto(PCA9548A_ADDR, bytes([1 << 3]))

oled = ssd1306.SSD1306_I2C(128, 64, i2c)
oled.fill(0)
oled.text("Hello World!", 0, 10)
oled.show()
