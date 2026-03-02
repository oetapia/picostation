from machine import Pin
import time

class GameControls:
    def __init__(self):
        # Initialize all buttons with pull-up resistors
        self.keyA = Pin(15, Pin.IN, Pin.PULL_UP)
        self.keyB = Pin(17, Pin.IN, Pin.PULL_UP)
        self.keyX = Pin(19, Pin.IN, Pin.PULL_UP)
        self.keyY = Pin(21, Pin.IN, Pin.PULL_UP)
        
        self.up = Pin(2, Pin.IN, Pin.PULL_UP)
        self.down = Pin(18, Pin.IN, Pin.PULL_UP)
        self.left = Pin(16, Pin.IN, Pin.PULL_UP)
        self.right = Pin(20, Pin.IN, Pin.PULL_UP)
        self.ctrl = Pin(3, Pin.IN, Pin.PULL_UP)
        
        # Button state tracking for debouncing
        self.last_press_time = {}
        self.debounce_time = 0.1  # 100ms debounce
        
    def is_pressed(self, button):
        """Check if a button is currently pressed (active low)"""
        return button.value() == 0
    
    def was_pressed(self, button_name):
        """Check if button was just pressed (with debouncing)"""
        button = getattr(self, button_name)
        current_time = time.ticks_ms()
        
        if self.is_pressed(button):
            if button_name not in self.last_press_time:
                self.last_press_time[button_name] = current_time
                return True
            elif time.ticks_diff(current_time, self.last_press_time[button_name]) > self.debounce_time * 1000:
                self.last_press_time[button_name] = current_time
                return True
        else:
            # Button released, clear the press time
            if button_name in self.last_press_time:
                del self.last_press_time[button_name]
        
        return False
    
    def get_current_state(self):
        """Get current state of all buttons"""
        return {
            'keyA': self.is_pressed(self.keyA),
            'keyB': self.is_pressed(self.keyB),
            'keyX': self.is_pressed(self.keyX),
            'keyY': self.is_pressed(self.keyY),
            'up': self.is_pressed(self.up),
            'down': self.is_pressed(self.down),
            'left': self.is_pressed(self.left),
            'right': self.is_pressed(self.right),
            'ctrl': self.is_pressed(self.ctrl)
        }
    
    def get_direction(self):
        """Get directional input as tuple (x, y) where -1, 0, 1"""
        x = 0
        y = 0
        
        if self.is_pressed(self.left):
            x = -1
        elif self.is_pressed(self.right):
            x = 1
            
        if self.is_pressed(self.up):
            y = -1
        elif self.is_pressed(self.down):
            y = 1
            
        return (x, y)
    
    def any_button_pressed(self):
        """Check if any button is currently pressed"""
        buttons = [self.keyA, self.keyB, self.keyX, self.keyY,
                  self.up, self.down, self.left, self.right, self.ctrl]
        return any(self.is_pressed(button) for button in buttons)
    
    def wait_for_button_release(self):
        """Wait until all buttons are released"""
        while self.any_button_pressed():
            time.sleep(0.01)
    
    def wait_for_button_press(self):
        """Wait for any button to be pressed"""
        while not self.any_button_pressed():
            time.sleep(0.01)