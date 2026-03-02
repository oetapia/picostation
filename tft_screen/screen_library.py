from machine import Pin, SPI, PWM
import framebuf
import time

# Pin definitions
BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

class ScreenLibrary:
    def __init__(self):
        # Initialize LCD
        self.width = 240
        self.height = 240
        
        self.cs = Pin(CS, Pin.OUT)
        self.rst = Pin(RST, Pin.OUT)
        
        self.cs(1)
        self.spi = SPI(1, 100000_000, polarity=0, phase=0, sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
        self.dc = Pin(DC, Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width * 2)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.RGB565)
        
        # Initialize display
        self._init_display()
        
        # Initialize backlight
        self.pwm = PWM(Pin(BL))
        self.pwm.freq(1000)
        self.pwm.duty_u16(32768)  # 50% brightness
        
        # Colors (fixed RGB565 values)
        self.BLACK = 0x0000
        self.WHITE = 0xFFFF
        self.GRAY = 0xef5d
        self.RED = 0xF800
        self.GREEN = 0x6666
        self.BLUE = 0x001F
        self.YELLOW = 0xFFE0
        self.CYAN = 0x07FF
        self.MAGENTA = 0xF81F
        
        # Initialize buttons
        self.keyA = Pin(15, Pin.IN, Pin.PULL_UP)
        self.keyB = Pin(17, Pin.IN, Pin.PULL_UP)
        self.keyX = Pin(19, Pin.IN, Pin.PULL_UP)
        self.keyY = Pin(21, Pin.IN, Pin.PULL_UP)
        
        self.up = Pin(2, Pin.IN, Pin.PULL_UP)
        self.down = Pin(18, Pin.IN, Pin.PULL_UP)
        self.left = Pin(16, Pin.IN, Pin.PULL_UP)
        self.right = Pin(20, Pin.IN, Pin.PULL_UP)
        self.ctrl = Pin(3, Pin.IN, Pin.PULL_UP)
        
        # Button state tracking for better debouncing
        self.button_states = {
            'keyA': False, 'keyB': False, 'keyX': False, 'keyY': False,
            'up': False, 'down': False, 'left': False, 'right': False, 'ctrl': False
        }
        
        # Auto-update flag - when False, you need to call Update() manually
        self.auto_update = True
        
        # Clear screen
        self.Clear()
    
    def _write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def _write_data(self, data):
        """Send single byte or bytes-like object to display"""
        self.cs.value(0)
        self.dc.value(1)
        if isinstance(data, int):
            self.spi.write(bytearray([data]))
        else:
            self.spi.write(data)
        self.cs.value(1)

    def _init_display(self):
        """Initialize display"""  
        self.rst(1)
        self.rst(0)
        self.rst(1)
        
        self._write_cmd(0x36)
        self._write_data(0x70)

        self._write_cmd(0x3A) 
        self._write_data(0x05)

        self._write_cmd(0xB2)
        self._write_data(0x0C)
        self._write_data(0x0C)
        self._write_data(0x00)
        self._write_data(0x33)
        self._write_data(0x33)

        self._write_cmd(0xB7)
        self._write_data(0x35) 

        self._write_cmd(0xBB)
        self._write_data(0x19)

        self._write_cmd(0xC0)
        self._write_data(0x2C)

        self._write_cmd(0xC2)
        self._write_data(0x01)

        self._write_cmd(0xC3)
        self._write_data(0x12)   

        self._write_cmd(0xC4)
        self._write_data(0x20)

        self._write_cmd(0xC6)
        self._write_data(0x0F) 

        self._write_cmd(0xD0)
        self._write_data(0xA4)
        self._write_data(0xA1)

        self._write_cmd(0xE0)
        self._write_data(0xD0)
        self._write_data(0x04)
        self._write_data(0x0D)
        self._write_data(0x11)
        self._write_data(0x13)
        self._write_data(0x2B)
        self._write_data(0x3F)
        self._write_data(0x54)
        self._write_data(0x4C)
        self._write_data(0x18)
        self._write_data(0x0D)
        self._write_data(0x0B)
        self._write_data(0x1F)
        self._write_data(0x23)

        self._write_cmd(0xE1)
        self._write_data(0xD0)
        self._write_data(0x04)
        self._write_data(0x0C)
        self._write_data(0x11)
        self._write_data(0x13)
        self._write_data(0x2C)
        self._write_data(0x3F)
        self._write_data(0x44)
        self._write_data(0x51)
        self._write_data(0x2F)
        self._write_data(0x1F)
        self._write_data(0x1F)
        self._write_data(0x20)
        self._write_data(0x23)
        
        self._write_cmd(0x21)
        self._write_cmd(0x11)
        self._write_cmd(0x29)

    def _show(self):
        """Update the display with current buffer"""
        self._write_cmd(0x2A)
        self._write_data(0x00)
        self._write_data(0x00)
        self._write_data(0x00)
        self._write_data(0xef)
        
        self._write_cmd(0x2B)
        self._write_data(0x00)
        self._write_data(0x00)
        self._write_data(0x00)
        self._write_data(0xEF)
        
        self._write_cmd(0x2C)
        
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)
    
    # Button methods with improved debouncing
    def ButtonA(self):
        """Check if button A is pressed (with debouncing)"""
        current = self.keyA.value() == 0
        if current and not self.button_states['keyA']:
            self.button_states['keyA'] = True
            return True
        elif not current:
            self.button_states['keyA'] = False
        return False
    
    def ButtonB(self):
        """Check if button B is pressed (with debouncing)"""
        current = self.keyB.value() == 0
        if current and not self.button_states['keyB']:
            self.button_states['keyB'] = True
            return True
        elif not current:
            self.button_states['keyB'] = False
        return False
    
    def ButtonX(self):
        """Check if button X is pressed (with debouncing)"""
        current = self.keyX.value() == 0
        if current and not self.button_states['keyX']:
            self.button_states['keyX'] = True
            return True
        elif not current:
            self.button_states['keyX'] = False
        return False
    
    def ButtonY(self):
        """Check if button Y is pressed (with debouncing)"""
        current = self.keyY.value() == 0
        if current and not self.button_states['keyY']:
            self.button_states['keyY'] = True
            return True
        elif not current:
            self.button_states['keyY'] = False
        return False
    
    # Directional pad methods with debouncing
    def Up(self):
        """Check if up button is pressed (with debouncing)"""
        current = self.up.value() == 0
        if current and not self.button_states['up']:
            self.button_states['up'] = True
            return True
        elif not current:
            self.button_states['up'] = False
        return False
    
    def Down(self):
        """Check if down button is pressed (with debouncing)"""
        current = self.down.value() == 0
        if current and not self.button_states['down']:
            self.button_states['down'] = True
            return True
        elif not current:
            self.button_states['down'] = False
        return False
    
    def Left(self):
        """Check if left button is pressed (with debouncing)"""
        current = self.left.value() == 0
        if current and not self.button_states['left']:
            self.button_states['left'] = True
            return True
        elif not current:
            self.button_states['left'] = False
        return False
    
    def Right(self):
        """Check if right button is pressed (with debouncing)"""
        current = self.right.value() == 0
        if current and not self.button_states['right']:
            self.button_states['right'] = True
            return True
        elif not current:
            self.button_states['right'] = False
        return False
    
    def Center(self):
        """Check if center/ctrl button is pressed (with debouncing)"""
        current = self.ctrl.value() == 0
        if current and not self.button_states['ctrl']:
            self.button_states['ctrl'] = True
            return True
        elif not current:
            self.button_states['ctrl'] = False
        return False
    
    # Raw button methods (no debouncing) for hold detection
    def ButtonA_Raw(self):
        return self.keyA.value() == 0
    
    def ButtonB_Raw(self):
        return self.keyB.value() == 0
    
    def ButtonX_Raw(self):
        return self.keyX.value() == 0
    
    def ButtonY_Raw(self):
        return self.keyY.value() == 0
    
    # Display methods - NOW WITH OPTIONAL AUTO-UPDATE
    def Write(self, text, x=10, y=10, color=None):
        """Write text to screen at specified position"""
        if color is None:
            color = self.WHITE
        self.framebuf.text(text, x, y, color)
        if self.auto_update:
            self._show()
    
    def Clear(self, color=None):
        """Clear the screen with specified color (default black)"""
        if color is None:
            color = self.BLACK
        self.framebuf.fill(color)
        if self.auto_update:
            self._show()
    
    def SetPixel(self, x, y, color):
        """Set a single pixel"""
        self.framebuf.pixel(x, y, color)
        if self.auto_update:
            self._show()
    
    def DrawLine(self, x1, y1, x2, y2, color):
        """Draw a line from (x1,y1) to (x2,y2)"""
        self.framebuf.line(x1, y1, x2, y2, color)
        if self.auto_update:
            self._show()
    
    def DrawRect(self, x, y, width, height, color, filled=False):
        """Draw a rectangle"""
        if filled:
            self.framebuf.fill_rect(x, y, width, height, color)
        else:
            self.framebuf.rect(x, y, width, height, color)
        if self.auto_update:
            self._show()
    
    def DrawCircle(self, x, y, radius, color):
        """Draw a circle (simple implementation using rectangles)"""
        # Simple circle using filled rectangles - basic implementation
        for i in range(-radius, radius + 1):
            for j in range(-radius, radius + 1):
                if i*i + j*j <= radius*radius:
                    if 0 <= x+i < self.width and 0 <= y+j < self.height:
                        self.framebuf.pixel(x+i, y+j, color)
        if self.auto_update:
            self._show()
    
    def DrawRawImage(self, path, x, y, width, height):
        """Draw raw RGB565 image from file at position x,y"""
        try:
            with open(path, "rb") as f:
                data = f.read()
            fb = framebuf.FrameBuffer(bytearray(data), width, height, framebuf.RGB565)
            self.framebuf.blit(fb, x, y)
            if self.auto_update:
                self._show()
        except Exception as e:
            print("DrawRawImage error:", e)
    
    
    def Update(self):
        """Manually update the display"""
        self._show()
    
    # Batch drawing mode for flicker-free multi-element drawing
    def BeginDraw(self):
        """Begin batch drawing mode (disable auto-update)"""
        self.auto_update = False
    
    def EndDraw(self):
        """End batch drawing mode and update display"""
        self.auto_update = True
        self._show()
    
    def SetBrightness(self, brightness):
        """Set screen brightness (0-100)"""
        duty = int((brightness / 100) * 65535)
        self.pwm.duty_u16(duty)
    
    def Sleep(self, seconds):
        """Convenience sleep method"""
        time.sleep(seconds)