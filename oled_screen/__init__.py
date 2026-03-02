from machine import Pin, I2C
import ssd1306
import time


class OLEDScreen:
    """OLED (SSD1306 128x32) adapter with the same API as ScreenLibrary.

    Coordinates are scaled from the TFT's 240x240 space so existing game
    code works without changes.

    Buttons are not available — they are part of the TFT hat which is not
    connected when this adapter is active. All button methods return False.
    """

    def __init__(self):
        self.width = 128
        self.height = 32

        # Monochrome — map all colours to on/off
        self.BLACK = 0
        self.WHITE = 1
        self.GRAY = 1
        self.RED = 1
        self.GREEN = 1
        self.BLUE = 1
        self.YELLOW = 1
        self.CYAN = 1
        self.MAGENTA = 1

        self._auto_update = True

        i2c = I2C(1, sda=Pin(18), scl=Pin(19), freq=400000)
        self._display = ssd1306.SSD1306_I2C(128, 32, i2c)

        self.Clear()

    # -- coordinate scaling --------------------------------------------------

    def _sx(self, x):
        return min(127, int(x * 128 // 240))

    def _sy(self, y):
        return min(31, int(y * 32 // 240))

    def _show(self):
        self._display.show()

    # -- buttons (not available without TFT hat) -----------------------------

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

    # -- display -------------------------------------------------------------

    def Write(self, text, x=10, y=10, color=None):
        self._display.text(text, self._sx(x), self._sy(y), 1)
        if self._auto_update:
            self._show()

    def Clear(self, color=None):
        self._display.fill(0)
        if self._auto_update:
            self._show()

    def SetPixel(self, x, y, color):
        self._display.pixel(self._sx(x), self._sy(y), 1 if color else 0)
        if self._auto_update:
            self._show()

    def DrawLine(self, x1, y1, x2, y2, color):
        self._display.line(self._sx(x1), self._sy(y1), self._sx(x2), self._sy(y2), 1 if color else 0)
        if self._auto_update:
            self._show()

    def DrawRect(self, x, y, width, height, color, filled=False):
        w = max(1, self._sx(width))
        h = max(1, self._sy(height) if height > 0 else 1)
        if filled:
            self._display.fill_rect(self._sx(x), self._sy(y), w, h, 1 if color else 0)
        else:
            self._display.rect(self._sx(x), self._sy(y), w, h, 1 if color else 0)
        if self._auto_update:
            self._show()

    def DrawCircle(self, x, y, radius, color):
        sx, sy = self._sx(x), self._sy(y)
        sr = max(1, self._sx(radius))
        for i in range(-sr, sr + 1):
            for j in range(-sr, sr + 1):
                if i * i + j * j <= sr * sr:
                    px, py = sx + i, sy + j
                    if 0 <= px < 128 and 0 <= py < 32:
                        self._display.pixel(px, py, 1)
        if self._auto_update:
            self._show()

    def DrawRawImage(self, path, x, y, width, height):
        pass  # Not supported on OLED

    def Update(self):
        self._show()

    def BeginDraw(self):
        self._auto_update = False

    def EndDraw(self):
        self._auto_update = True
        self._show()

    def SetBrightness(self, brightness):
        pass  # Not supported on SSD1306

    def Sleep(self, seconds):
        time.sleep(seconds)
