# Import the screen library
from screen_library import Screen

# Example usage
Screen.Write("Hello World!", 50, 50, Screen.BLACK)
Screen.Write("Press buttons!", 50, 70, Screen.BLUE)

# Main loop
while True:
    # Check buttons and respond
    if Screen.ButtonA():
        Screen.Write("Button A pressed!", 10, 100, Screen.RED)
    
    if Screen.ButtonB():
        Screen.Write("Button B pressed!", 10, 120, Screen.GREEN)
    
    if Screen.ButtonX():
        Screen.DrawRect(100, 100, 50, 30, Screen.BLUE, filled=True)
    
    if Screen.ButtonY():
        Screen.DrawCircle(120, 180, 20, Screen.RED)
    
    # Directional controls
    if Screen.Up():
        Screen.Write("UP", 10, 10, Screen.BLACK)
    
    if Screen.Down():
        Screen.Write("DOWN", 10, 220, Screen.BLACK)
    
    if Screen.Left():
        Screen.Write("LEFT", 10, 115, Screen.BLACK)
    
    if Screen.Right():
        Screen.Write("RIGHT", 180, 115, Screen.BLACK)
    
    if Screen.Center():
        Screen.Clear()  # Clear screen when center is pressed
    
    Screen.Sleep(0.1)  # Small delay to prevent overwhelming the display