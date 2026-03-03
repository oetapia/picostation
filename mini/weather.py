"""
mini/weather.py — compact weather display for the OLED (SSD1306 128x32).

Cycles through cities every 10 seconds automatically.
Weather data is refreshed every 5 minutes per city.

Layout (16 chars × 4 rows at 8px each):
  row 0  City name
  row 1  Temp + condition (truncated)
  row 2  Local time
  row 3  City index indicator
"""

import time
import urequests
from oled_screen import OLEDScreen
from breadboard.buttons import GameControls

try:
    import wifi
    import config
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

# Cities to cycle through
CITIES = ["Berlin", "Quito", "Seoul", "Madrid", "Raleigh", "NYC", "Bali"]

CITY_SWITCH_INTERVAL = 18   # seconds between city switches
WEATHER_REFRESH      = 300  # seconds between API calls per city


def _trunc(text, n):
    return text[:n] if len(text) <= n else text[:n - 1] + "~"


def _scroll(text, n, offset):
    """Return an n-char window into text, scrolling if text is longer than n."""
    if len(text) <= n:
        return text
    padded = text + "   "  # gap before repeat
    start = offset % len(padded)
    doubled = padded + padded
    return doubled[start:start + n]


class MiniWeather:
    def __init__(self):
        # Use oled_screen for display init; access raw ssd1306 for native coords
        self.oled = OLEDScreen()._display
        self.api_key = config.WEATHER_API_KEY
        self.base_url = "http://api.weatherapi.com/v1/current.json"

        self.city_index = 0
        # Cache: city → {temp_c, condition, local_time, fetched_at}
        self.cache = {}

        self.last_switch = time.time()
        self.scroll_offset = 0
        self.connected = False
        self.controls = GameControls()

        self._show_msg("Connecting...")
        if WIFI_AVAILABLE:
            self.connected = wifi.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD)

        if self.connected:
            self._fetch(self.current_city())
        else:
            self._show_msg("No WiFi")
            time.sleep(3)

    # ------------------------------------------------------------------ utils

    def current_city(self):
        return CITIES[self.city_index]

    def _show_msg(self, msg):
        self.oled.fill(0)
        self.oled.text(_trunc(msg, 16), 0, 12)
        self.oled.show()

    # ----------------------------------------------------------------- fetch

    def _fetch(self, city):
        url = f"{self.base_url}?key={self.api_key}&q={city}&aqi=no"
        try:
            r = urequests.get(url)
            if r.status_code == 200:
                data = r.json()
                r.close()
                self.cache[city] = {
                    "temp_c":      data["current"]["temp_c"],
                    "condition":   data["current"]["condition"]["text"],
                    "local_time":  data["location"]["localtime"],  # "2024-03-01 14:30"
                    "feelslike_c": data["current"]["feelslike_c"],
                    "wind_kph":    data["current"]["wind_kph"],
                    "humidity":    data["current"]["humidity"],
                    "fetched_at":  time.time(),
                }
            else:
                r.close()
                print(f"Weather API error {r.status_code} for {city}")
        except Exception as e:
            print(f"Fetch error for {city}:", e)

    def _maybe_refresh(self, city):
        entry = self.cache.get(city)
        if entry is None or time.time() - entry["fetched_at"] >= WEATHER_REFRESH:
            self._fetch(city)

    # ------------------------------------------------------------------ draw

    def draw(self):
        city = self.current_city()
        entry = self.cache.get(city)

        self.oled.fill(0)

        if entry is None:
            # Still loading
            self.oled.text(_trunc(city, 16), 0, 0)
            self.oled.text("Loading...", 0, 12)
        else:
            temp      = entry["temp_c"]
            condition = entry["condition"]
            loc_time  = entry["local_time"]
            feels_like = entry["feelslike_c"]
            wind_kph = entry["wind_kph"]
            humidity = entry["humidity"]

            # Row 0 — city name + local time
            time_str = loc_time.split(" ")[1][:5] if " " in loc_time else loc_time[:5]
            self.oled.text(_trunc(city.upper() + " " + time_str, 16), 0, 0)

            # Row 1 — temp + condition (scrolls if condition is long)
            temp_str = f"{temp}C ({feels_like}C)"
            row1 = f" {temp_str}"
            self.oled.text(_scroll(row1, 16, self.scroll_offset), 0, 10)

            # Row 2 — feels like, wind, humidity (scrolls if too long)
            row2 = f" {condition} W:{wind_kph}kph H:{humidity}%"
            self.oled.text(_scroll(row2, 16, self.scroll_offset), 0, 20)

            # Row 3 — city indicator dots (compact, no truncation needed for 7 cities)
            #dots = "".join("*" if i == self.city_index else "." for i in range(len(CITIES)))
            #self.oled.text(dots, 0, 24)

        self.scroll_offset += 1
        self.oled.show()

    # ------------------------------------------------------------------- run

    def _switch_city(self, delta):
        self.city_index = (self.city_index + delta) % len(CITIES)
        self.scroll_offset = 0
        self._maybe_refresh(self.current_city())

    def run(self):
        while True:
            city = self.current_city()
            self._maybe_refresh(city)
            self.scroll_offset = 0

            # Redraw every second; buttons override auto-advance
            for _ in range(CITY_SWITCH_INTERVAL):
                self.draw()
                if self.controls.was_pressed("down"):
                    self._switch_city(1)
                    break
                if self.controls.was_pressed("up"):
                    self._switch_city(-1)
                    break
                time.sleep(1)
            else:
                # Auto-advance only if no button was pressed
                self.city_index = (self.city_index + 1) % len(CITIES)


def run():
    MiniWeather().run()
