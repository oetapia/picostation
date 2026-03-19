import machine
import time
from oled_screen import OLEDScreen
from vl53l0x_mp import VL53L0X, VL53L0XError

SDA_PIN = 8
SCL_PIN = 9
I2C_FREQ = 100_000


def run():
    oled = OLEDScreen()._display

    oled.fill(0)
    oled.text("VL53L0X", 0, 0)
    oled.text("Initializing...", 0, 10)
    oled.show()

    i2c = machine.SoftI2C(sda=machine.Pin(SDA_PIN),
                          scl=machine.Pin(SCL_PIN),
                          freq=I2C_FREQ)

    try:
        tof = VL53L0X(i2c)
        tof.init()
    except VL53L0XError as e:
        oled.fill(0)
        oled.text("Init error", 0, 0)
        oled.text(str(e)[:16], 0, 10)
        oled.show()
        print("TOF init error:", e)
        return
    except Exception as e:
        oled.fill(0)
        oled.text("I2C error", 0, 0)
        oled.text(str(e)[:16], 0, 10)
        oled.show()
        print("TOF error:", e)
        return

    while True:
        try:
            dist_mm = tof.read_mm()
            oled.fill(0)
            oled.text("VL53L0X", 0, 0)
            if dist_mm is None:
                oled.text("Out of range", 0, 10)
                oled.text("", 0, 20)
            else:
                dist_cm = dist_mm / 10.0
                oled.text(f"{dist_mm} mm", 0, 10)
                oled.text(f"{dist_cm:.1f} cm", 0, 20)
            oled.show()
        except Exception as e:
            oled.fill(0)
            oled.text("Read error", 0, 10)
            oled.show()
            print("TOF read error:", e)
        time.sleep_ms(100)
