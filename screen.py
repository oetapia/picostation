"""
screen.py — auto-detects the connected display and exports a single Screen object.

Detection order:
  1. OLED (SSD1306, 128x32, I2C) — I2C scan is definitive; raises OSError if absent
  2. TFT (ST7789, 240x240, SPI)  — SPI is assumed if OLED not found (no way to probe)
  3. NullScreen (headless — buttons always return False)

OLED is probed first because SPI never raises an exception even when nothing is
connected, so TFT detection cannot be used as a reliable presence check.

All game/app files should import via:
    from screen import Screen
"""

import time


class _NullScreen:
    """No-op screen used when no display hardware is detected."""

    def __init__(self):
        self.width = 0
        self.height = 0
        self.BLACK = 0
        self.WHITE = 1
        self.GRAY = 1
        self.RED = 1
        self.GREEN = 1
        self.BLUE = 1
        self.YELLOW = 1
        self.CYAN = 1
        self.MAGENTA = 1

    def ButtonA(self): return False
    def ButtonB(self): return False
    def ButtonX(self): return False
    def ButtonY(self): return False
    def Up(self): return False
    def Down(self): return False
    def Left(self): return False
    def Right(self): return False
    def Center(self): return False
    def ButtonA_Raw(self): return False
    def ButtonB_Raw(self): return False
    def ButtonX_Raw(self): return False
    def ButtonY_Raw(self): return False

    def Write(self, text, x=10, y=10, color=None): pass
    def Clear(self, color=None): pass
    def SetPixel(self, x, y, color): pass
    def DrawLine(self, x1, y1, x2, y2, color): pass
    def DrawRect(self, x, y, width, height, color, filled=False): pass
    def DrawCircle(self, x, y, radius, color): pass
    def DrawRawImage(self, path, x, y, width, height): pass
    def Update(self): pass
    def BeginDraw(self): pass
    def EndDraw(self): pass
    def SetBrightness(self, brightness): pass
    def Sleep(self, seconds): time.sleep(seconds)


def _detect():
    # 1. OLED — I2C scan raises OSError if no device present, so this is reliable
    try:
        from oled_screen import OLEDScreen
        screen = OLEDScreen()
        print("Display: OLED 128x32")
        return screen
    except Exception as e:
        print("OLED not available:", e)

    # 2. TFT — SPI gives no feedback; assume connected if OLED wasn't found
    try:
        from tft_screen import ScreenLibrary
        screen = ScreenLibrary()
        print("Display: TFT 240x240")
        return screen
    except Exception as e:
        print("TFT not available:", e)

    # 3. Headless
    print("Display: none (headless)")
    return _NullScreen()


Screen = _detect()
