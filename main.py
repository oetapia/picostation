import os
import machine
from screen import Screen

# Initialize LED
led = machine.Pin("LED", machine.Pin.OUT)
led.off()


def _discover_apps():
    """Discover apps from apps/*.py by reading the `# APP: NAME` header line."""
    apps = []
    try:
        for fname in sorted(os.listdir("apps")):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            try:
                with open("apps/" + fname) as fp:
                    line = fp.readline().strip()
                if line.startswith("# APP:"):
                    apps.append((line[6:].strip(), fname[:-3]))
            except OSError:
                pass
    except OSError:
        pass
    return apps  # [(label, module_stem), ...]


APPS = _discover_apps()


class GameMenu:
    def __init__(self):
        self.selected = 0
        self.last_drawn = -1
        self.apps = APPS

    def draw(self, force_redraw=False):
        if not force_redraw and self.selected == self.last_drawn:
            return

        Screen.Clear()
        Screen.Write("Apps", 65, 20, Screen.YELLOW)
        Screen.DrawLine(65, 35, 175, 35, Screen.YELLOW)

        if not self.apps:
            Screen.Write("No apps installed", 30, 110, Screen.RED)
            self.last_drawn = self.selected
            return

        start_y = 55
        item_height = 20
        for i, (label, _stem) in enumerate(self.apps):
            y_pos = start_y + (i * item_height)
            if i == self.selected:
                Screen.Write(">", 10, y_pos, Screen.BLUE)
            Screen.Write(label, 25, y_pos, Screen.WHITE)

        Screen.Write("UP/DOWN: Select", 10, 220, Screen.CYAN)
        Screen.Write("B: Start App", 130, 220, Screen.CYAN)

        self.last_drawn = self.selected

    def handle_input(self):
        if not self.apps:
            return None
        if Screen.Up():
            self.selected = (self.selected - 1) % len(self.apps)
            Screen.Sleep(0.15)
            return "selection_changed"
        elif Screen.Down():
            self.selected = (self.selected + 1) % len(self.apps)
            Screen.Sleep(0.15)
            return "selection_changed"
        elif Screen.ButtonB():
            Screen.Sleep(0.2)
            self.launch_selected()
            return "game_launched"
        return None

    def launch_selected(self):
        _label, stem = self.apps[self.selected]
        Screen.Clear()
        mod = __import__("apps." + stem, None, None, ["run"])
        mod.run()


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
