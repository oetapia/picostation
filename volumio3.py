import urequests
import time
import json
import machine
from screen_library import Screen

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False
    print("WiFi modules not available")

# Initialize LED
led = machine.Pin("LED", machine.Pin.OUT)
led.off()

class VolumioGame:
    def __init__(self):
        self.base_url = 'http://volumio.local/api/v1'
        self.song_title = 'Unknown Song'
        self.song_artist = 'Unknown Artist'
        self.song_album = 'Unknown Album'
        self.song_bitrate = 'Unknown'
        self.status = 'stop'
        self.last_status_update = time.time()
        self.status_update_interval = 5  # Update every 5 seconds
        self.connected = False
        self.error_message = ""
        self.needs_redraw = True  # Track if screen needs updating
        
        # Store previous state to detect changes
        self.prev_song_title = None
        self.prev_status = None
        self.prev_error = None
        
        # Connect to WiFi
        if WIFI_AVAILABLE:
            self.connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if self.connected:
                self.get_status()
        else:
            self.error_message = "WiFi not available"
    
    def send_command(self, command):
        """Send command to Volumio API"""
        url = f'{self.base_url}/commands/?cmd={command}'
        try:
            response = urequests.get(url)
            success = response.status_code == 200
            response.close()
            if success:
                print(f'Command sent: {command}')
                # Update status after command
                time.sleep(0.3)
                self.get_status()
            return success
        except Exception as e:
            print('Error sending command:', e)
            self.error_message = f"Command failed: {command}"
            self.needs_redraw = True
            return False
    
    def get_status(self):
        """Get current playback status from Volumio"""
        url = f"{self.base_url}/getState"
        try:
            response = urequests.get(url)
            result = response.json()
            response.close()
            
            # Store old values
            old_title = self.song_title
            old_status = self.status
            
            # Update song info
            self.song_title = result.get('title', 'Unknown Song')
            self.song_artist = result.get('artist', 'Unknown Artist')
            self.song_album = result.get('album', 'Unknown Album')
            self.song_bitrate = result.get('bitrate', 'Unknown')
            self.status = result.get('status', 'stop')
            
            # Check if anything changed
            if (old_title != self.song_title or 
                old_status != self.status or
                self.error_message != ""):
                self.needs_redraw = True
            
            self.error_message = ""
            print(f'Status: {self.status} - {self.song_title}')
            
        except Exception as e:
            print('Error getting status:', e)
            if self.error_message != "Failed to get status":
                self.error_message = "Failed to get status"
                self.needs_redraw = True
    
    def handle_input(self):
        """Handle button inputs"""
        if Screen.ButtonB():  # Play/Pause
            if self.status == 'play':
                self.send_command('pause')
            else:
                self.send_command('play')
            Screen.Sleep(0.3)
            
        elif Screen.Left():  # Previous track
            self.send_command('prev')
            Screen.Sleep(0.3)
            
        elif Screen.Right():  # Next track
            self.send_command('next')
            Screen.Sleep(0.3)
            
        elif Screen.Up():  # Volume up
            self.send_command('volume&volume=plus')
            Screen.Sleep(0.2)
            
        elif Screen.Down():  # Volume down
            self.send_command('volume&volume=minus')
            Screen.Sleep(0.2)
            
        elif Screen.ButtonX():  # Exit to menu
            return "exit"
        
        return None
    
    def update(self):
        """Update status periodically"""
        current_time = time.time()
        if current_time - self.last_status_update >= self.status_update_interval:
            self.get_status()
            self.last_status_update = current_time
    
    def draw(self):
        """Draw the Volumio interface only when needed"""
        if not self.needs_redraw:
            return  # Skip drawing if nothing changed
        
        Screen.Clear()
        
        if not self.connected:
            Screen.Write("VOLUMIO PLAYER", 50, 20, Screen.YELLOW)
            Screen.Write("Not Connected", 60, 100, Screen.RED)
            Screen.Write(self.error_message, 20, 120, Screen.RED)
            Screen.Write("X: Back to Menu", 50, 200, Screen.CYAN)
            self.needs_redraw = False
            return
        
        # Header
        Screen.Write("VOLUMIO PLAYER", 50, 10, Screen.YELLOW)
        Screen.DrawLine(10, 25, 230, 25, Screen.YELLOW)
        
        # Status indicator
        status_color = Screen.GREEN if self.status == 'play' else Screen.RED
        status_text = "PLAYING" if self.status == 'play' else "PAUSED"
        Screen.Write(status_text, 10, 35, status_color)
        
        # Bitrate
        Screen.Write(f"{self.song_bitrate}", 180, 35, Screen.CYAN)
        
        # Song info
        Screen.Write("Title:", 10, 60, Screen.WHITE)
        Screen.Write(self.truncate_text(self.song_title, 25), 10, 75, Screen.GREEN)
        
        Screen.Write("Artist:", 10, 95, Screen.WHITE)
        Screen.Write(self.truncate_text(self.song_artist, 25), 10, 110, Screen.GREEN)
        
        Screen.Write("Album:", 10, 130, Screen.WHITE)
        Screen.Write(self.truncate_text(self.song_album, 25), 10, 145, Screen.GREEN)
        
        # Error message if any
        if self.error_message:
            Screen.Write(self.error_message, 10, 165, Screen.RED)
        
        # Controls
        Screen.DrawLine(10, 180, 230, 180, Screen.CYAN)
        Screen.Write("LEFT: Prev", 10, 190, Screen.CYAN)
        Screen.Write("RIGHT: Next", 10, 200, Screen.CYAN)
        Screen.Write("B: Play/Pause", 10, 210, Screen.CYAN)
        Screen.Write("UP/DOWN: Vol", 130, 190, Screen.CYAN)
        Screen.Write("X: Menu", 130, 210, Screen.CYAN)
        
        self.needs_redraw = False  # Reset flag after drawing
    
    def truncate_text(self, text, max_length):
        """Truncate text to fit screen"""
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text
    
    def run(self):
        """Main game loop"""
        self.needs_redraw = True  # Force initial draw
        
        while True:
            result = self.handle_input()
            
            if result == "exit":
                return
            
            self.update()
            self.draw()  # Only draws if needs_redraw is True
            Screen.Sleep(0.1)

def launch_volumio():
    game = VolumioGame()
    game.run()