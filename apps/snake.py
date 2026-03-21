import random
from screen import Screen

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
BLOCK_SIZE = 10

class Snake:
    def __init__(self):
        self.body = [(100, 100), (90, 100), (80, 100)]
        self.direction = (BLOCK_SIZE, 0)  # starts moving right
        self.growing = False

    def move(self):
        head_x, head_y = self.body[0]
        delta_x, delta_y = self.direction
        new_head = (head_x + delta_x, head_y + delta_y)

        self.body = [new_head] + self.body
        if not self.growing:
            self.body.pop()
        else:
            self.growing = False

    def grow(self):
        self.growing = True

    def set_direction(self, direction):
        opposite = (-self.direction[0], -self.direction[1])
        if direction != opposite:
            self.direction = direction

    def check_collision(self):
        head_x, head_y = self.body[0]
        if head_x < 0 or head_x >= SCREEN_WIDTH or head_y < 0 or head_y >= SCREEN_HEIGHT:
            return True
        if self.body[0] in self.body[1:]:
            return True
        return False

class Food:
    def __init__(self):
        self.position = (0, 0)
        self.spawn()

    def spawn(self):
        x = random.randint(0, (SCREEN_WIDTH - BLOCK_SIZE) // BLOCK_SIZE) * BLOCK_SIZE
        y = random.randint(0, (SCREEN_HEIGHT - BLOCK_SIZE) // BLOCK_SIZE) * BLOCK_SIZE
        self.position = (x, y)

class SnakeGame:
    def __init__(self):
        self.snake = Snake()
        self.food = Food()
        self.score = 0
        self.game_over = False
        self.speed = 0.15  # seconds per frame

    def handle_input(self):
        if Screen.Up():
            self.snake.set_direction((0, -BLOCK_SIZE))
        elif Screen.Down():
            self.snake.set_direction((0, BLOCK_SIZE))
        elif Screen.Left():
            self.snake.set_direction((-BLOCK_SIZE, 0))
        elif Screen.Right():
            self.snake.set_direction((BLOCK_SIZE, 0))

    def update(self):
        self.snake.move()
        if self.snake.body[0] == self.food.position:
            self.snake.grow()
            self.food.spawn()
            self.score += 1
            if self.score % 5 == 0 and self.speed > 0.05:
                self.speed -= 0.01
        if self.snake.check_collision():
            self.game_over = True

    def draw(self):
        Screen.BeginDraw()
        Screen.Clear()
        # Snake
        for x, y in self.snake.body:
            Screen.DrawRect(x, y, BLOCK_SIZE, BLOCK_SIZE, Screen.GREEN, filled=True)
        # Food
        fx, fy = self.food.position
        Screen.DrawRect(fx, fy, BLOCK_SIZE, BLOCK_SIZE, Screen.RED, filled=True)
        # Score
        Screen.Write(f"Score: {self.score}", 5, 5, Screen.WHITE)

        if self.game_over:
            Screen.Write("GAME OVER", 70, 100, Screen.RED)
            Screen.Write(f"Score: {self.score}", 80, 120, Screen.WHITE)
            Screen.Write("B: Restart", 70, 150, Screen.BLUE)
            Screen.Write("X: Menu", 80, 170, Screen.CYAN)
        Screen.EndDraw()

    def run(self):
        while True:
            if not self.game_over:
                self.handle_input()
                self.update()
            else:
                if Screen.ButtonB():  # restart
                    self.__init__()
                elif Screen.ButtonX():  # exit to menu
                    return

            self.draw()
            Screen.Sleep(self.speed)

def launch_snake():
    game = SnakeGame()
    game.run()
