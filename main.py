import time
import urequests
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

class GameMenu:
    def __init__(self):
        self.selected_game = 0
        self.last_drawn = -1  # Track what was last drawn
        self.games = [
            {"name": "SPACE INVADERS", "description": "Shoot the aliens!"},
            {"name": "MUSIC PLAYER", "description": "Volumio controls"},
            {"name": "WEATHER", "description": "City weather"},
            {"name": "SNAKE", "description": "Classic snake game"}
        ]
        
    def draw(self, force_redraw=False):
        """Draw menu only when selection changes"""
        if not force_redraw and self.selected_game == self.last_drawn:
            return  # No change needed
            
        Screen.Clear()
        Screen.Write("ARCADE GAMES", 65, 20, Screen.YELLOW)
        Screen.DrawLine(65, 35, 175, 35, Screen.YELLOW)
        
        start_y = 55
        item_height = 30
        
        for i, game in enumerate(self.games):
            y_pos = start_y + (i * item_height)
            
            if i == self.selected_game:
                Screen.Write(">", 10, y_pos, Screen.BLUE)
                name_color = Screen.WHITE
                desc_color = Screen.WHITE
            else:
                name_color = Screen.WHITE
                desc_color = Screen.GREEN
            
            Screen.Write(game["name"], 25, y_pos, name_color)
            Screen.Write(game["description"], 25, y_pos + 10, desc_color)
        
        Screen.Write("UP/DOWN: Select", 10, 220, Screen.CYAN)
        Screen.Write("B: Start Game", 130, 220, Screen.CYAN)
        
        self.last_drawn = self.selected_game
    
    def handle_input(self):
        if Screen.Up():
            self.selected_game = (self.selected_game - 1) % len(self.games)
            Screen.Sleep(0.15)
            return "selection_changed"
        elif Screen.Down():
            self.selected_game = (self.selected_game + 1) % len(self.games)
            Screen.Sleep(0.15)
            return "selection_changed"
        elif Screen.ButtonB():
            Screen.Sleep(0.2)
            return self.launch_selected_game()
        return None
    
    def launch_selected_game(self):
        selected = self.games[self.selected_game]
        
        if selected["name"] == "SPACE INVADERS":
            launch_space_invaders()  # <- No arguments
            return "game_launched"
        elif selected["name"] == "MUSIC PLAYER":
            launch_volumio()
            return "game_launched"
        elif selected["name"] == "WEATHER":
            launch_weather()
            return "game_launched"
        elif selected["name"] == "SNAKE":
            launch_snake()
            return "game_launched"
        return None

# Placeholder Volumio and Snake launch functions
def launch_volumio():
    Screen.Clear()
    Screen.Write("Launching Volumio...", 40, 100, Screen.YELLOW)
    from volumio3 import VolumioGame
    game = VolumioGame()
    game.run()
    Screen.Sleep(1)


def launch_weather():
    Screen.Clear()
    Screen.Write("Launching Weather...", 40, 100, Screen.YELLOW)
    from weather import WeatherGame
    game = WeatherGame()
    game.run()
    Screen.Sleep(1)


def launch_space_invaders():
    from space_invaders import SpaceInvadersGame
    game = SpaceInvadersGame()
    game.run()

def launch_snake():
    from snake import SnakeGame
    game = SnakeGame()
    game.run()

def show_startup():
    Screen.Clear()
    title = "ARCADE GAMES"
    for i in range(len(title) + 1):
        Screen.Clear()
        Screen.Write(title[:i], 65, 100, Screen.YELLOW)
        Screen.Sleep(0.08)
    Screen.Sleep(0.5)

def main():
    show_startup()
    menu = GameMenu()
    menu.draw(force_redraw=True)
    
    while True:
        result = menu.handle_input()
        if result == "selection_changed":
            menu.draw()
        elif result == "game_launched":
            menu.draw(force_redraw=True)
        Screen.Sleep(0.02)

if __name__ == "__main__":
    main()
