"""
MINI-DOOM  --  a Doom-style raycasting shooter in pure Python + pygame.

Install:  pip install pygame
Run:      python doom.py

Controls
  W A S D / arrows   move & strafe / turn        Mouse    turn
  Shift              run                         E        open doors / use exit switch
  Space / Ctrl / LMB fire (hold to auto-fire)    1 / 2    pistol / shotgun (mouse wheel too)
  R                  restart after death/win     Esc      quit

Kill (or dodge) the imps and demons, grab the shotgun, then find the EXIT switch.
Everything (textures, monsters, weapons, sounds) is generated in code - no asset files.
"""
import array
import math
import random
import sys

import pygame

# ------------------------------------------------------------------ config
SCREEN_W, SCREEN_H = 960, 540
HUD_H = 60
VIEW_SCALE = 2                                  # render low-res, scale up: chunky retro look
RW, RH = SCREEN_W // VIEW_SCALE, (SCREEN_H - HUD_H) // VIEW_SCALE   # 480 x 240
HALF = RH // 2
FOV = math.radians(66)
PLANE_K = math.tan(FOV / 2)
FOCAL = RW / (2 * PLANE_K)                      # pixels per world unit at distance 1
TEX = 64
SHADES = 8

WALLCH = set("#$%DX")
TEXMAP = {"#": "brick", "$": "tech", "%": "stone", "D": "door", "X": "exit"}

# legend: # brick  $ tech  % stone  D door  X exit switch  P player
#         I imp  M demon  h medkit  a ammo  s shotgun
LEVEL = [
    "#####################X##",
    "#.....#............#...#",
    "#.P...#.....I......#...#",
    "#.....D............D...#",
    "#.....#............#.M.#",
    "#.....#............#...#",
    "#######............#####",
    "#.....#............#..a#",
    "#.h...#..$$....$$..#...#",
    "#.....D............D...#",
    "#...s.#..$$....$$..#.I.#",
    "#.....#............#...#",
    "#######............#####",
    "#......................#",
    "#...%%.....M....%%.....#",
    "#..I.....h.......I.....#",
    "#...%%..........%%.....#",
    "#......a.........M.....#",
    "#......................#",
    "########################",
]

SPEC = {
    "imp":   dict(hp=60,  speed=1.5, ranged=True,  mdmg=8,  mcd=1.0),
    "demon": dict(hp=150, speed=2.7, ranged=False, mdmg=18, mcd=0.8),
}
FRAMES = ["walk0", "walk1", "attack", "pain", "die0", "die1", "die2"]


def clamp(v, a, b):
    return a if v < a else b if v > b else v


# ------------------------------------------------------------ procedural art
def noise(surf, rng, n, amt):
    w, h = surf.get_size()
    for _ in range(n):
        x, y = rng.randrange(w), rng.randrange(h)
        r, g, b, _a = surf.get_at((x, y))
        d = rng.randint(-amt, amt)
        surf.set_at((x, y), (clamp(r + d, 0, 255), clamp(g + d, 0, 255), clamp(b + d, 0, 255)))


def tex_brick(rng):
    s = pygame.Surface((TEX, TEX))
    s.fill((50, 32, 28))
    for row in range(4):
        off = 0 if row % 2 == 0 else 16
        for bx in range(-1, 3):
            x = bx * 32 + off
            base = rng.randint(115, 160)
            col = (base, base * 45 // 100, base * 30 // 100)
            pygame.draw.rect(s, col, (x + 1, row * 16 + 1, 30, 14))
            pygame.draw.line(s, (min(255, base + 35), base * 6 // 10, base * 4 // 10), (x + 1, row * 16 + 1), (x + 30, row * 16 + 1))
            pygame.draw.line(s, (base // 2, base // 5, base // 7), (x + 1, row * 16 + 14), (x + 30, row * 16 + 14))
    noise(s, rng, 500, 18)
    return s


def tex_tech(rng):
    s = pygame.Surface((TEX, TEX))
    s.fill((84, 90, 102))
    pygame.draw.rect(s, (52, 57, 68), (0, 0, TEX, TEX), 2)
    pygame.draw.rect(s, (62, 67, 78), (5, 5, 22, 54), 1)
    pygame.draw.rect(s, (30, 34, 42), (34, 8, 24, 12))
    for i in range(5):
        pygame.draw.rect(s, (70, 230, 255) if i % 2 == 0 else (30, 120, 140), (36 + i * 4, 10, 3, 8))
    for i in range(5):
        pygame.draw.line(s, (50, 55, 64), (34, 28 + i * 5), (58, 28 + i * 5), 2)
    pygame.draw.circle(s, (230, 40, 40), (46, 54), 3)
    for (x, y) in ((4, 4), (59, 4), (4, 59), (59, 59)):
        pygame.draw.circle(s, (40, 44, 52), (x, y), 2)
    noise(s, rng, 350, 12)
    return s


def tex_stone(rng):
    s = pygame.Surface((TEX, TEX))
    s.fill((30, 50, 32))
    for row in range(4):
        off = 0 if row % 2 == 0 else 20
        for bx in range(-1, 3):
            x = bx * 40 + off
            g = rng.randint(85, 125)
            pygame.draw.rect(s, (g * 55 // 100, g, g * 55 // 100), (x + 1, row * 16 + 1, 38, 14))
    noise(s, rng, 700, 22)
    return s


def tex_door(rng):
    s = pygame.Surface((TEX, TEX))
    s.fill((112, 114, 124))
    for x in range(0, TEX, 16):
        pygame.draw.rect(s, (88, 90, 100), (x, 0, 16, TEX), 1)
        pygame.draw.line(s, (150, 152, 162), (x + 1, 1), (x + 1, TEX - 10))
    for x in range(0, TEX, 16):
        pygame.draw.rect(s, (235, 200, 30) if (x // 16) % 2 == 0 else (30, 30, 30), (x, TEX - 10, 16, 10))
    pygame.draw.rect(s, (60, 60, 68), (TEX // 2 - 3, 26, 6, 12))
    noise(s, rng, 250, 10)
    return s


def tex_exit():
    s = pygame.Surface((TEX, TEX))
    s.fill((26, 26, 34))
    pygame.draw.rect(s, (200, 30, 30), (3, 3, TEX - 6, TEX - 6), 2)
    f = pygame.font.Font(None, 28)
    t = f.render("EXIT", True, (255, 60, 50))
    s.blit(t, ((TEX - t.get_width()) // 2, 14))
    pygame.draw.polygon(s, (60, 255, 90), [(18, 42), (46, 42), (32, 56)])
    return s


def make_monster(kind, frame):
    S = pygame.Surface((64, 64), pygame.SRCALPHA)
    if frame.startswith("die"):
        k = int(frame[3])
        base = make_monster(kind, "pain")
        hs = (50, 32, 14)[k]
        w = 64 + k * 6
        sq = pygame.transform.scale(base, (w, hs))
        if k == 2:
            pygame.draw.ellipse(S, (120, 0, 0, 255), (6, 52, 52, 12))
        S.blit(sq, ((64 - w) // 2, 64 - hs))
        return S
    imp = kind == "imp"
    skin = (165, 100, 58) if imp else (210, 112, 130)
    dark = (104, 60, 34) if imp else (140, 62, 84)
    bw = 26 if imp else 40
    cx = 32
    walk1 = frame == "walk1"
    l0 = 47 + (0 if walk1 else 3)
    l1 = 47 + (3 if walk1 else 0)
    pygame.draw.rect(S, dark, (cx - bw // 2 + 3, l0, 10, 64 - l0))
    pygame.draw.rect(S, dark, (cx + bw // 2 - 13, l1, 10, 64 - l1))
    pygame.draw.ellipse(S, skin, (cx - bw // 2, 22, bw, 34))
    pygame.draw.arc(S, dark, (cx - bw // 2 + 4, 30, bw - 8, 20), 0, math.pi, 2)
    ax, bx = cx - bw // 2, cx + bw // 2
    pygame.draw.line(S, skin, (ax + 2, 28), (ax - 6, 44), 6)
    if frame == "attack" and imp:
        pygame.draw.line(S, skin, (bx - 2, 28), (bx + 8, 12), 6)
        pygame.draw.circle(S, (255, 140, 20), (bx + 9, 9), 7)
        pygame.draw.circle(S, (255, 240, 120), (bx + 9, 9), 3)
    else:
        pygame.draw.line(S, skin, (bx - 2, 28), (bx + 6, 44), 6)
    hy, hr = (16, 10) if imp else (21, 14)
    pygame.draw.circle(S, skin, (cx, hy), hr)
    horn = (232, 222, 190)
    pygame.draw.polygon(S, horn, [(cx - hr + 1, hy - 4), (cx - hr - 4, hy - 14), (cx - hr + 6, hy - 8)])
    pygame.draw.polygon(S, horn, [(cx + hr - 1, hy - 4), (cx + hr + 4, hy - 14), (cx + hr - 6, hy - 8)])
    ey = hy - 3
    pygame.draw.rect(S, (255, 235, 40), (cx - 7, ey, 5, 3))
    pygame.draw.rect(S, (255, 235, 40), (cx + 2, ey, 5, 3))
    my = hy + 4
    if frame == "attack" and not imp:
        pygame.draw.ellipse(S, (70, 0, 0), (cx - 9, my - 2, 18, 11))
    else:
        pygame.draw.rect(S, (70, 0, 0), (cx - 6, my, 12, 3))
    if not imp:
        for i in range(5):
            pygame.draw.rect(S, (245, 245, 235), (cx - 8 + i * 4, my, 2, 3))
    if frame == "pain":
        S.fill((70, 60, 60, 0), special_flags=pygame.BLEND_RGB_ADD)
    return S


def make_fireball():
    S = pygame.Surface((64, 64), pygame.SRCALPHA)
    for r, c in ((28, (200, 40, 0, 150)), (20, (255, 110, 0, 255)), (12, (255, 200, 60, 255)), (5, (255, 255, 210, 255))):
        pygame.draw.circle(S, c, (32, 32), r)
    return S


def make_item(kind):
    S = pygame.Surface((64, 64), pygame.SRCALPHA)
    if kind == "h":
        pygame.draw.rect(S, (235, 235, 235), (12, 38, 40, 24))
        pygame.draw.rect(S, (60, 60, 60), (12, 38, 40, 24), 2)
        pygame.draw.rect(S, (200, 20, 20), (29, 41, 6, 18))
        pygame.draw.rect(S, (200, 20, 20), (22, 47, 20, 6))
    elif kind == "a":
        pygame.draw.rect(S, (100, 96, 40), (14, 44, 36, 18))
        pygame.draw.rect(S, (50, 48, 20), (14, 44, 36, 18), 2)
        for i in range(6):
            pygame.draw.rect(S, (235, 190, 60), (18 + i * 5, 38, 3, 8))
    else:
        pygame.draw.line(S, (110, 110, 118), (6, 52), (58, 46), 5)
        pygame.draw.line(S, (110, 110, 118), (6, 56), (58, 50), 4)
        pygame.draw.line(S, (130, 78, 36), (6, 54), (24, 60), 8)
        pygame.draw.line(S, (130, 78, 36), (30, 51), (42, 49), 6)
    return S


def make_bg():
    s = pygame.Surface((RW, RH))
    for y in range(HALF):
        t = y / HALF
        pygame.draw.line(s, (int(22 + 34 * t), int(20 + 30 * t), int(26 + 32 * t)), (0, y), (RW, y))
        pygame.draw.line(s, (int(38 + 70 * t), int(34 + 62 * t), int(30 + 54 * t)), (0, RH - 1 - (HALF - 1 - y)), (RW, RH - 1 - (HALF - 1 - y)))
    return s


# -------------------------------------------------------------------- sound
RATE = 22050


def synth(dur, f0, f1, noise_mix, vol, decay=2.0, lp=0.0):
    n = int(RATE * dur)
    out = array.array("h")
    phase = prev = 0.0
    for i in range(n):
        t = i / n
        phase += 2 * math.pi * (f0 + (f1 - f0) * t) / RATE
        s = math.sin(phase) * (1 - noise_mix) + random.uniform(-1, 1) * noise_mix
        if lp:
            prev += (s - prev) * lp
            s = prev
        s *= ((1 - t) ** decay) * vol
        out.append(int(clamp(s, -1, 1) * 32767))
    return pygame.mixer.Sound(buffer=out.tobytes())


def make_sounds():
    try:
        pygame.mixer.init(RATE, -16, 1, 512)
        return {
            "pistol": synth(0.18, 900, 200, 0.75, 0.8, 3),
            "shotgun": synth(0.45, 170, 40, 0.9, 1.0, 2, lp=0.3),
            "fireball": synth(0.35, 600, 150, 0.4, 0.5),
            "hurt": synth(0.25, 140, 80, 0.3, 0.9, 1.5),
            "pickup": synth(0.15, 600, 1200, 0.0, 0.4, 1),
            "door": synth(0.5, 70, 50, 0.5, 0.7, 1, lp=0.2),
            "death": synth(0.5, 300, 60, 0.5, 0.8, 1.5),
            "claw": synth(0.15, 200, 100, 0.8, 0.7, 2),
            "click": synth(0.05, 1500, 1500, 0.5, 0.4, 2),
        }
    except Exception:
        return {}


class Assets:
    def __init__(self):
        rng = random.Random(7)
        base = {"brick": tex_brick(rng), "tech": tex_tech(rng), "stone": tex_stone(rng),
                "door": tex_door(rng), "exit": tex_exit()}
        factors = [1.0, .84, .70, .58, .47, .37, .28, .2]
        self.tex = {}
        for name, t in base.items():
            lst = []
            for f in factors:
                c = t.copy()
                v = int(255 * f)
                c.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
                lst.append(c)
            self.tex[name] = lst
        self.mon = {k: {fr: make_monster(k, fr) for fr in FRAMES} for k in ("imp", "demon")}
        self.items = {k: make_item(k) for k in "has"}
        self.fireball = make_fireball()
        self.bg = make_bg()
        self.snd = make_sounds()
        self.red = pygame.Surface((RW, RH))
        self.red.fill((200, 0, 0))
        self.gold = pygame.Surface((RW, RH))
        self.gold.fill((230, 200, 60))
        self.black = pygame.Surface((SCREEN_W, SCREEN_H))
        self.black.fill((0, 0, 0))

    def play(self, name):
        s = self.snd.get(name)
        if s:
            s.play()


# --------------------------------------------------------------------- game
class Game:
    def __init__(self, assets):
        self.A = assets
        self.view = pygame.Surface((RW, RH))
        self.reset()
        self.state = "title"

    def reset(self):
        self.grid = [list(r) for r in LEVEL]
        self.NY, self.NX = len(self.grid), len(self.grid[0])
        self.enemies, self.items, self.fireballs, self.doors = [], [], [], {}
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                cx, cy = x + 0.5, y + 0.5
                if ch == "P":
                    self.px, self.py = cx, cy
                elif ch in "IM":
                    kind = "imp" if ch == "I" else "demon"
                    self.enemies.append(dict(kind=kind, x=cx, y=cy, hp=SPEC[kind]["hp"], state="idle",
                                             timer=0.0, cd=random.uniform(0.5, 1.5), anim=random.random() * 3,
                                             melee=False))
                elif ch in "has":
                    self.items.append(dict(kind=ch, x=cx, y=cy, taken=False))
                elif ch == "D":
                    self.doors[(x, y)] = dict(o=0.0, dir=0, hold=0.0)
                if ch in "PIMhas":
                    self.grid[y][x] = "."
        self.pa = 0.35
        self.hp = 100
        self.ammo = {"bull": 50, "shel": 0}
        self.have = [True, False]
        self.weapon = 0
        self.fire_t = 0.0
        self.cool = 0.4
        self.bob = 0.0
        self.moving = False
        self.hurt_t = 0.0
        self.pickup_t = 0.0
        self.face_look = 0
        self.grin_t = 0.0
        self.kills = 0
        self.total = len(self.enemies)
        self.time = 0.0
        self.msg, self.msg_t = "", 0.0

    def start(self):
        self.reset()
        self.state = "play"
        self.say("Find the EXIT.  Doors: E")

    def say(self, text):
        self.msg, self.msg_t = text, 3.0

    # ---------------------------------------------------------- world helpers
    def tile(self, x, y):
        ix, iy = int(math.floor(x)), int(math.floor(y))
        if ix < 0 or iy < 0 or ix >= self.NX or iy >= self.NY:
            return "#"
        return self.grid[iy][ix]

    def solid(self, x, y):
        ch = self.tile(x, y)
        if ch == "D":
            return self.doors[(int(x), int(y))]["o"] < 0.9
        return ch in WALLCH

    def blocked(self, x, y, r):
        return (self.solid(x - r, y - r) or self.solid(x + r, y - r) or
                self.solid(x - r, y + r) or self.solid(x + r, y + r))

    def los(self, x0, y0, x1, y1):
        d = math.hypot(x1 - x0, y1 - y0)
        n = int(d / 0.15) + 1
        for i in range(1, n):
            t = i / n
            if self.solid(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
                return False
        return True

    def cast(self, dx, dy, render=False):
        px, py = self.px, self.py
        mx, my = int(px), int(py)
        ddx = abs(1 / dx) if dx else 1e30
        ddy = abs(1 / dy) if dy else 1e30
        if dx < 0:
            stepx, sdx = -1, (px - mx) * ddx
        else:
            stepx, sdx = 1, (mx + 1 - px) * ddx
        if dy < 0:
            stepy, sdy = -1, (py - my) * ddy
        else:
            stepy, sdy = 1, (my + 1 - py) * ddy
        door = None
        grid = self.grid
        side, dist = 0, 0.0
        while True:
            if sdx < sdy:
                sdx += ddx
                mx += stepx
                side, dist = 0, sdx - ddx
            else:
                sdy += ddy
                my += stepy
                side, dist = 1, sdy - ddy
            if mx < 0 or my < 0 or mx >= self.NX or my >= self.NY:
                return 99.0, side, "#", 0.0, None
            ch = grid[my][mx]
            if ch in WALLCH:
                wx = (py + dist * dy) if side == 0 else (px + dist * dx)
                wx -= math.floor(wx)
                if (side == 0 and dx > 0) or (side == 1 and dy < 0):
                    wx = 1 - wx
                if ch == "D":
                    o = self.doors[(mx, my)]["o"]
                    if o >= 0.98:
                        continue
                    if render and o > 0.02:
                        if door is None:
                            door = (dist, side, wx, o)
                        continue
                return dist, side, ch, wx, door

    # --------------------------------------------------------------- actions
    def switch(self, n):
        if self.state == "play" and self.have[n] and self.weapon != n:
            self.weapon = n
            self.fire_t = 0.15

    def use(self):
        if self.state != "play":
            return
        c, s = math.cos(self.pa), math.sin(self.pa)
        for dist in (0.6, 1.1, 1.6):
            tx, ty = int(self.px + c * dist), int(self.py + s * dist)
            ch = self.tile(tx, ty)
            if ch == "D":
                d = self.doors[(tx, ty)]
                if d["o"] >= 1:
                    d["hold"] = 4.0
                elif d["dir"] != 1:
                    d["dir"] = 1
                    self.A.play("door")
                return
            if ch == "X":
                self.state = "won"
                return
            if ch in WALLCH:
                return

    def hurt(self, n, fx, fy):
        if self.state != "play":
            return
        self.hp -= n
        self.hurt_t = 0.35
        rel = (math.atan2(fy - self.py, fx - self.px) - self.pa + math.pi) % (2 * math.pi) - math.pi
        self.face_look = -1 if rel < -0.3 else 1 if rel > 0.3 else 0
        self.A.play("hurt")
        if self.hp <= 0:
            self.hp = 0
            self.state = "dead"

    def hitscan(self, spread, dmg):
        a = self.pa + random.uniform(-spread, spread)
        dx, dy = math.cos(a), math.sin(a)
        bd = self.cast(dx, dy)[0]
        best = None
        for e in self.enemies:
            if e["state"] in ("dying", "dead"):
                continue
            ex, ey = e["x"] - self.px, e["y"] - self.py
            fwd = ex * dx + ey * dy
            if fwd <= 0 or fwd >= bd:
                continue
            if abs(ex * dy - ey * dx) < 0.28:
                best, bd = e, fwd
        if best:
            self.damage_enemy(best, dmg)

    def damage_enemy(self, e, dmg):
        e["hp"] -= dmg
        if e["state"] == "idle":
            e["state"] = "chase"
        if e["hp"] <= 0:
            e["state"], e["timer"] = "dying", 0.0
            self.kills += 1
            self.A.play("death")
        elif random.random() < 0.55 and e["state"] != "attack":
            e["state"], e["timer"] = "pain", 0.25

    def shoot(self):
        if self.fire_t > 0 or self.state != "play":
            return
        if self.weapon == 0:
            if self.ammo["bull"] <= 0:
                self.fire_t = self.cool = 0.3
                self.A.play("click")
                return
            self.ammo["bull"] -= 1
            self.fire_t = self.cool = 0.38
            self.A.play("pistol")
            self.hitscan(0.012, random.randint(14, 22))
        else:
            if self.ammo["shel"] <= 0:
                self.fire_t = self.cool = 0.3
                self.A.play("click")
                return
            self.ammo["shel"] -= 1
            self.fire_t = self.cool = 0.95
            self.A.play("shotgun")
            for _ in range(7):
                self.hitscan(0.09, 9)
        for e in self.enemies:                      # gunfire wakes the neighbourhood
            if e["state"] == "idle" and math.hypot(e["x"] - self.px, e["y"] - self.py) < 9:
                e["state"] = "chase"

    # ---------------------------------------------------------------- update
    def occupied(self, x, y):
        if abs(self.px - (x + .5)) < .8 and abs(self.py - (y + .5)) < .8:
            return True
        return any(e["state"] not in ("dying", "dead") and abs(e["x"] - (x + .5)) < .7 and abs(e["y"] - (y + .5)) < .7
                   for e in self.enemies)

    def update(self, dt, keys, mdx, fire):
        if self.state in ("play",):
            self.time += dt
        self.msg_t = max(0, self.msg_t - dt)
        self.hurt_t = max(0, self.hurt_t - dt)
        self.pickup_t = max(0, self.pickup_t - dt)
        self.grin_t = max(0, self.grin_t - dt)
        if self.state == "dead":
            return
        for (x, y), d in self.doors.items():
            if d["dir"] == 1:
                d["o"] = min(1.0, d["o"] + dt * 1.8)
                if d["o"] >= 1:
                    d["dir"], d["hold"] = 0, 4.0
            elif d["dir"] == -1:
                if self.occupied(x, y):
                    d["dir"] = 1
                else:
                    d["o"] = max(0.0, d["o"] - dt * 1.8)
                    if d["o"] <= 0:
                        d["dir"] = 0
            elif d["o"] >= 1 and d["hold"] > 0:
                d["hold"] -= dt
                if d["hold"] <= 0:
                    d["dir"] = -1
        if self.state != "play":
            return

        self.pa += mdx * 0.0025
        if keys[pygame.K_LEFT]:
            self.pa -= 2.4 * dt
        if keys[pygame.K_RIGHT]:
            self.pa += 2.4 * dt
        c, s = math.cos(self.pa), math.sin(self.pa)
        mx = my = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            mx, my = mx + c, my + s
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            mx, my = mx - c, my - s
        if keys[pygame.K_a]:
            mx, my = mx + s, my - c
        if keys[pygame.K_d]:
            mx, my = mx - s, my + c
        n = math.hypot(mx, my)
        self.moving = n > 0
        if n:
            sp = 3.2 * (1.7 if keys[pygame.K_LSHIFT] else 1.0) * dt / n
            nx, ny = self.px + mx * sp, self.py + my * sp
            if not self.blocked(nx, self.py, 0.25):
                self.px = nx
            if not self.blocked(self.px, ny, 0.25):
                self.py = ny
            self.bob += dt * 10
        self.fire_t = max(0.0, self.fire_t - dt)
        if fire:
            self.shoot()

        for it in self.items:
            if it["taken"] or math.hypot(it["x"] - self.px, it["y"] - self.py) > 0.55:
                continue
            k = it["kind"]
            if k == "h":
                if self.hp >= 100:
                    continue
                self.hp = min(100, self.hp + 25)
                self.say("Picked up a medikit.")
            elif k == "a":
                self.ammo["bull"] = min(200, self.ammo["bull"] + 15)
                self.ammo["shel"] = min(50, self.ammo["shel"] + 4)
                self.say("Picked up ammo.")
            else:
                self.have[1] = True
                self.ammo["shel"] = min(50, self.ammo["shel"] + 8)
                self.weapon = 1
                self.say("You got the SHOTGUN!  (1/2 switch)")
                self.grin_t = 2.0
            it["taken"] = True
            self.pickup_t = 0.18
            self.A.play("pickup")

        for e in self.enemies:
            self.update_enemy(e, dt)
        for fb in self.fireballs[:]:
            fb["x"] += fb["vx"] * dt
            fb["y"] += fb["vy"] * dt
            if self.solid(fb["x"], fb["y"]):
                self.fireballs.remove(fb)
            elif math.hypot(fb["x"] - self.px, fb["y"] - self.py) < 0.45:
                self.fireballs.remove(fb)
                self.hurt(random.randint(10, 16), fb["x"], fb["y"])
        if int(self.time * 0.5) % 4 == 0 and self.hurt_t <= 0 and not self.grin_t:
            self.face_look = 0

    def update_enemy(self, e, dt):
        st = e["state"]
        if st == "dying":
            e["timer"] += dt
            if e["timer"] > 0.54:
                e["state"] = "dead"
            return
        if st == "dead":
            return
        dx, dy = self.px - e["x"], self.py - e["y"]
        d = math.hypot(dx, dy) or 1e-6
        cfg = SPEC[e["kind"]]
        if st == "idle":
            if d < 14 and self.los(e["x"], e["y"], self.px, self.py):
                e["state"] = "chase"
            return
        e["cd"] -= dt
        if st == "pain":
            e["timer"] -= dt
            if e["timer"] <= 0:
                e["state"] = "chase"
            return
        if st == "attack":
            e["timer"] -= dt
            if e["timer"] <= 0:
                if e["melee"]:
                    if d < 1.6:
                        self.A.play("claw")
                        self.hurt(cfg["mdmg"], e["x"], e["y"])
                else:
                    v = 5.0
                    self.fireballs.append(dict(x=e["x"], y=e["y"], vx=dx / d * v, vy=dy / d * v))
                    self.A.play("fireball")
                e["state"] = "chase"
                e["cd"] = cfg["mcd"] if e["melee"] else random.uniform(1.4, 2.4)
            return
        if d > 0.9:                                  # chase
            sp = cfg["speed"] * dt
            nx, ny = e["x"] + dx / d * sp, e["y"] + dy / d * sp
            moved = False
            if not self.blocked(nx, e["y"], 0.28):
                e["x"], moved = nx, True
            if not self.blocked(e["x"], ny, 0.28):
                e["y"], moved = ny, True
            if moved:
                e["anim"] += dt * 2.4
        if e["cd"] <= 0:
            if d < 1.3:
                e["state"], e["timer"], e["melee"] = "attack", 0.35, True
            elif cfg["ranged"] and d < 12 and self.los(e["x"], e["y"], self.px, self.py):
                e["state"], e["timer"], e["melee"] = "attack", 0.5, False

    # ------------------------------------------------------------- rendering
    def draw_column(self, view, x, dist, side, name, wx, frac):
        line_h = FOCAL / dist
        tex = self.A.tex[name][min(SHADES - 1, int(dist * 0.5) + side)]
        tx = min(TEX - 1, int(wx * TEX))
        dst_y = HALF - line_h / 2
        dst_h = line_h * frac
        src_y = (1 - frac) * TEX
        src_h = TEX * frac
        if dst_y < 0:
            cut = -dst_y
            r = cut / dst_h
            src_y += src_h * r
            src_h -= src_h * r
            dst_h -= cut
            dst_y = 0
        if dst_y + dst_h > RH:
            over = dst_y + dst_h - RH
            src_h -= src_h * over / dst_h
            dst_h -= over
        if dst_h < 1:
            return
        sy = int(clamp(src_y, 0, TEX - 1))
        sh = int(clamp(src_h, 1, TEX - sy))
        col = tex.subsurface((tx, sy, 1, sh))
        view.blit(pygame.transform.scale(col, (1, max(1, int(dst_h)))), (x, int(dst_y)))

    def render_walls(self, view):
        dirx, diry = math.cos(self.pa), math.sin(self.pa)
        plx, ply = -diry * PLANE_K, dirx * PLANE_K
        zbuf = [99.0] * RW
        for x in range(RW):
            cx = 2 * x / RW - 1
            dist, side, ch, wx, door = self.cast(dirx + plx * cx, diry + ply * cx, True)
            dist = max(dist, 0.05)
            zbuf[x] = dist
            self.draw_column(view, x, dist, side, TEXMAP[ch], wx, 1.0)
            if door:
                self.draw_column(view, x, max(door[0], 0.05), door[1], "door", door[2], 1 - door[3])
        return zbuf

    def enemy_surf(self, e):
        st, k = e["state"], e["kind"]
        if st == "dying":
            fr = "die%d" % min(2, int(e["timer"] / 0.18))
        elif st == "dead":
            fr = "die2"
        elif st in ("pain", "attack"):
            fr = st
        else:
            fr = "walk%d" % (int(e["anim"] * 2) % 2) if st == "chase" else "walk0"
        return self.A.mon[k][fr]

    def render_sprites(self, view, zbuf):
        spr = []
        for e in self.enemies:
            spr.append((e["x"], e["y"], self.enemy_surf(e), 0.85 if e["kind"] == "imp" else 0.8, 0.0))
        for it in self.items:
            if not it["taken"]:
                spr.append((it["x"], it["y"], self.A.items[it["kind"]], 0.4, 0.0))
        for fb in self.fireballs:
            spr.append((fb["x"], fb["y"], self.A.fireball, 0.35, 0.3))
        spr.sort(key=lambda s: -((s[0] - self.px) ** 2 + (s[1] - self.py) ** 2))
        dirx, diry = math.cos(self.pa), math.sin(self.pa)
        for sx, sy, surf, hw, z in spr:
            rx, ry = sx - self.px, sy - self.py
            depth = dirx * rx + diry * ry
            if depth < 0.2:
                continue
            side = -diry * rx + dirx * ry            # +right
            scr = RW / 2 * (1 + side / (depth * PLANE_K))
            size = FOCAL / depth * hw
            bottom = HALF + FOCAL / depth * (0.5 - z)
            top = bottom - size
            x0 = int(scr - size / 2)
            x1 = int(scr + size / 2)
            ih = max(1, int(size))
            for xx in range(max(0, x0), min(RW, x1)):
                if depth < zbuf[xx]:
                    tc = clamp(int((xx - x0) / size * 64), 0, 63)
                    view.blit(pygame.transform.scale(surf.subsurface((tc, 0, 1, 64)), (1, ih)), (xx, int(top)))

    def draw_weapon(self, view):
        bx = RW // 2 + (math.sin(self.bob) * 6 if self.moving else 0)
        by = RH + (abs(math.cos(self.bob)) * 5 if self.moving else 0)
        frac = self.fire_t / self.cool if self.cool else 0
        skin, sleeve = (205, 150, 110), (58, 98, 58)
        if self.weapon == 0:
            rec = (frac ** 2) * 14 if frac > 0.8 else 0
            pygame.draw.rect(view, sleeve, (bx - 22, by - 16, 44, 30))
            pygame.draw.rect(view, skin, (bx - 13, by - 40 + rec, 26, 44))
            pygame.draw.rect(view, (70, 70, 78), (bx - 7, by - 64 + rec, 14, 34))
            pygame.draw.rect(view, (110, 110, 120), (bx - 5, by - 68 + rec, 10, 8))
            flash_y = by - 74 + rec
            flash = frac > 0.86
        else:
            rec = 10 * frac if frac > 0.7 else 0
            pump = 0
            if 0.15 < frac < 0.65:
                pump = math.sin((frac - 0.15) / 0.5 * math.pi) * 14
            pygame.draw.rect(view, sleeve, (bx - 22, by - 10 + rec, 44, 24))
            pygame.draw.rect(view, (60, 62, 68), (bx - 8, by - 96 + rec, 16, 84))
            pygame.draw.rect(view, (88, 90, 98), (bx - 8, by - 96 + rec, 5, 84))
            pygame.draw.rect(view, (125, 74, 34), (bx - 12, by - 58 + pump + rec, 24, 20))
            pygame.draw.rect(view, (82, 46, 20), (bx - 12, by - 58 + pump + rec, 24, 20), 2)
            pygame.draw.rect(view, skin, (bx - 13, by - 34 + rec, 26, 36))
            flash_y = by - 104 + rec
            flash = frac > 0.88
        if flash:
            pygame.draw.circle(view, (255, 190, 50), (bx, flash_y), 20 if self.weapon else 14)
            pygame.draw.circle(view, (255, 250, 200), (bx, flash_y), 10 if self.weapon else 7)

    def draw_face(self, screen, x, y):
        pygame.draw.rect(screen, (22, 18, 16), (x - 4, y - 3, 52, 57))
        pygame.draw.rect(screen, (110, 108, 100), (x - 4, y - 3, 52, 57), 2)
        dead = self.state == "dead"
        lvl = 0 if self.hp > 80 else 1 if self.hp > 60 else 2 if self.hp > 40 else 3 if self.hp > 20 else 4
        pygame.draw.ellipse(screen, (206, 156, 114) if not dead else (180, 130, 100), (x, y + 6, 44, 44))
        pygame.draw.ellipse(screen, (70, 44, 24), (x + 2, y, 40, 20))
        look = self.face_look if self.hurt_t > 0 else int(self.time) % 3 - 1 if self.state == "play" else 0
        for ex in (x + 9, x + 26):
            if dead:
                pygame.draw.line(screen, (30, 20, 20), (ex, y + 19), (ex + 8, y + 27), 2)
                pygame.draw.line(screen, (30, 20, 20), (ex + 8, y + 19), (ex, y + 27), 2)
            else:
                pygame.draw.rect(screen, (240, 240, 240), (ex, y + 20, 9, 7))
                pygame.draw.rect(screen, (30, 30, 30), (ex + 3 + look * 2, y + 21, 4, 5))
                pygame.draw.line(screen, (60, 36, 20), (ex - 1, y + 17 + (2 if lvl > 2 else 0)), (ex + 9, y + 17), 2)
        if dead:
            pygame.draw.rect(screen, (60, 10, 10), (x + 14, y + 38, 16, 5))
        elif self.grin_t > 0 or self.fire_t > self.cool * 0.5:
            pygame.draw.rect(screen, (245, 245, 240), (x + 11, y + 36, 22, 8))
            pygame.draw.rect(screen, (60, 10, 10), (x + 11, y + 36, 22, 8), 1)
        else:
            pygame.draw.rect(screen, (120, 40, 40), (x + 14, y + 39, 16, 3))
        blood = [(x + 5, y + 8, x + 12, y + 30), (x + 36, y + 12, x + 32, y + 36), (x + 18, y + 6, x + 22, y + 18),
                 (x + 30, y + 30, x + 38, y + 46)]
        for i in range(lvl + (1 if dead else 0)):
            a, b, c, d = blood[i % 4]
            pygame.draw.line(screen, (170, 10, 10), (a, b), (c, d), 3)

    def draw_hud(self, screen, f):
        y0 = RH * VIEW_SCALE
        pygame.draw.rect(screen, (58, 56, 52), (0, y0, SCREEN_W, HUD_H))
        pygame.draw.line(screen, (130, 128, 120), (0, y0), (SCREEN_W, y0), 2)

        def box(x, w, label, text, color=(210, 28, 28)):
            pygame.draw.rect(screen, (14, 12, 12), (x, y0 + 6, w, 48))
            pygame.draw.rect(screen, (110, 108, 100), (x, y0 + 6, w, 48), 2)
            screen.blit(f["tiny"].render(label, True, (170, 170, 160)), (x + 6, y0 + 8))
            t = f["big"].render(text, True, color)
            screen.blit(t, (x + w - t.get_width() - 8, y0 + 20))

        cur = self.ammo["bull"] if self.weapon == 0 else self.ammo["shel"]
        box(10, 130, "AMMO", str(cur))
        box(150, 150, "HEALTH", "%d%%" % self.hp)
        pygame.draw.rect(screen, (14, 12, 12), (310, y0 + 6, 100, 48))
        pygame.draw.rect(screen, (110, 108, 100), (310, y0 + 6, 100, 48), 2)
        screen.blit(f["tiny"].render("ARMS", True, (170, 170, 160)), (316, y0 + 8))
        for i in range(2):
            col = (240, 210, 40) if self.have[i] else (80, 80, 80)
            t = f["big"].render(str(i + 1), True, col)
            screen.blit(t, (326 + i * 40, y0 + 22))
            if self.weapon == i:
                pygame.draw.rect(screen, (240, 240, 240), (322 + i * 40, y0 + 20, 26, 30), 1)
        self.draw_face(screen, 458, y0 + 4)
        pygame.draw.rect(screen, (14, 12, 12), (530, y0 + 6, 200, 48))
        pygame.draw.rect(screen, (110, 108, 100), (530, y0 + 6, 200, 48), 2)
        for i, (nm, key, mx) in enumerate((("BULL", "bull", 200), ("SHEL", "shel", 50))):
            t = f["small"].render("%s  %3d / %d" % (nm, self.ammo[key], mx), True, (235, 205, 60))
            screen.blit(t, (540, y0 + 12 + i * 20))
        box(740, 100, "KILLS", "%d/%d" % (self.kills, self.total), (235, 205, 60))
        m, s = divmod(int(self.time), 60)
        box(850, 100, "TIME", "%d:%02d" % (m, s), (235, 205, 60))

    def draw(self, screen, f):
        v = self.view
        v.blit(self.A.bg, (0, 0))
        zbuf = self.render_walls(v)
        self.render_sprites(v, zbuf)
        if self.state != "title":
            self.draw_weapon(v)
        if self.hurt_t > 0:
            self.A.red.set_alpha(int(min(140, self.hurt_t * 380)))
            v.blit(self.A.red, (0, 0))
        if self.pickup_t > 0:
            self.A.gold.set_alpha(int(self.pickup_t * 300))
            v.blit(self.A.gold, (0, 0))
        if self.state == "dead":
            self.A.red.set_alpha(120)
            v.blit(self.A.red, (0, 0))
        pygame.transform.scale(v, (SCREEN_W, RH * VIEW_SCALE), screen.subsurface((0, 0, SCREEN_W, RH * VIEW_SCALE)))
        if self.state != "title":
            pygame.draw.line(screen, (255, 255, 255), (SCREEN_W // 2 - 6, RH), (SCREEN_W // 2 + 6, RH), 1)
        self.draw_hud(screen, f)
        if self.msg_t > 0 and self.state == "play":
            for off, col in ((2, (0, 0, 0)), (0, (255, 235, 150))):
                screen.blit(f["small"].render(self.msg, True, col), (12 + off, 12 + off))

        def center(text, font, col, y):
            screen.blit(font.render(text, True, col), (SCREEN_W // 2 - font.size(text)[0] // 2, y))

        if self.state == "title":
            self.A.black.set_alpha(170)
            screen.blit(self.A.black, (0, 0))
            center("MINI-DOOM", f["huge"], (200, 20, 20), 90)
            for i, line in enumerate(("WASD move   Mouse turn   Space/LMB fire   E use door/exit   Shift run",
                                      "1/2 switch weapon      Find the EXIT switch (top right)",
                                      "Imps throw fireballs.  Demons bite.  Doors open with E.")):
                center(line, f["small"], (220, 220, 210), 230 + i * 28)
            center("PRESS ENTER", f["big"], (235, 205, 60), 360)
        elif self.state == "dead":
            center("YOU DIED", f["huge"], (230, 30, 30), 170)
            center("Press R to restart", f["big"], (240, 240, 240), 270)
        elif self.state == "won":
            self.A.black.set_alpha(150)
            screen.blit(self.A.black, (0, 0))
            m, s = divmod(int(self.time), 60)
            center("LEVEL COMPLETE", f["huge"], (80, 255, 120), 150)
            center("Kills %d/%d    Time %d:%02d" % (self.kills, self.total, m, s), f["big"], (240, 240, 240), 250)
            center("Press R to play again", f["small"], (235, 205, 60), 310)


# --------------------------------------------------------------------- main
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("MINI-DOOM")
    fonts = {"tiny": pygame.font.Font(None, 18), "small": pygame.font.Font(None, 26),
             "big": pygame.font.Font(None, 42), "huge": pygame.font.Font(None, 120)}
    game = Game(Assets())
    clock = pygame.time.Clock()
    while True:
        dt = min(clock.tick(60) / 1000, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if game.state == "title" and ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    game.start()
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    pygame.mouse.get_rel()
                elif ev.key == pygame.K_e:
                    game.use()
                elif ev.key == pygame.K_1:
                    game.switch(0)
                elif ev.key == pygame.K_2:
                    game.switch(1)
                elif ev.key == pygame.K_r and game.state in ("dead", "won"):
                    game.start()
            if ev.type == pygame.MOUSEWHEEL:
                game.switch(0 if ev.y < 0 else 1)
        mdx, _ = pygame.mouse.get_rel()
        keys = pygame.key.get_pressed()
        fire = game.state == "play" and (keys[pygame.K_SPACE] or keys[pygame.K_LCTRL] or pygame.mouse.get_pressed()[0])
        if game.state == "title":
            game.pa += dt * 0.25
        game.update(dt, keys, mdx, fire)
        game.draw(screen, fonts)
        pygame.display.flip()


if __name__ == "__main__":
    main()
