import time
import random
from screen_library import Screen

class Player:
    def __init__(self, screen_width, screen_height):
        self.width = 12
        self.height = 8
        self.x = screen_width // 2 - self.width // 2
        self.y = screen_height - self.height - 10
        self.speed = 3
        self.bullets = []
        self.screen_width = screen_width
        
    def move_left(self):
        if self.x > 0:
            self.x -= self.speed
    
    def move_right(self):
        if self.x < self.screen_width - self.width:
            self.x += self.speed
    
    def shoot(self):
        if len(self.bullets) < 3:
            bullet = Bullet(self.x + self.width // 2, self.y)
            self.bullets.append(bullet)
    
    def update_bullets(self):
        for bullet in self.bullets[:]:
            bullet.update()
            if bullet.y < 0:
                self.bullets.remove(bullet)

class Bullet:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 2
        self.height = 4
        self.speed = 4
    
    def update(self):
        self.y -= self.speed

class Enemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 8
        self.height = 6
        self.speed = 1
    
    def move(self, direction):
        if direction == "right":
            self.x += self.speed
        elif direction == "left":
            self.x -= self.speed
    
    def drop_down(self, drop_amount):
        self.y += drop_amount

class SpaceInvadersGame:
    def __init__(self):
        self.screen_width = 240
        self.screen_height = 240
        self.reset_game()
    
    def reset_game(self):
        self.player = Player(self.screen_width, self.screen_height)
        self.enemies = self.create_enemies()
        self.enemy_direction = "right"
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.victory = False
        self.enemy_move_timer = 0
        self.enemy_move_delay = 30  # Frames between enemy moves
        
    def create_enemies(self):
        enemies = []
        rows, cols = 4, 6
        start_x, start_y = 20, 30
        spacing_x, spacing_y = 30, 20
        
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * spacing_x
                y = start_y + row * spacing_y
                enemies.append(Enemy(x, y))
        return enemies
    
    def update_player(self):
        if Screen.Left():
            self.player.move_left()
        if Screen.Right():
            self.player.move_right()
        if Screen.ButtonY():
            self.player.shoot()
    
    def update_enemies(self):
        if self.game_over or self.victory:
            return
        
        self.enemy_move_timer += 10
        if self.enemy_move_timer >= self.enemy_move_delay:
            self.enemy_move_timer = 0
            self.move_enemies()
    
    def move_enemies(self):
        if not self.enemies:
            return
            
        hit_edge = False
        for enemy in self.enemies:
            enemy.move(self.enemy_direction)
            if (enemy.x <= 0 and self.enemy_direction == "left") or \
               (enemy.x >= self.screen_width - enemy.width and self.enemy_direction == "right"):
                hit_edge = True
        
        if hit_edge:
            self.enemy_direction = "left" if self.enemy_direction == "right" else "right"
            for enemy in self.enemies:
                enemy.drop_down(10)
                
        for enemy in self.enemies:
            if enemy.y + enemy.height >= self.player.y:
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
                else:
                    self.enemies = self.create_enemies()
                    self.enemy_direction = "right"
                break
    
    def update_bullets(self):
        self.player.update_bullets()
        for bullet in self.player.bullets[:]:
            for enemy in self.enemies[:]:
                if (bullet.x < enemy.x + enemy.width and
                    bullet.x + bullet.width > enemy.x and
                    bullet.y < enemy.y + enemy.height and
                    bullet.y + bullet.height > enemy.y):
                    
                    self.player.bullets.remove(bullet)
                    self.enemies.remove(enemy)
                    self.score += 10
                    
                    if not self.enemies:
                        self.victory = True
                    break
    
    def draw(self):
        Screen.BeginDraw()
        Screen.Clear()
        
        if not self.game_over and not self.victory:
            # Player
            Screen.DrawRect(self.player.x, self.player.y, self.player.width, self.player.height, Screen.GREEN, filled=True)
            
            # Bullets
            for bullet in self.player.bullets:
                Screen.DrawRect(bullet.x, bullet.y, bullet.width, bullet.height, Screen.WHITE, filled=True)
            
            # Enemies
            for enemy in self.enemies:
                Screen.DrawRect(enemy.x, enemy.y, enemy.width, enemy.height, Screen.RED, filled=True)
            
            # UI
            Screen.Write(f"Score: {self.score}", 5, 5, Screen.WHITE)
            Screen.Write(f"Lives: {self.lives}", 170, 5, Screen.WHITE)
        
        elif self.victory:
            Screen.Write("VICTORY!", 85, 100, Screen.GREEN)
            Screen.Write(f"Score: {self.score}", 85, 120, Screen.WHITE)
            Screen.Write("Press B to restart", 60, 140, Screen.BLUE)
            
        else:
            Screen.Write("GAME OVER", 80, 100, Screen.RED)
            Screen.Write(f"Score: {self.score}", 85, 120, Screen.WHITE)
            Screen.Write("Press B to restart", 60, 140, Screen.BLUE)
        
        if not self.game_over and not self.victory:
            Screen.Write("Y: Shoot", 5, 225, Screen.CYAN)
        
        Screen.EndDraw()
    
    def run(self):
        while True:
            if Screen.ButtonB() and (self.game_over or self.victory):
                self.reset_game()
            
            if Screen.ButtonX():
                return  # Exit back to menu
            
            self.update_player()
            self.update_enemies()
            self.update_bullets()
            self.draw()
            
            Screen.Sleep(0.033)  # ~30 FPS

def launch_space_invaders():
    game = SpaceInvadersGame()
    game.run()
