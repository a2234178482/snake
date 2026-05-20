"""
==============================================
进化贪吃蛇 - Evolutionary Snake (用户版)
==============================================
Setup Guide:
1. Install dependencies:
   pip install pygame
2. Run the game:
   python evolutionary_snake.py
==============================================
功能列表:
(1) 用户注册: 首次使用需注册用户名和密码
(2) 用户登录: 每次开始游戏需验证用户名和密码
(3) 游戏主界面显示"***XXX正在游戏中***"
(4) 游戏主界面显示"按F5显示游戏用户日志"
(5) 游戏用户表记录用户名和密码; 游戏用户日志记录ID、用户名、开始时间、持续时长和得分
(6) 蛇可见, 吃食物后长度增加, 敌人/Boss/技能树/日夜循环等高级功能
==============================================
"""

import pygame
import math
import random
import sys
import os
import json
import time
import hashlib
from typing import List, Tuple, Dict, Optional
from enum import Enum, auto
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

pygame.init()

SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 800
MAP_WIDTH, MAP_HEIGHT = 2400, 1600
FPS = 60

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DARK_GRAY = (40, 40, 40)
GRAY = (100, 100, 100)
LIGHT_GRAY = (180, 180, 180)
RED = (220, 60, 60)
GREEN = (60, 220, 60)
BLUE = (60, 60, 220)
GOLD = (255, 215, 0)
PURPLE = (180, 60, 220)
CYAN = (60, 220, 220)
ORANGE = (255, 140, 0)
YELLOW = (255, 255, 0)
LAVA_COLOR = (255, 80, 0)
DARK_BG = (20, 20, 30)
GRID_COLOR = (40, 40, 50)
SNAKE_HEAD = (80, 200, 80)
SNAKE_BODY = (60, 160, 60)
SNAKE_OUTLINE = (40, 120, 40)
SNAKE_INV_COLOR = (180, 180, 255)

USERS_FILE = "snake_users.json"
LOGS_FILE = "snake_game_logs.json"


class GameState(Enum):
    MENU = auto()
    REGISTER = auto()
    LOGIN = auto()
    PLAYING = auto()
    PAUSED = auto()
    SKILL_TREE = auto()
    GAME_OVER = auto()
    USER_LOG = auto()


class EnemyType(Enum):
    HUNTER = auto()
    TURRET = auto()
    GHOST = auto()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def normalize(vx: float, vy: float) -> Tuple[float, float]:
    m = math.hypot(vx, vy)
    return (vx / m, vy / m) if m > 0 else (0, 0)


def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


# ==============================================================================
# 数据管理: 用户表 + 游戏日志
# ==============================================================================

class UserDataManager:
    def __init__(self):
        self.users: Dict[str, dict] = {}
        self.logs: List[dict] = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
        except Exception:
            self.users = {}
        try:
            if os.path.exists(LOGS_FILE):
                with open(LOGS_FILE, "r", encoding="utf-8") as f:
                    self.logs = json.load(f)
        except Exception:
            self.logs = []

    def _save_users(self):
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_logs(self):
        try:
            with open(LOGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def register(self, username: str, password: str) -> Tuple[bool, str]:
        if not username or not password:
            return False, "用户名和密码不能为空"
        if username in self.users:
            return False, "该用户名已存在"
        if len(username) < 2:
            return False, "用户名至少2个字符"
        if len(password) < 3:
            return False, "密码至少3个字符"
        uid = str(len(self.users) + 1)
        self.users[username] = {
            "id": uid,
            "username": username,
            "password": hash_password(password),
        }
        self._save_users()
        return True, "注册成功!"

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        if not username or not password:
            return False, "用户名和密码不能为空"
        if username not in self.users:
            return False, "用户名不存在"
        if self.users[username]["password"] != hash_password(password):
            return False, "密码错误"
        return True, "登录成功!"

    def get_user_id(self, username: str) -> str:
        return self.users.get(username, {}).get("id", "?")

    def add_log(self, username: str, start_time: str, duration: float, score: int):
        uid = self.get_user_id(username)
        entry = {
            "id": uid,
            "username": username,
            "start_time": start_time,
            "duration_sec": round(duration, 1),
            "score": score,
        }
        self.logs.append(entry)
        self._save_logs()

    def get_logs(self) -> List[dict]:
        return self.logs


# ==============================================================================
# 粒子系统
# ==============================================================================

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    color: Tuple[int, int, int]


class ParticleSystem:
    def __init__(self):
        self.particles: List[Particle] = []

    def emit(self, x: float, y: float, count: int, color: Tuple[int, int, int],
             speed_range: Tuple[float, float] = (2, 8),
             size_range: Tuple[float, float] = (2, 8),
             life_range: Tuple[float, float] = (0.5, 2.0)):
        for _ in range(count):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(*speed_range)
            life = random.uniform(*life_range)
            size = random.uniform(*size_range)
            self.particles.append(Particle(
                x, y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                life, life, size, color
            ))

    def update(self, dt: float):
        alive = []
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.vy += 0.1
            p.life -= dt
            if p.life > 0:
                alive.append(p)
        self.particles = alive

    def draw(self, surface: pygame.Surface, cx: float, cy: float):
        for p in self.particles:
            alpha = max(0, min(255, int(255 * (p.life / p.max_life))))
            px, py = int(p.x - cx), int(p.y - cy)
            if -20 < px < SCREEN_WIDTH + 20 and -20 < py < SCREEN_HEIGHT + 20:
                sz = max(1, int(p.size))
                s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*p.color, alpha), (sz, sz), sz)
                surface.blit(s, (px - sz, py - sz))


# ==============================================================================
# 蛇类 (Verlet 身体物理)
# ==============================================================================

@dataclass
class BodySegment:
    x: float
    y: float
    radius: float = 10


class Snake:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = MAP_WIDTH / 2
        self.y = MAP_HEIGHT / 2
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0
        self.speed = 200
        self.body: List[BodySegment] = []
        self.health = 100
        self.max_health = 100
        self.stamina = 100
        self.max_stamina = 100
        self.boost = False
        self.invincible = False
        self.invincible_timer = 0.0
        self.titanic = False
        self.magnet = False
        self.heads = 1
        for i in range(20):
            self.body.append(BodySegment(self.x - i * 15, self.y, 12 - i * 0.3))

    def add_head(self):
        self.heads += 1

    def grow(self, segments: int = 3):
        for _ in range(segments):
            tail = self.body[-1]
            self.body.append(BodySegment(tail.x, tail.y, max(6, tail.radius - 0.1)))

    def update(self, dt: float, keys, game):
        ax, ay = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            ay -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            ay += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            ax -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            ax += 1

        self.boost = keys[pygame.K_SPACE] and self.stamina > 0
        if self.boost:
            self.stamina = max(0, self.stamina - dt * 50)
        else:
            self.stamina = min(self.max_stamina, self.stamina + dt * 20)

        if ax != 0 or ay != 0:
            ax, ay = normalize(ax, ay)
            target = math.atan2(ay, ax)
            diff = math.atan2(math.sin(target - self.angle), math.cos(target - self.angle))
            self.angle += diff * dt * 8

        spd = self.speed * (2 if self.boost else 1)
        tvx = math.cos(self.angle) * spd
        tvy = math.sin(self.angle) * spd
        self.vx = lerp(self.vx, tvx, dt * 5)
        self.vy = lerp(self.vy, tvy, dt * 5)

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = max(50, min(MAP_WIDTH - 50, self.x))
        self.y = max(50, min(MAP_HEIGHT - 50, self.y))

        if self.invincible:
            self.invincible_timer -= dt
            if self.invincible_timer <= 0:
                self.invincible = False

        self.body[0].x = self.x
        self.body[0].y = self.y
        self.body[0].radius = 20 if self.titanic else 15

        for i in range(1, len(self.body)):
            prev = self.body[i - 1]
            seg = self.body[i]
            dx = prev.x - seg.x
            dy = prev.y - seg.y
            d = math.hypot(dx, dy)
            if d > 18:
                seg.x += dx * 0.25
                seg.y += dy * 0.25

        if self.magnet:
            for food in game.foods[:]:
                d = dist((self.x, self.y), (food.x, food.y))
                if d < 200 and d > 0:
                    food.x += (self.x - food.x) * 0.05
                    food.y += (self.y - food.y) * 0.05

    def draw(self, surface: pygame.Surface, cx: float, cy: float):
        for i in range(len(self.body) - 1, -1, -1):
            seg = self.body[i]
            sx = int(seg.x - cx)
            sy = int(seg.y - cy)
            if -50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50:
                t = i / max(1, len(self.body) - 1)
                if i == 0:
                    color = SNAKE_HEAD
                else:
                    color = (
                        int(60 + t * 30),
                        int(180 - t * 40),
                        int(60 + t * 30),
                    )
                if self.invincible:
                    color = SNAKE_INV_COLOR
                radius = int(seg.radius * (1.5 if self.titanic else 1))
                pygame.draw.circle(surface, color, (sx, sy), radius)
                pygame.draw.circle(surface, SNAKE_OUTLINE, (sx, sy), radius, 2)

        hx = int(self.x - cx)
        hy = int(self.y - cy)
        eo = 8
        for sign in (0.3, -0.3):
            ex = hx + math.cos(self.angle + sign) * eo
            ey = hy + math.sin(self.angle + sign) * eo
            pygame.draw.circle(surface, WHITE, (int(ex), int(ey)), 5)
            pygame.draw.circle(surface, BLACK, (int(ex), int(ey)), 2)


# ==============================================================================
# 食物
# ==============================================================================

class Food:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = 12
        self.pulse = random.uniform(0, 6)
        self.color = random.choice([RED, GOLD, GREEN, BLUE, PURPLE])
        self.xp_value = random.randint(10, 30)

    def update(self, dt: float):
        self.pulse += dt * 4

    def draw(self, surface: pygame.Surface, cx: float, cy: float):
        fx = int(self.x - cx)
        fy = int(self.y - cy)
        if -30 < fx < SCREEN_WIDTH + 30 and -30 < fy < SCREEN_HEIGHT + 30:
            sz = self.radius + math.sin(self.pulse) * 3
            pygame.draw.circle(surface, self.color, (fx, fy), int(sz))
            pygame.draw.circle(surface, WHITE, (fx, fy), int(sz * 0.4))


# ==============================================================================
# 敌人系统
# ==============================================================================

class Enemy(ABC):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.health = 30
        self.damage = 10
        self.speed = 100

    @abstractmethod
    def update(self, dt: float, game) -> None:
        pass

    @abstractmethod
    def draw(self, surface: pygame.Surface, cx: float, cy: float) -> None:
        pass


class Hunter(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.health = 30
        self.speed = 120

    def update(self, dt, game):
        dx = game.snake.x - self.x
        dy = game.snake.y - self.y
        d = math.hypot(dx, dy)
        if d > 0:
            self.x += (dx / d) * self.speed * dt
            self.y += (dy / d) * self.speed * dt

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        pygame.draw.circle(surface, RED, (x, y), 15)
        pygame.draw.circle(surface, (150, 0, 0), (x, y), 15, 3)
        pygame.draw.circle(surface, WHITE, (x - 5, y - 3), 4)
        pygame.draw.circle(surface, WHITE, (x + 5, y - 3), 4)


class Turret(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.health = 50
        self.shoot_timer = 0
        self.angle = 0

    def update(self, dt, game):
        self.shoot_timer -= dt
        if self.shoot_timer <= 0:
            self.shoot_timer = 2
            dx = game.snake.x - self.x
            dy = game.snake.y - self.y
            self.angle = math.atan2(dy, dx)
            game.projectiles.append(Projectile(
                self.x, self.y,
                math.cos(self.angle) * 200,
                math.sin(self.angle) * 200, 10
            ))

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        pygame.draw.circle(surface, DARK_GRAY, (x, y), 20)
        pygame.draw.circle(surface, GRAY, (x, y), 20, 3)
        gx = x + math.cos(self.angle) * 25
        gy = y + math.sin(self.angle) * 25
        pygame.draw.line(surface, GRAY, (x, y), (int(gx), int(gy)), 6)


class Ghost(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.health = 20
        self.speed = 80
        self.phase = 0

    def update(self, dt, game):
        self.phase += dt * 2
        dx = game.snake.x - self.x
        dy = game.snake.y - self.y
        d = math.hypot(dx, dy)
        if d > 0:
            self.x += (dx / d) * self.speed * dt + math.sin(self.phase) * 20 * dt
            self.y += (dy / d) * self.speed * dt + math.cos(self.phase) * 20 * dt

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        alpha = int(128 + math.sin(self.phase) * 64)
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(s, (*PURPLE, alpha), (20, 20), 18)
        surface.blit(s, (x - 20, y - 20))


class Boss(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.health = 300
        self.max_health = 300
        self.damage = 20
        self.speed = 60
        self.phase = 0
        self.segments = [(x, y) for _ in range(10)]

    def update(self, dt, game):
        self.phase += dt
        dx = game.snake.x - self.x
        dy = game.snake.y - self.y
        d = math.hypot(dx, dy)
        if d > 0:
            self.x += (dx / d) * self.speed * dt
            self.y += (dy / d) * self.speed * dt
        self.segments[0] = (self.x, self.y)
        for i in range(1, len(self.segments)):
            prev = self.segments[i - 1]
            curr = self.segments[i]
            dx2 = prev[0] - curr[0]
            dy2 = prev[1] - curr[1]
            d2 = math.hypot(dx2, dy2)
            if d2 > 30:
                self.segments[i] = (curr[0] + dx2 * 0.1, curr[1] + dy2 * 0.1)
        if int(self.phase * 2) % 3 == 0 and 0 < self.phase % 1 < dt * 5:
            for a in range(8):
                angle = math.pi * 2 / 8 * a
                game.projectiles.append(Projectile(
                    self.x, self.y,
                    math.cos(angle) * 150,
                    math.sin(angle) * 150, 15
                ))

    def draw(self, surface, cx, cy):
        for i, (sx, sy) in enumerate(reversed(self.segments)):
            x, y = int(sx - cx), int(sy - cy)
            sz = 35 - i * 2
            pygame.draw.circle(surface, (200, 50, 50), (x, y), sz)
            pygame.draw.circle(surface, (150, 0, 0), (x, y), sz, 3)
        hx, hy = int(self.x - cx), int(self.y - cy)
        for dx in (-15, 15):
            pygame.draw.circle(surface, YELLOW, (hx + dx, hy - 10), 8)
            pygame.draw.circle(surface, BLACK, (hx + dx, hy - 10), 4)
        bw, bh = 100, 10
        bx, by = hx - bw // 2, hy - 60
        pygame.draw.rect(surface, DARK_GRAY, (bx, by, bw, bh))
        pygame.draw.rect(surface, RED, (bx, by, int(bw * self.health / self.max_health), bh))


class Projectile:
    def __init__(self, x, y, vx, vy, damage):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.damage = damage
        self.life = 5

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        pygame.draw.circle(surface, ORANGE, (x, y), 6)


class EnemyManager:
    def __init__(self):
        self.enemies: List[Enemy] = []
        self.projectiles: List[Projectile] = []
        self.spawn_timer = 0

    def update(self, dt, game):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = max(2, 5 - game.score / 200)
            x = random.uniform(100, MAP_WIDTH - 100)
            y = random.uniform(100, MAP_HEIGHT - 100)
            et = random.choice([EnemyType.HUNTER, EnemyType.TURRET, EnemyType.GHOST])
            if et == EnemyType.HUNTER:
                self.enemies.append(Hunter(x, y))
            elif et == EnemyType.TURRET:
                self.enemies.append(Turret(x, y))
            else:
                self.enemies.append(Ghost(x, y))

        for e in self.enemies:
            e.update(dt, game)
            d = dist((e.x, e.y), (game.snake.x, game.snake.y))
            if d < 40 and not game.snake.invincible:
                game.snake.health -= e.damage * dt
                game.particles.emit(e.x, e.y, 10, RED)
                game.screen_shake = 10

        rm = []
        for p in self.projectiles:
            p.update(dt)
            d = dist((p.x, p.y), (game.snake.x, game.snake.y))
            if d < 25 and not game.snake.invincible:
                game.snake.health -= p.damage
                game.particles.emit(p.x, p.y, 8, ORANGE)
                rm.append(p)
            elif p.life <= 0:
                rm.append(p)
        for p in rm:
            if p in self.projectiles:
                self.projectiles.remove(p)

    def draw(self, surface, cx, cy):
        for e in self.enemies:
            e.draw(surface, cx, cy)
        for p in self.projectiles:
            p.draw(surface, cx, cy)


# ==============================================================================
# 地图 & 危险物
# ==============================================================================

class Wall:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, surface, cx, cy):
        x, y = int(self.rect.x - cx), int(self.rect.y - cy)
        pygame.draw.rect(surface, DARK_GRAY, (x, y, self.rect.width, self.rect.height))
        pygame.draw.rect(surface, GRAY, (x, y, self.rect.width, self.rect.height), 2)


class Lava:
    def __init__(self, x, y, radius):
        self.x, self.y, self.radius = x, y, radius
        self.phase = 0

    def update(self, dt):
        self.phase += dt * 3

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        sz = int(self.radius + math.sin(self.phase) * 5)
        s = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*LAVA_COLOR, 200), (sz, sz), sz)
        surface.blit(s, (x - sz, y - sz))


class Portal:
    def __init__(self, x, y, tx, ty):
        self.x, self.y = x, y
        self.tx, self.ty = tx, ty
        self.phase = 0

    def update(self, dt):
        self.phase += dt * 2

    def draw(self, surface, cx, cy):
        x, y = int(self.x - cx), int(self.y - cy)
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(s, (*PURPLE, 150), (40, 40), int(30 + math.sin(self.phase) * 5))
        pygame.draw.circle(s, (*CYAN, 200), (40, 40), 15)
        surface.blit(s, (x - 40, y - 40))


class HazardManager:
    def __init__(self):
        self.walls: List[Wall] = []
        self.lavas: List[Lava] = []
        self.portals: List[Portal] = []

    def generate(self):
        self.walls.clear()
        self.lavas.clear()
        self.portals.clear()
        for _ in range(30):
            self.walls.append(Wall(
                random.uniform(100, MAP_WIDTH - 200),
                random.uniform(100, MAP_HEIGHT - 200),
                random.uniform(50, 200), random.uniform(50, 200)
            ))
        for _ in range(10):
            self.lavas.append(Lava(
                random.uniform(200, MAP_WIDTH - 200),
                random.uniform(200, MAP_HEIGHT - 200),
                random.uniform(30, 60)
            ))
        for _ in range(3):
            self.portals.append(Portal(
                random.uniform(200, MAP_WIDTH - 200),
                random.uniform(200, MAP_HEIGHT - 200),
                random.uniform(200, MAP_WIDTH - 200),
                random.uniform(200, MAP_HEIGHT - 200)
            ))

    def update(self, dt):
        for l in self.lavas:
            l.update(dt)
        for p in self.portals:
            p.update(dt)

    def draw(self, surface, cx, cy):
        for w in self.walls:
            w.draw(surface, cx, cy)
        for l in self.lavas:
            l.draw(surface, cx, cy)
        for p in self.portals:
            p.draw(surface, cx, cy)

    def check(self, snake, game):
        sr = pygame.Rect(snake.x - 15, snake.y - 15, 30, 30)
        for w in self.walls:
            if sr.colliderect(w.rect):
                if snake.titanic:
                    pass
                else:
                    return True
        for l in self.lavas:
            if dist((snake.x, snake.y), (l.x, l.y)) < l.radius + 15 and not snake.invincible:
                snake.health -= 0.5
        for p in self.portals:
            if dist((snake.x, snake.y), (p.x, p.y)) < 40:
                snake.x, snake.y = p.tx, p.ty
                game.particles.emit(p.tx, p.ty, 20, PURPLE)
        return False


# ==============================================================================
# 输入框 UI 组件
# ==============================================================================

class InputBox:
    def __init__(self, x, y, w, h, label="", password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ""
        self.label = label
        self.active = False
        self.password = password
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_TAB:
                return "TAB"
            elif event.key == pygame.K_RETURN:
                return "ENTER"
            elif len(self.text) < 20 and event.unicode.isprintable() and event.unicode:
                self.text += event.unicode
        return None

    def draw(self, surface, font, small_font):
        label_surf = small_font.render(self.label, True, LIGHT_GRAY)
        surface.blit(label_surf, (self.rect.x, self.rect.y - 25))
        color = GOLD if self.active else GRAY
        pygame.draw.rect(surface, (30, 30, 40), self.rect)
        pygame.draw.rect(surface, color, self.rect, 2)
        display = "*" * len(self.text) if self.password else self.text
        self.cursor_timer += 1
        cursor = "|" if self.active and self.cursor_timer % 60 < 30 else ""
        txt = font.render(display + cursor, True, WHITE)
        surface.blit(txt, (self.rect.x + 10, self.rect.y + 8))


# ==============================================================================
# 主游戏类
# ==============================================================================

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("进化贪吃蛇 - Evolutionary Snake")
        self.clock = pygame.time.Clock()

        self.font_large = pygame.font.SysFont("Microsoft YaHei", 48, bold=True)
        self.font_medium = pygame.font.SysFont("Microsoft YaHei", 28)
        self.font_small = pygame.font.SysFont("Microsoft YaHei", 20)
        self.font_tiny = pygame.font.SysFont("Microsoft YaHei", 16)
        self.font_input = pygame.font.SysFont("Microsoft YaHei", 22)

        self.data_mgr = UserDataManager()
        self.state = GameState.MENU
        self.current_user = ""
        self.message = ""
        self.message_timer = 0

        self.reg_user_box = InputBox(SCREEN_WIDTH // 2 - 150, 300, 300, 40, "用户名")
        self.reg_pwd_box = InputBox(SCREEN_WIDTH // 2 - 150, 380, 300, 40, "密码", password=True)
        self.login_user_box = InputBox(SCREEN_WIDTH // 2 - 150, 300, 300, 40, "用户名")
        self.login_pwd_box = InputBox(SCREEN_WIDTH // 2 - 150, 380, 300, 40, "密码", password=True)

        self.log_scroll = 0
        self.log_from_menu = False
        self.high_score = 0
        self._init_game_vars()

    def _init_game_vars(self):
        self.snake = Snake()
        self.enemies = EnemyManager()
        self.hazards = HazardManager()
        self.foods: List[Food] = []
        self.particles = ParticleSystem()
        self.projectiles: List[Projectile] = []
        self.score = 0
        self.level = 1
        self.xp = 0
        self.xp_to_next = 100
        self.skill_points = 0
        self.skills = {"hydra": False, "titanic": False, "phase_shift": 0, "magnet": False}
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.day_night = 0.0
        self.screen_shake = 0.0
        self.boss_spawned = False
        self.game_start_time = ""
        self.game_start_tick = 0.0

    def start_new_game(self):
        self._init_game_vars()
        self.hazards.generate()
        for _ in range(20):
            self.foods.append(Food(
                random.uniform(100, MAP_WIDTH - 100),
                random.uniform(100, MAP_HEIGHT - 100)
            ))
        self.game_start_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.game_start_tick = time.time()
        self.state = GameState.PLAYING

    def _show_msg(self, msg, duration=3.0):
        self.message = msg
        self.message_timer = duration

    # ---------- 事件处理 ----------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._on_quit()
                pygame.quit()
                sys.exit()

            if self.state == GameState.MENU:
                self._ev_menu(event)
            elif self.state == GameState.REGISTER:
                self._ev_register(event)
            elif self.state == GameState.LOGIN:
                self._ev_login(event)
            elif self.state == GameState.PLAYING:
                self._ev_playing(event)
            elif self.state == GameState.PAUSED:
                self._ev_paused(event)
            elif self.state == GameState.SKILL_TREE:
                self._ev_skill(event)
            elif self.state == GameState.GAME_OVER:
                self._ev_gameover(event)
            elif self.state == GameState.USER_LOG:
                self._ev_log(event)

    def _on_quit(self):
        if self.state == GameState.PLAYING and self.current_user:
            dur = time.time() - self.game_start_tick
            self.data_mgr.add_log(self.current_user, self.game_start_time, dur, self.score)

    def _ev_menu(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self.state = GameState.REGISTER
                self.reg_user_box.text = ""
                self.reg_pwd_box.text = ""
                self.reg_user_box.active = True
                self.reg_pwd_box.active = False
            elif event.key == pygame.K_2:
                self.state = GameState.LOGIN
                self.login_user_box.text = ""
                self.login_pwd_box.text = ""
                self.login_user_box.active = True
                self.login_pwd_box.active = False
            elif event.key == pygame.K_3:
                self.log_scroll = 0
                self.log_from_menu = True
                self.state = GameState.USER_LOG
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

    def _ev_register(self, event):
        r1 = self.reg_user_box.handle_event(event)
        r2 = self.reg_pwd_box.handle_event(event)
        if r1 == "TAB":
            self.reg_user_box.active = False
            self.reg_pwd_box.active = True
        if r2 == "TAB":
            self.reg_pwd_box.active = False
            self.reg_user_box.active = True
        if r1 == "ENTER" or r2 == "ENTER":
            ok, msg = self.data_mgr.register(self.reg_user_box.text, self.reg_pwd_box.text)
            self._show_msg(msg)
            if ok:
                self.current_user = self.reg_user_box.text
                self.start_new_game()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = GameState.MENU

    def _ev_login(self, event):
        r1 = self.login_user_box.handle_event(event)
        r2 = self.login_pwd_box.handle_event(event)
        if r1 == "TAB":
            self.login_user_box.active = False
            self.login_pwd_box.active = True
        if r2 == "TAB":
            self.login_pwd_box.active = False
            self.login_user_box.active = True
        if r1 == "ENTER" or r2 == "ENTER":
            ok, msg = self.data_mgr.login(self.login_user_box.text, self.login_pwd_box.text)
            self._show_msg(msg)
            if ok:
                self.current_user = self.login_user_box.text
                self.start_new_game()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = GameState.MENU

    def _ev_playing(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_t:
                self.state = GameState.SKILL_TREE
            elif event.key == pygame.K_p:
                self.state = GameState.PAUSED
            elif event.key == pygame.K_ESCAPE:
                dur = time.time() - self.game_start_tick
                self.data_mgr.add_log(self.current_user, self.game_start_time, dur, self.score)
                self.state = GameState.MENU
            elif event.key == pygame.K_F5:
                self.log_scroll = 0
                self.log_from_menu = False
                self.state = GameState.USER_LOG

    def _ev_paused(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                self.state = GameState.PLAYING
            elif event.key == pygame.K_ESCAPE:
                dur = time.time() - self.game_start_tick
                self.data_mgr.add_log(self.current_user, self.game_start_time, dur, self.score)
                self.state = GameState.MENU

    def _ev_skill(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_t, pygame.K_ESCAPE):
                self.state = GameState.PLAYING
            elif event.key == pygame.K_1 and self.skill_points > 0 and not self.skills["hydra"]:
                self.skills["hydra"] = True
                self.skill_points -= 1
                self.snake.add_head()
            elif event.key == pygame.K_2 and self.skill_points > 0 and not self.skills["titanic"]:
                self.skills["titanic"] = True
                self.skill_points -= 1
                self.snake.titanic = True
            elif event.key == pygame.K_3 and self.skill_points > 0 and self.skills["phase_shift"] < 3:
                self.skills["phase_shift"] += 1
                self.skill_points -= 1
                self.snake.invincible = True
                self.snake.invincible_timer = 10.0
            elif event.key == pygame.K_4 and self.skill_points > 0 and not self.skills["magnet"]:
                self.skills["magnet"] = True
                self.skill_points -= 1
                self.snake.magnet = True

    def _ev_gameover(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.start_new_game()
            elif event.key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def _ev_log(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.log_from_menu:
                    self.state = GameState.MENU
                else:
                    self.state = GameState.PLAYING
            elif event.key == pygame.K_F5 and not self.log_from_menu:
                self.state = GameState.PLAYING
            elif event.key == pygame.K_UP:
                self.log_scroll = max(0, self.log_scroll - 3)
            elif event.key == pygame.K_DOWN:
                self.log_scroll += 3
        if event.type == pygame.MOUSEWHEEL:
            self.log_scroll = max(0, self.log_scroll - event.y * 2)

    # ---------- 更新 ----------

    def update(self):
        dt = self.clock.tick(FPS) / 1000.0
        if self.message_timer > 0:
            self.message_timer -= dt

        if self.state == GameState.PLAYING:
            keys = pygame.key.get_pressed()
            self.snake.update(dt, keys, self)
            self.enemies.update(dt, self)
            self.particles.update(dt)
            self.hazards.update(dt)
            self.day_night += dt * 0.01
            if self.day_night > math.pi * 2:
                self.day_night = 0

            if self.hazards.check(self.snake, self):
                self._game_over()

            if self.snake.health <= 0:
                self._game_over()

            if self.score > 0 and self.score % 500 == 0 and not self.boss_spawned:
                self._spawn_boss()
                self.boss_spawned = True
            elif self.score % 500 != 0:
                self.boss_spawned = False

            self._check_food()
        else:
            self.particles.update(dt)

    def _game_over(self):
        dur = time.time() - self.game_start_tick
        self.data_mgr.add_log(self.current_user, self.game_start_time, dur, self.score)
        if self.score > self.high_score:
            self.high_score = self.score
        self.state = GameState.GAME_OVER

    def _spawn_boss(self):
        x = self.snake.x + random.choice([-500, 500])
        y = self.snake.y + random.choice([-400, 400])
        bx = max(200, min(MAP_WIDTH - 200, x))
        by = max(200, min(MAP_HEIGHT - 200, y))
        self.enemies.enemies.append(Boss(bx, by))
        self.particles.emit(x, y, 50, PURPLE)

    def _check_food(self):
        rm = []
        for food in self.foods:
            d = dist((self.snake.x, self.snake.y), (food.x, food.y))
            if d < 30:
                self.score += food.xp_value
                self.xp += food.xp_value
                self.particles.emit(food.x, food.y, 15, food.color)
                self.screen_shake = 5
                self.snake.grow(3)
                rm.append(food)
                if self.xp >= self.xp_to_next:
                    self.level += 1
                    self.xp -= self.xp_to_next
                    self.xp_to_next = int(self.xp_to_next * 1.5)
                    self.skill_points += 1
                    self.snake.max_health += 10
                    self.snake.health = self.snake.max_health
        for f in rm:
            self.foods.remove(f)
            self.foods.append(Food(
                random.uniform(100, MAP_WIDTH - 100),
                random.uniform(100, MAP_HEIGHT - 100)
            ))

    # ---------- 渲染 ----------

    def draw(self):
        if self.state == GameState.MENU:
            self._draw_menu()
        elif self.state == GameState.REGISTER:
            self._draw_register()
        elif self.state == GameState.LOGIN:
            self._draw_login()
        elif self.state == GameState.USER_LOG:
            self._draw_log_screen()
        else:
            self._draw_world()
            self._draw_hud()
            if self.state == GameState.PAUSED:
                self._draw_overlay_text("游戏暂停", "按 P 继续 | ESC 退出", (0, 0, 0, 180))
            elif self.state == GameState.SKILL_TREE:
                self._draw_skill_tree()
            elif self.state == GameState.GAME_OVER:
                self._draw_gameover()

        if self.message_timer > 0 and self.message:
            alpha = min(255, int(self.message_timer / 0.5 * 255))
            s = self.font_small.render(self.message, True, GOLD)
            r = s.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60))
            bg = pygame.Surface((r.width + 20, r.height + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, min(180, alpha)))
            self.screen.blit(bg, (r.x - 10, r.y - 5))
            self.screen.blit(s, r)

        pygame.display.flip()

    def _draw_menu(self):
        self.screen.fill(DARK_BG)
        t = self.font_large.render("🐍 进化贪吃蛇", True, GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, 150)))
        sub = self.font_medium.render("Evolutionary Snake", True, LIGHT_GRAY)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 220)))

        opts = [
            ("1", "注册新用户", GREEN),
            ("2", "用户登录", CYAN),
            ("3", "查看游戏日志", ORANGE),
            ("ESC", "退出游戏", RED),
        ]
        y = 310
        for key, label, color in opts:
            kt = self.font_medium.render(f"[{key}]", True, color)
            lt = self.font_medium.render(f"  {label}", True, WHITE)
            total_w = kt.get_width() + lt.get_width()
            sx = SCREEN_WIDTH // 2 - total_w // 2
            self.screen.blit(kt, (sx, y))
            self.screen.blit(lt, (sx + kt.get_width(), y))
            y += 60

        if self.high_score > 0:
            hs = self.font_small.render(f"历史最高分: {self.high_score}", True, GOLD)
            self.screen.blit(hs, hs.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 60)))

    def _draw_auth_screen(self, title, box1, box2, btn_label):
        self.screen.fill(DARK_BG)
        t = self.font_large.render(title, True, GOLD)
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, 150)))
        box1.draw(self.screen, self.font_input, self.font_small)
        box2.draw(self.screen, self.font_input, self.font_small)
        btn = self.font_medium.render(f"[Enter] {btn_label}", True, GREEN)
        self.screen.blit(btn, btn.get_rect(center=(SCREEN_WIDTH // 2, 470)))
        hint = self.font_tiny.render("TAB 切换输入框 | ESC 返回菜单", True, GRAY)
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 530)))

    def _draw_register(self):
        self._draw_auth_screen("注册新用户", self.reg_user_box, self.reg_pwd_box, "注册并开始游戏")

    def _draw_login(self):
        self._draw_auth_screen("用户登录", self.login_user_box, self.login_pwd_box, "登录并开始游戏")

    def _draw_world(self):
        tcx = self.snake.x - SCREEN_WIDTH / 2
        tcy = self.snake.y - SCREEN_HEIGHT / 2
        self.camera_x = lerp(self.camera_x, tcx, 0.1)
        self.camera_y = lerp(self.camera_y, tcy, 0.1)
        self.camera_x = max(0, min(MAP_WIDTH - SCREEN_WIDTH, self.camera_x))
        self.camera_y = max(0, min(MAP_HEIGHT - SCREEN_HEIGHT, self.camera_y))

        if self.screen_shake > 0:
            self.screen_shake -= 0.5
        sx = random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0
        sy = random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0
        cx, cy = self.camera_x + sx, self.camera_y + sy

        self.screen.fill((30, 30, 40))

        for gy in range(0, MAP_HEIGHT, 100):
            for gx in range(0, MAP_WIDTH, 100):
                dx, dy = gx - cx, gy - cy
                if -100 < dx < SCREEN_WIDTH + 100 and -100 < dy < SCREEN_HEIGHT + 100:
                    pygame.draw.circle(self.screen, GRID_COLOR, (int(dx), int(dy)), 3)

        self.hazards.draw(self.screen, cx, cy)
        for f in self.foods:
            f.update(1 / 60)
            f.draw(self.screen, cx, cy)
        self.enemies.draw(self.screen, cx, cy)
        self.snake.draw(self.screen, cx, cy)
        self.particles.draw(self.screen, cx, cy)

        nf = 0.5 + 0.5 * math.cos(self.day_night)
        if nf < 0.3:
            ls = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            darkness = int((0.3 - nf) * 255)
            ls.fill((0, 0, 30, darkness))
            hx = int(self.snake.x - cx)
            hy = int(self.snake.y - cy)
            for i in range(80, 0, -2):
                s2 = pygame.Surface((i * 2, i * 2), pygame.SRCALPHA)
                pygame.draw.circle(s2, (0, 0, 0, 0), (i, i), i)
                ls.blit(s2, (hx - i, hy - i), special_flags=pygame.BLEND_RGBA_SUB)
            self.screen.blit(ls, (0, 0))

    def _draw_hud(self):
        user_text = f"*** {self.current_user} 正在游戏中 ***"
        ut = self.font_medium.render(user_text, True, GOLD)
        ur = ut.get_rect(midtop=(SCREEN_WIDTH // 2, 8))
        bg = pygame.Surface((ur.width + 20, ur.height + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        self.screen.blit(bg, (ur.x - 10, ur.y - 3))
        self.screen.blit(ut, ur)

        self.screen.blit(self.font_small.render(f"分数: {self.score}", True, WHITE), (10, 10))
        self.screen.blit(self.font_small.render(f"等级: {self.level}", True, GOLD), (10, 35))
        self.screen.blit(self.font_small.render(f"蛇长: {len(self.snake.body)}", True, GREEN), (10, 60))

        bw, bh = 200, 16
        pygame.draw.rect(self.screen, DARK_GRAY, (10, 90, bw, bh))
        pygame.draw.rect(self.screen, RED, (10, 90, int(bw * max(0, self.snake.health / self.snake.max_health)), bh))
        pygame.draw.rect(self.screen, WHITE, (10, 90, bw, bh), 1)
        self.screen.blit(self.font_tiny.render("生命", True, WHITE), (bw + 15, 90))

        pygame.draw.rect(self.screen, DARK_GRAY, (10, 112, bw, 12))
        pygame.draw.rect(self.screen, BLUE, (10, 112, int(bw * (self.xp / self.xp_to_next)), 12))
        pygame.draw.rect(self.screen, WHITE, (10, 112, bw, 12), 1)
        self.screen.blit(self.font_tiny.render("经验", True, WHITE), (bw + 15, 112))

        pygame.draw.rect(self.screen, DARK_GRAY, (10, 130, 150, 10))
        pygame.draw.rect(self.screen, YELLOW, (10, 130, int(150 * (self.snake.stamina / self.snake.max_stamina)), 10))
        pygame.draw.rect(self.screen, WHITE, (10, 130, 150, 10), 1)
        self.screen.blit(self.font_tiny.render("体力", True, WHITE), (165, 128))

        ms = 150
        mm = pygame.Surface((ms, ms))
        mm.fill((20, 20, 30))
        pygame.draw.rect(mm, GRAY, (0, 0, ms, ms), 2)
        sx2, sy2 = ms / MAP_WIDTH, ms / MAP_HEIGHT
        for w in self.hazards.walls:
            pygame.draw.rect(mm, GRAY, (int(w.rect.x * sx2), int(w.rect.y * sy2),
                                        max(1, int(w.rect.width * sx2)), max(1, int(w.rect.height * sy2))))
        for f in self.foods:
            pygame.draw.circle(mm, GREEN, (int(f.x * sx2), int(f.y * sy2)), 2)
        for e in self.enemies.enemies:
            pygame.draw.circle(mm, RED, (int(e.x * sx2), int(e.y * sy2)), 3)
        pygame.draw.circle(mm, (100, 200, 100), (int(self.snake.x * sx2), int(self.snake.y * sy2)), 4)
        self.screen.blit(mm, (SCREEN_WIDTH - ms - 10, 10))

        f5t = self.font_tiny.render("按F5显示游戏用户日志", True, LIGHT_GRAY)
        self.screen.blit(f5t, (SCREEN_WIDTH - ms - 10, ms + 15))
        ct = self.font_tiny.render("T:技能 P:暂停 ESC:菜单", True, GRAY)
        self.screen.blit(ct, (SCREEN_WIDTH - 220, SCREEN_HEIGHT - 25))

    def _draw_overlay_text(self, title, subtitle, bg_color=(0, 0, 0, 200)):
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill(bg_color)
        self.screen.blit(ov, (0, 0))
        t = self.font_large.render(title, True, WHITE)
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30)))
        s = self.font_medium.render(subtitle, True, LIGHT_GRAY)
        self.screen.blit(s, s.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)))

    def _draw_skill_tree(self):
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 220))
        self.screen.blit(ov, (0, 0))
        self.screen.blit(self.font_large.render("技能树", True, GOLD),
                         self.font_large.render("技能树", True, GOLD).get_rect(center=(SCREEN_WIDTH // 2, 80)))
        pt = self.font_medium.render(f"技能点: {self.skill_points}", True, WHITE)
        self.screen.blit(pt, pt.get_rect(center=(SCREEN_WIDTH // 2, 140)))

        skills = [
            ("1. 九头蛇 (Hydra)", "添加额外的蛇头", self.skills["hydra"]),
            ("2. 泰坦 (Titanic)", "增大体型, 可碾碎障碍物", self.skills["titanic"]),
            ("3. 相位转移 (Phase Shift)", f"临时无敌 (等级: {self.skills['phase_shift']}/3)", self.skills["phase_shift"] > 0),
            ("4. 磁铁 (Magnet)", "自动吸引食物", self.skills["magnet"]),
        ]
        y = 200
        for name, desc, unlocked in skills:
            c = GREEN if unlocked else LIGHT_GRAY
            self.screen.blit(self.font_small.render(name, True, c), (100, y))
            self.screen.blit(self.font_tiny.render(desc, True, GRAY), (100, y + 28))
            y += 70
        self.screen.blit(self.font_tiny.render("按 T 或 ESC 关闭", True, LIGHT_GRAY),
                         self.font_tiny.render("按 T 或 ESC 关闭", True, LIGHT_GRAY).get_rect(
                             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50)))

    def _draw_gameover(self):
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 220))
        self.screen.blit(ov, (0, 0))
        self.screen.blit(self.font_large.render("游戏结束!", True, RED),
                         self.font_large.render("游戏结束!", True, RED).get_rect(
                             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3)))
        self.screen.blit(self.font_medium.render(f"最终分数: {self.score}", True, WHITE),
                         self.font_medium.render(f"最终分数: {self.score}", True, WHITE).get_rect(
                             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
        if self.score >= self.high_score and self.score > 0:
            self.screen.blit(self.font_medium.render("🎉 新纪录! 🎉", True, GOLD),
                             self.font_medium.render("🎉 新纪录! 🎉", True, GOLD).get_rect(
                                 center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)))
        self.screen.blit(self.font_small.render("按 R 重新开始 | ESC 返回菜单", True, LIGHT_GRAY),
                         self.font_small.render("按 R 重新开始 | ESC 返回菜单", True, LIGHT_GRAY).get_rect(
                             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT * 3 // 4)))

    def _draw_log_screen(self):
        self.screen.fill(DARK_BG)
        self.screen.blit(self.font_large.render("游戏用户日志", True, GOLD),
                         self.font_large.render("游戏用户日志", True, GOLD).get_rect(center=(SCREEN_WIDTH // 2, 50)))

        headers = ["ID", "用户名", "开始时间", "持续时长(秒)", "得分"]
        col_x = [50, 120, 250, 550, 750]
        y = 110
        for i, h in enumerate(headers):
            self.screen.blit(self.font_small.render(h, True, CYAN), (col_x[i], y))
        pygame.draw.line(self.screen, GRAY, (40, y + 28), (SCREEN_WIDTH - 40, y + 28))

        logs = self.data_mgr.get_logs()
        visible = logs[self.log_scroll:]
        y = 145
        for entry in visible:
            if y > SCREEN_HEIGHT - 80:
                break
            vals = [
                str(entry.get("id", "")),
                str(entry.get("username", "")),
                str(entry.get("start_time", "")),
                str(entry.get("duration_sec", "")),
                str(entry.get("score", "")),
            ]
            for i, v in enumerate(vals):
                self.screen.blit(self.font_tiny.render(v, True, WHITE), (col_x[i], y))
            y += 28

        if self.log_from_menu:
            hint = "↑↓ 翻页 | ESC 返回主菜单"
        else:
            hint = "↑↓ 翻页 | ESC/F5 返回游戏"
        self.screen.blit(self.font_tiny.render(hint, True, LIGHT_GRAY),
                         self.font_tiny.render(hint, True, LIGHT_GRAY).get_rect(
                             center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30)))

    # ---------- 主循环 ----------

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()


if __name__ == "__main__":
    game = Game()
    game.run()
