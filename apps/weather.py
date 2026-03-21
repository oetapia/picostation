import urequests
import time
import json
import machine
from screen import Screen

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

class WeatherGame:
    def __init__(self):
        self.api_key = config.WEATHER_API_KEY
        self.cities = ["Berlin", "Quito", "Seoul", "Madrid", "Raleigh","NYC","Bali"]
        self.city_index = 0
        self.city = self.cities[self.city_index]
        self.base_url = "http://api.weatherapi.com/v1/current.json"
        
        # Weather data
        self.condition = "Loading..."
        self.temp_c = "--"
        self.feels_like = "--"
        self.wind_kph = "--"
        self.humidity = "--"
        self.last_updated = "Never"
        self.icon_id = None  # << added
        self.icon_path = None
        
        self.last_weather_update = time.time()
        self.weather_update_interval = 300  # Update every 5 minutes (300 seconds)
        self.connected = False
        self.error_message = ""
        self.needs_redraw = True
        
        # Connect to WiFi
        if WIFI_AVAILABLE:
            self.connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)
            if self.connected:
                self.get_weather()
        else:
            self.error_message = "WiFi not available"
    
    def get_weather(self):
        """Fetch current weather from API"""
        url = f"{self.base_url}?key={self.api_key}&q={self.city}&aqi=no"
        
        try:
            response = urequests.get(url)
            
            if response.status_code == 200:
                result = response.json()
                response.close()
                
                old_temp = self.temp_c
                old_condition = self.condition
                
                # Update weather data
                self.condition = result["current"]["condition"]["text"]
                self.temp_c = result["current"]["temp_c"]
                self.feels_like = result["current"]["feelslike_c"]
                self.wind_kph = result["current"]["wind_kph"]
                self.humidity = result["current"]["humidity"]
                self.last_updated = result["current"]["last_updated"]
                self.time = result["location"]["localtime"]

                # Extract icon id (e.g. //cdn.../326.png → 326)
                icon_url = result["current"]["condition"]["icon"]
                self.icon_id = icon_url.split('/')[-1].split('.')[0]
                self.icon_path = f"/icons_rgb565/{self.icon_id}.raw"

                # Check if anything changed
                if old_temp != self.temp_c or old_condition != self.condition:
                    self.needs_redraw = True
                
                self.error_message = ""
                print(f"Weather in {self.city}: {self.condition}, {self.temp_c}°C, icon {self.icon_id}")
                
            else:
                print(f"Failed to get weather. Status code: {response.status_code}")
                self.error_message = f"API Error: {response.status_code}"
                self.needs_redraw = True
                response.close()
                
        except Exception as e:
            print('Error getting weather:', e)
            if self.error_message != "Failed to fetch weather":
                self.error_message = "Failed to fetch weather"
                self.needs_redraw = True
    
    def handle_input(self):
        if Screen.ButtonB():
            self.get_weather()
            Screen.Sleep(0.3)
        
        elif Screen.Down():
            # Cycle to next city
            self.city_index = (self.city_index + 1) % len(self.cities)
            self.city = self.cities[self.city_index]
            self.get_weather()
            Screen.Sleep(0.3)

        elif Screen.Up():
            # Cycle to next city
            self.city_index = (self.city_index - 1) % len(self.cities)
            self.city = self.cities[self.city_index]
            self.get_weather()
            Screen.Sleep(0.3)
            
        elif Screen.ButtonX():
            return "exit"
        
        return None
    
    def update(self):
        current_time = time.time()
        if current_time - self.last_weather_update >= self.weather_update_interval:
            self.get_weather()
            self.last_weather_update = current_time
    
    def draw(self):
        if not self.needs_redraw:
            return
        
        Screen.Clear()
        
        if not self.connected:
            Screen.Write("WEATHER", 80, 20, Screen.YELLOW)
            Screen.Write("Not Connected", 60, 100, Screen.RED)
            Screen.Write(self.error_message, 20, 120, Screen.RED)
            Screen.Write("X: Back to Menu", 50, 200, Screen.CYAN)
            self.needs_redraw = False
            return
        
        # Header
        Screen.Write("WEATHER", 80, 10, Screen.YELLOW)
        Screen.DrawLine(10, 25, 230, 25, Screen.YELLOW)
        
        # City name
        Screen.Write(self.city, 10, 35, Screen.WHITE)
        
        # Main temperature
        temp_text = f"{self.temp_c} C"
        Screen.Write(temp_text, 10, 60, Screen.GREEN)

        # Condition
        Screen.Write(self.truncate_text(self.condition, 30), 10, 90, Screen.CYAN)

        # --- NEW: Draw weather icon ---
        if self.icon_path:
            try:
                Screen.DrawRawImage(self.icon_path, 160, 40, 64, 64)
            except Exception as e:
                Screen.Write("[No Icon]", 160, 80, Screen.RED)
                print("Icon load error:", e)
        
        # Details
        Screen.Write("Feels like:", 10, 115, Screen.WHITE)
        Screen.Write(f"{self.feels_like} C", 120, 115, Screen.GRAY)
        
        Screen.Write("Wind:", 10, 135, Screen.WHITE)
        Screen.Write(f"{self.wind_kph} km/h", 120, 135, Screen.GREEN)
        
        Screen.Write("Humidity:", 10, 155, Screen.WHITE)
        Screen.Write(f"{self.humidity}%", 120, 155, Screen.WHITE)
        
        # Last updated
        #Screen.Write("Updated:", 10, 175, Screen.WHITE)
        Screen.Write("Local:", 10, 175, Screen.WHITE)
        time_only = self.last_updated.split()[1] if " " in str(self.last_updated) else "Never"
        local_time = self.time.split()[1] if " " in str(self.last_updated) else "Never"
        #Screen.Write(time_only, 90, 175, Screen.WHITE)
        Screen.Write(local_time, 120, 175, Screen.WHITE)
        
        # Error message
        if self.error_message:
            Screen.Write(self.error_message, 10, 195, Screen.RED)
        
        # Controls
        Screen.DrawLine(10, 205, 230, 205, Screen.CYAN)
        Screen.Write("B: Refresh", 10, 215, Screen.CYAN)
        Screen.Write("Down: City", 10, 225, Screen.CYAN)
        Screen.Write("X: Menu", 160, 215, Screen.CYAN)
        
        self.needs_redraw = False
    
    def truncate_text(self, text, max_length):
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text
    
    def run(self):
        self.needs_redraw = True
        
        while True:
            result = self.handle_input()
            if result == "exit":
                return
            
            self.update()
            self.draw()
            Screen.Sleep(0.1)

def launch_weather():
    game = WeatherGame()
    game.run()