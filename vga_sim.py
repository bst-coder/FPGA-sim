#!/usr/bin/env python3
"""
vga_sim.py -- Generic DE1 VGA Simulator (QSF-style config)
"""
import os, re, sys
import tkinter as tk
from tkinter import messagebox

try:
    import numpy as np
    from PIL import Image, ImageTk
except ImportError:
    print("Missing: pip install numpy Pillow")
    sys.exit(1)

# Standard DE1 ports (for fallback checking)
DE1_STANDARD_PORTS = [
    "CLOCK_50", "KEY", "SW", "LEDR", "VGA_R", "VGA_G", "VGA_B", "VGA_HS", "VGA_VS"
]

DEFAULT_CONFIG_TEXT = """set_global_assignment -name TOP_LEVEL_ENTITY flappy_top

# Map simulator controls to your entity's ports
# Syntax: set_location_assignment <GUI_NODE> -to <VHDL_PORT> # Label
# GUI_NODE must be SW0..SW9, KEY0..KEY3, or LED0..LED9.
# VHDL_PORT is the name of the port in your entity.

set_location_assignment SW0 -to SW(0) # Speed[0]
set_location_assignment SW1 -to SW(1) # Speed[1]
set_location_assignment SW2 -to SW(2) # Hard Mode

set_location_assignment KEY0 -to KEY(0) # Reset
set_location_assignment KEY1 -to KEY(1) # Flap (Start)
set_location_assignment KEY2 -to KEY(2) # Flap (Start)

# LEDR is usually used for the score, but you can map it to anything:
set_location_assignment LED0 -to LEDR(0) # Score bit 0
set_location_assignment LED1 -to LEDR(1) # Score bit 1
"""

def find_vhd_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    for n in ("vhd", "VHD", "Vhd"):
        p = os.path.join(here, n)
        if os.path.isdir(p):
            return p
    return here

# ============================================================================
#  QSF-style Config Parser
# ============================================================================
def load_config(vhd_dir):
    cfg_path = os.path.join(vhd_dir, "config.txt")
    
    if not os.path.isfile(cfg_path):
        with open(cfg_path, "w") as f:
            f.write(DEFAULT_CONFIG_TEXT)

    config = {
        "entity": "flappy_top",
        "sw": {i: f"SW({i})" for i in range(10)},
        "key": {i: f"KEY({i})" for i in range(4)},
        "led": {i: f"LEDR({i})" for i in range(10)},
        "mapping": {}
    }

    if os.path.isfile(cfg_path):
        with open(cfg_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): 
                    continue
                
                # 1. Parse Top Level Entity
                m = re.search(r"set_global_assignment\s+-name\s+TOP_LEVEL_ENTITY\s+(\w+)", line, re.IGNORECASE)
                if m:
                    config["entity"] = m.group(1)
                    continue

                # 2. Parse Pin Mapping
                m = re.search(r"set_location_assignment\s+(\w+)\s+-to\s+([\w\(\)\[\]]+)(?:\s*#\s*(.*))?", line, re.IGNORECASE)
                if m:
                    gui_node = m.group(1).upper()
                    vhdl_port = m.group(2)
                    label = m.group(3).strip() if m.group(3) else vhdl_port
                    
                    node_match = re.match(r"(SW|KEY|LED)(\d+)", gui_node)
                    if node_match:
                        prefix, idx_str = node_match.groups()
                        idx = int(idx_str)
                        if prefix == "SW" and idx < 10:
                            config["sw"][idx] = label
                            config["mapping"][f"SW{idx}"] = vhdl_port
                        elif prefix == "KEY" and idx < 4:
                            config["key"][idx] = label
                            config["mapping"][f"KEY{idx}"] = vhdl_port
                        elif prefix == "LED" and idx < 10:
                            config["led"][idx] = label
                            config["mapping"][f"LED{idx}"] = vhdl_port
    return config


# ============================================================================
#  VHDL validation
# ============================================================================
def parse_entity_ports(path):
    with open(path, "r", errors="ignore") as f:
        text = re.sub(r"--[^\n]*", "", f.read())
    m = re.search(r"\bport\s*\(", text, re.IGNORECASE)
    if not m: return {}
    start = m.end()
    depth = 1
    end = -1
    for i in range(start, len(text)):
        if text[i] == '(': depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                end = i; break
    if end == -1: return {}
    port_block = text[start:end]
    decls, depth, current = [], 0, ""
    for ch in port_block:
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == ';' and depth == 0:
            decls.append(current); current = ""
        else: current += ch
    if current.strip(): decls.append(current)
    ports = {}
    for decl in decls:
        decl = decl.strip()
        if ":" not in decl: continue
        names, tpart = decl.split(":", 1)
        dm = re.match(r"\s*(\w+)", tpart)
        if not dm or dm.group(1).lower() not in ("in", "out", "inout", "buffer"): continue
        direction = dm.group(1).lower()
        rest = tpart[dm.end():]
        wm = re.search(r"\(\s*(\d+)\s+downto\s+(\d+)\s*\)", rest)
        width = abs(int(wm.group(1)) - int(wm.group(2))) + 1 if wm else 1
        for n in (s.strip() for s in names.split(",")):
            if n: ports[n.upper()] = (direction, width)
    return ports

def validate_entity(vhd_dir, config):
    path = os.path.join(vhd_dir, config["entity"] + ".vhd")
    if not os.path.isfile(path):
        return None, f"File not found: {path}"
    ports = parse_entity_ports(path)
    if not ports:
        return None, "Could not parse VHDL ports."
    
    missing = []
    for node, port in config["mapping"].items():
        # Extract base port name (e.g. HEX3[6] -> HEX3, SW(0) -> SW)
        base_port = re.split(r'[\(\[]', port)[0].upper()
        if base_port not in ports:
            missing.append(f"{node} -> {port} (missing port {base_port})")
            
    if missing:
        return None, "Mapped ports not found in VHDL:\n" + "\n".join(missing)
    
    return ports, None

def ports_summary(name, config):
    lines = [f"Entity: {name}"]
    for node, port in config["mapping"].items():
        lines.append(f"  {node:4s} -> {port}")
    return "\n".join(lines)


# ============================================================================
#  vga_pattern logic
# ============================================================================
class VGAPattern:
    SQ = 64
    BAR_COLORS = np.array([[1,1,1],[1,1,0],[0,1,1],[0,1,0],[1,0,1],[1,0,0],[0,0,1],[0,0,0]], dtype=np.uint8)
    def __init__(self):
        self.sq_x, self.sq_y = 100, 60
        self.dx_pos = self.dy_pos = True
        self.scroll = 0

    def update(self, freeze, speed):
        if freeze: return
        step = (speed & 3) + 1
        if self.dx_pos:
            if self.sq_x + step >= 576: self.sq_x, self.dx_pos = 576, False
            else: self.sq_x += step
        else:
            if self.sq_x <= step: self.sq_x, self.dx_pos = 0, True
            else: self.sq_x -= step
        if self.dy_pos:
            if self.sq_y + step >= 416: self.sq_y, self.dy_pos = 416, False
            else: self.sq_y += step
        else:
            if self.sq_y <= step: self.sq_y, self.dy_pos = 0, True
            else: self.sq_y -= step
        self.scroll = (self.scroll + step) % 640

    def render(self, mode, csel, scroll_en, rows, cols):
        H, W = rows.shape
        cs = np.array([int(b) for b in csel], dtype=np.uint8)
        if mode == "00": return np.broadcast_to(cs, (H, W, 3)).copy()
        if mode == "01": return self.BAR_COLORS[np.clip(rows // 60, 0, 7)]
        if mode == "10": return self.BAR_COLORS[np.clip(cols // 80, 0, 7)]
        if scroll_en:
            s = (cols + self.scroll) % 640
            bg = self.BAR_COLORS[np.clip(s // 80, 0, 7)]
        else: bg = np.zeros((H, W, 3), dtype=np.uint8)
        sqc = np.array([1,1,1], dtype=np.uint8) if csel == "000" else cs
        in_sq = ((cols >= self.sq_x) & (cols < self.sq_x + self.SQ) & (rows >= self.sq_y) & (rows < self.sq_y + self.SQ))
        sq_col = (1 - bg) if scroll_en else np.broadcast_to(sqc, bg.shape)
        return np.where(in_sq[..., None], sq_col, bg)


# ============================================================================
#  flappy logic
# ============================================================================
SCREEN_W, SCREEN_H = 640, 480
GROUND_Y = 420
BIRD_X, BIRD_SIZE, HIT_MARGIN = 160, 32, 4
NUM_PIPES, PIPE_W, PIPE_SPACING = 3, 80, 256
PIPE_RING = NUM_PIPES * PIPE_SPACING
PIPE_X0 = 680
CAP_H, GAP_MIN_TOP = 24, 48
GAP_NORMAL, GAP_HARD = 150, 110

FRAC, GRAVITY, FLAP_VEL, HIT_VEL, VEL_MAX = 64, 22, -448, -160, 640
Y_MAX_Q = (GROUND_Y - BIRD_SIZE) * FRAC
BOB_BASE, OVER_LOCK = 208, 40

FONT_STRINGS = [
    "111101101101111","010110010010111","111001111100111","111001111001111",
    "101101111001001","111100111001111","111100111101111","111001001010010",
    "111101111101111","111101111001111","010101111101101","110101110101110",
    "111100110100111","111100110100100","111100101101111","101101110101101",
    "100100100100111","101111111101101","111101101101111","111101111100100",
    "110101110101101","111100111001111","111010010010010","101101101101010",
    "101101010010010","000000000000000","111100100100111",
]
FONT = np.zeros((27, 5, 3), dtype=bool)
for _i, _s in enumerate(FONT_STRINGS):
    _b = int(_s, 2)
    for _gy in range(5):
        for _gx in range(3):
            FONT[_i, _gy, _gx] = bool((_b >> (14 - (_gy * 3 + _gx))) & 1)

G_A, G_B, G_E, G_F, G_G, G_K, G_L = 10, 11, 12, 13, 14, 15, 16
G_M, G_O, G_P, G_R, G_S, G_T = 17, 18, 19, 20, 21, 22
G_V, G_Y, G_SPACE, G_C = 23, 24, 25, 26

SPRITES_OCTAL = [
    ["0000000000000000","0000000000000000","0000011110000000","0001122221111000",
     "0011117771333100","0116661221331100","1166666121331100","1166666122111110",
     "1216661222244441","1221112222244441","1222222222255551","0166666666655551",
     "0166666666661110","0011666666110000","0000111111000000","0000000000000000"],
    ["0000000000000000","0000000000000000","0000011110000000","0001122221111000",
     "0017777771333100","0177222221331100","1221112221331100","1216661222111110",
     "1166666122244441","1166666122244441","1216661222255551","0161116666655551",
     "0166666666661110","0011666666110000","0000111111000000","0000000000000000"],
    ["0000000000000000","0000000000000000","0000011110000000","0001122221111000",
     "0017777771333100","0177222221331100","1222222221331100","1222222222111110",
     "1221112222244441","1216661222244441","1166666122255551","0166666166655551",
     "0166666166661110","0011111666110000","0000111111000000","0000000000000000"],
    ["0000000000000000","0000000000000000","0000011110000000","0001122221111000",
     "0017777771131100","0177222221313100","1222222221131100","1222222222111110",
     "1221112222244441","1216661222244441","1166666122255551","0166666166655551",
     "0166666166661110","0011111666110000","0000111111000000","0000000000000000"],
]
SPRITES = np.array([[[int(ch, 8) for ch in row] for row in f] for f in SPRITES_OCTAL], dtype=np.uint8)
SPRITE_PALETTE = np.array([0x000,0x423,0xFC3,0xFFF,0xF72,0xE32,0xFEA,0xE91], dtype=np.uint16)

C_WHITE, C_TXT_SHADOW = 0xFFF, 0x222
C_SKY, C_CLOUD, C_CLOUD_SH = 0x4CD, 0xFFF, 0xCEF
C_HILL_RIM, C_HILL = 0x9E8, 0x7D6
C_PIPE_OUT, C_PIPE_LT, C_PIPE_MD, C_PIPE_DK = 0x342, 0xAE5, 0x7C2, 0x481
C_GROUND_LINE, C_GRASS_LT, C_GRASS_DK = 0x342, 0x9E3, 0x7C2
C_SAND, C_SAND_DK = 0xDD9, 0xBA6

def bcd_value(b): return b[2]*100 + b[1]*10 + b[0]
def bcd_inc(b):
    if b[2] == 9 and b[1] == 9 and b[0] == 9: return list(b)
    b = list(b)
    if b[0] < 9: b[0] += 1
    else:
        b[0] = 0
        if b[1] < 9: b[1] += 1
        else: b[1] = 0; b[2] += 1
    return b

class FlappyGame:
    def __init__(self): self.reset()
    def reset(self):
        self.st = "READY"
        self.y_q = BOB_BASE * FRAC
        self.vel_q = 0
        self.px = [PIPE_X0, PIPE_X0 + PIPE_SPACING, PIPE_X0 + 2*PIPE_SPACING]
        self.gt = [200, 200, 200]
        self.scored = [False]*NUM_PIPES
        self.gap_r = GAP_NORMAL
        self.spd_r = 2
        self.score_r = [0, 0, 0]
        self.best_r = [0, 0, 0]
        self.frame_cnt = 0
        self.anim = 0
        self.gnd = 0
        self.bg = 0
        self.flash_cnt = 0
        self.over_cnt = 0
        self.lfsr = 0xACE1ACE1

    def _lfsr_next(self):
        b = ((self.lfsr >> 31) ^ (self.lfsr >> 21) ^ (self.lfsr >> 1) ^ self.lfsr) & 1
        self.lfsr = ((self.lfsr << 1) | b) & 0xFFFFFFFF

    def _gap_from_lfsr(self, i):
        r = (self.lfsr >> (8 * i)) & 0xFF
        return GAP_MIN_TOP + r - r // 4

    def _hit_test(self, by):
        bl, br, bt, bb = BIRD_X + HIT_MARGIN, BIRD_X + BIRD_SIZE - HIT_MARGIN, by + HIT_MARGIN, by + BIRD_SIZE - HIT_MARGIN
        for i in range(NUM_PIPES):
            if self.px[i] < br and self.px[i] + PIPE_W > bl:
                if bt < self.gt[i] or bb > self.gt[i] + self.gap_r: return True
        return False

    def bird_y_int(self): return self.y_q // FRAC
    def bird_frame_int(self):
        if self.st in ("DEAD","OVER"): return 3
        b = (self.anim >> 1) & 3
        return 0 if b == 0 else 2 if b == 2 else 1
    def blink(self): return ((self.frame_cnt >> 5) & 1) == 1
    def flash(self): return self.flash_cnt > 0

    def tick(self, flap, speed_sel, hard_mode):
        self._lfsr_next()
        self.frame_cnt = (self.frame_cnt + 1) & 0xFF
        if self.flash_cnt > 0: self.flash_cnt -= 1
        if self.st == "READY":
            self.spd_r = 2 + speed_sel
            self.gap_r = GAP_HARD if hard_mode else GAP_NORMAL
            self.px = [PIPE_X0, PIPE_X0 + PIPE_SPACING, PIPE_X0 + 2*PIPE_SPACING]
            self.scored = [False]*NUM_PIPES
            self.score_r = [0, 0, 0]
            for i in range(NUM_PIPES): self.gt[i] = self._gap_from_lfsr(i)
            ph = self.frame_cnt & 0x3F
            y = ph if ph < 32 else 63 - ph
            self.y_q = (BOB_BASE + y) * FRAC
            self.vel_q = 0
            self.anim = (self.anim + 1) & 0xF
            self.gnd = (self.gnd + self.spd_r) & 0x3FF
            self.bg = (self.bg + self.spd_r // 2) & 0x1FF
            if flap:
                self.st = "PLAY"; self.vel_q = FLAP_VEL; self.anim = 4
        elif self.st == "PLAY":
            v = self.vel_q + GRAVITY
            if v > VEL_MAX: v = VEL_MAX
            if flap: v = FLAP_VEL; self.anim = 4
            else: self.anim = (self.anim + 1) & 0xF
            y = self.y_q + v
            if y < 0: y, v = 0, 0
            sc_v = list(self.score_r)
            for i in range(NUM_PIPES):
                nx = self.px[i] - self.spd_r
                if nx <= -PIPE_W:
                    nx += PIPE_RING
                    self.gt[i] = self._gap_from_lfsr(i)
                    self.scored[i] = False
                elif not self.scored[i] and nx + PIPE_W < BIRD_X:
                    self.scored[i] = True
                    sc_v = bcd_inc(sc_v)
                self.px[i] = nx
            self.score_r = sc_v
            self.gnd = (self.gnd + self.spd_r) & 0x3FF
            self.bg = (self.bg + self.spd_r // 2) & 0x1FF
            ended = False
            if y >= Y_MAX_Q:
                y, v = Y_MAX_Q, 0
                self.st = "OVER"; self.over_cnt = OVER_LOCK; self.flash_cnt = 4; ended = True
            elif self._hit_test(y // FRAC):
                v = HIT_VEL; self.st = "DEAD"; self.flash_cnt = 4; ended = True
            if ended and bcd_value(sc_v) > bcd_value(self.best_r): self.best_r = list(sc_v)
            self.y_q, self.vel_q = y, v
        elif self.st == "DEAD":
            v = min(self.vel_q + GRAVITY, VEL_MAX)
            y = self.y_q + v
            if y < 0: y, v = 0, 0
            if y >= Y_MAX_Q:
                y, v = Y_MAX_Q, 0
                self.st = "OVER"; self.over_cnt = OVER_LOCK
            self.y_q, self.vel_q = y, v
        elif self.st == "OVER":
            if self.over_cnt > 0: self.over_cnt -= 1
            elif flap:
                self.st = "READY"
                self.px = [PIPE_X0, PIPE_X0 + PIPE_SPACING, PIPE_X0 + 2*PIPE_SPACING]
                self.y_q = BOB_BASE * FRAC
                self.vel_q = 0

def _draw_text(colors, x0, y0, sh, chars, color):
    H, W = colors.shape
    unit = 8 if sh == 3 else 16
    for ci, ch in enumerate(chars):
        if ch < 0 or ch >= 27: continue
        cx_base = x0 + ci * 4 * unit
        for gy in range(5):
            for gx in range(3):
                if not FONT[ch, gy, gx]: continue
                ry0, ry1 = y0 + gy*unit, y0 + (gy+1)*unit
                cx0, cx1 = cx_base + gx*unit, cx_base + (gx+1)*unit
                ry0c, ry1c = max(0, ry0), min(H, ry1)
                cx0c, cx1c = max(0, cx0), min(W, cx1)
                if ry0c < ry1c and cx0c < cx1c: colors[ry0c:ry1c, cx0c:cx1c] = color

def render_flappy(game):
    H, W = 480, 640
    r_bc = np.broadcast_to(np.arange(H, dtype=np.int32)[:, None], (H, W))
    c_bc = np.broadcast_to(np.arange(W, dtype=np.int32)[None, :], (H, W))
    colors = np.full((H, W), C_SKY, dtype=np.uint16)
    for xc, yc in [(120, 96), (380, 170)]:
        r0, r1 = max(0, yc), min(GROUND_Y, yc+32)
        if r0 >= r1: continue
        rr = r_bc[r0:r1]; cc = c_bc[r0:r1]
        cx = (cc + game.bg) % 512
        dy = rr - yc
        band = np.clip(dy // 8, 0, 3)
        hw = np.array([24,40,48,40])[band]
        in_c = (dy >= 0) & (dy < 32) & (np.abs(cx - xc) < hw)
        lower = in_c & (dy >= 24)
        upper = in_c & ~lower
        sub = colors[r0:r1]
        sub[upper] = C_CLOUD
        sub[lower] = C_CLOUD_SH
    r0, r1 = 329, GROUND_Y
    if r0 < r1:
        rr = r_bc[r0:r1]; cc = c_bc[r0:r1]
        hx = (cc + game.bg) % 128
        tri = np.where(hx < 64, hx, 127 - hx)
        d = 63 - tri
        top = 392 - (63 - (d*d) // 64)
        hill = rr >= top
        rim = hill & (rr < top + 3)
        sub = colors[r0:r1]
        sub[hill & ~rim] = C_HILL
        sub[rim] = C_HILL_RIM
    for i in range(NUM_PIPES):
        px = game.px[i]
        c0, c1 = max(0, px), min(W, px + PIPE_W)
        if c0 >= c1: continue
        rr = r_bc[:GROUND_Y, c0:c1]; cc = c_bc[:GROUND_Y, c0:c1]
        dx = cc - px
        in_x = (dx >= 0) & (dx < PIPE_W)
        gt, gb = game.gt[i], game.gt[i] + game.gap_r
        tb = in_x & (rr < gt - CAP_H) & (dx >= 4) & (dx < PIPE_W - 4)
        tc = in_x & (rr >= gt - CAP_H) & (rr < gt)
        be = tb & ((dx < 6) | (dx >= PIPE_W - 6))
        ce = tc & ((dx < 2) | (dx >= PIPE_W - 2) | (rr < gt - CAP_H + 2) | (rr >= gt - 2))
        any_top = tb | tc
        col = np.full_like(rr, C_PIPE_MD, dtype=np.uint16)
        col[dx < 14]  = C_PIPE_LT
        col[dx >= 58] = C_PIPE_DK
        col[be | ce]  = C_PIPE_OUT
        sub = colors[:GROUND_Y, c0:c1]
        sub[any_top] = col[any_top]
        bb = in_x & (rr >= gb + CAP_H) & (dx >= 4) & (dx < PIPE_W - 4)
        bc = in_x & (rr >= gb) & (rr < gb + CAP_H)
        be2 = bb & ((dx < 6) | (dx >= PIPE_W - 6))
        ce2 = bc & ((dx < 2) | (dx >= PIPE_W - 2) | (rr < gb + 2) | (rr >= gb + CAP_H - 2))
        any_bot = bb | bc
        col = np.full_like(rr, C_PIPE_MD, dtype=np.uint16)
        col[dx < 14]  = C_PIPE_LT
        col[dx >= 58] = C_PIPE_DK
        col[be2 | ce2] = C_PIPE_OUT
        sub[any_bot] = col[any_bot]
    gr = r_bc[GROUND_Y:] - GROUND_Y
    cc = c_bc[GROUND_Y:]
    sub = colors[GROUND_Y:]
    stripe = ((cc + game.gnd + gr) // 16) % 2 == 0
    sub[:] = C_SAND
    sub[gr < 2] = C_GROUND_LINE
    grass = (gr >= 2) & (gr < 10)
    sub[grass & stripe]  = C_GRASS_LT
    sub[grass & ~stripe] = C_GRASS_DK
    sub[(gr >= 10) & (gr < 12)] = C_GROUND_LINE
    sub[gr >= 44] = C_SAND_DK
    by0, bx0 = game.bird_y_int(), BIRD_X
    if 0 <= by0 < H and 0 <= bx0 < W:
        sprite = SPRITES[game.bird_frame_int()]
        by1, bx1 = min(H, by0+BIRD_SIZE), min(W, bx0+BIRD_SIZE)
        rr = r_bc[by0:by1, bx0:bx1] - by0
        cc = c_bc[by0:by1, bx0:bx1] - bx0
        code = sprite[np.clip(rr // 2, 0, 15), np.clip(cc // 2, 0, 15)]
        sprite_col = SPRITE_PALETTE[code]
        mask = code != 0
        sub = colors[by0:by1, bx0:bx1]
        sub[mask] = sprite_col[mask]
    
    # Text (Score Fixed: Units, Tens, Hundreds)
    texts = []
    if game.st != "READY":
        u, t, h = game.score_r
        if h > 0:    texts.append((276, 28, 3, [h, t, u]))
        elif t > 0:  texts.append((292, 28, 3, [t, u, G_SPACE]))
        else:        texts.append((308, 28, 3, [u, G_SPACE, G_SPACE]))
    if game.st == "READY": 
        texts.append((136, 90, 4, [G_F, G_L, G_A, G_P, G_P, G_Y]))
    if game.st == "OVER":
        texts.append((40, 90, 4, [G_G, G_A, G_M, G_E, G_SPACE, G_O, G_V, G_E, G_R]))
        u, t, h = game.score_r
        scl = [G_S, G_C, G_O, G_R, G_E, G_SPACE, G_SPACE, G_SPACE, u]
        if h > 0: scl[6] = h
        if h > 0 or t > 0: scl[7] = t
        texts.append((180, 210, 3, scl))
        
        bu, bt, bh = game.best_r
        bsl = [G_B, G_E, G_S, G_T, G_SPACE, G_SPACE, G_SPACE, G_SPACE, bu]
        if bh > 0: bsl[6] = bh
        if bh > 0 or bt > 0: bsl[7] = bt
        texts.append((180, 262, 3, bsl))
        
    if game.st in ("READY", "OVER") and game.blink():
        texts.append((164, 340, 3, [G_P, G_R, G_E, G_S, G_S, G_SPACE, G_K, G_E, G_Y, 1]))
    for x0, y0, sh, chars in texts: _draw_text(colors, x0+2, y0+2, sh, chars, C_TXT_SHADOW)
    for x0, y0, sh, chars in texts: _draw_text(colors, x0, y0, sh, chars, C_WHITE)
    if game.flash(): colors[:] = C_WHITE
    return colors

def rgb12_to_rgb8(colors):
    return np.stack([((colors >> 8) & 0xF) * 17, ((colors >> 4) & 0xF) * 17, (colors & 0xF) * 17], axis=-1).astype(np.uint8)


# ============================================================================
#  GUI
# ============================================================================
class DE1VgaSimulator:
    COLOR_LUT = np.array([[0,0,0],[0,0,255],[0,255,0],[0,255,255],[255,0,0],[255,0,255],[255,255,0],[255,255,255]], dtype=np.uint8)

    def __init__(self, root, config, port_info, vhd_dir):
        self.root = root
        self.config = config
        self.port_info = port_info
        self.vhd_dir = vhd_dir
        self.entity_name = config["entity"]
        
        if "flappy" in self.entity_name.lower(): self.design_type = "flappy"
        elif "vga_top" in self.entity_name.lower(): self.design_type = "pattern"
        else: self.design_type = "unknown"

        root.title(f"DE1 VGA Simulator - {self.entity_name}")
        root.resizable(False, False)

        self.sw = [0]*10
        self.key = [1, 1, 1, 1]
        self.flap_pending = False
        self.pattern = VGAPattern()
        self.game = FlappyGame()

        rows, cols = np.mgrid[0:480, 0:640]
        self.rows, self.cols = rows.astype(np.uint16), cols.astype(np.uint16)
        self.frame_count = 0

        self._build_ui()
        self._bind_keys()

    def _bind_keys(self):
        self.root.bind("<space>", lambda e: self._on_key_press(1))
        self.root.bind("<KeyRelease-space>", lambda e: self._on_key_release(1))
        self.root.bind("<r>", lambda e: self._on_key_press(0))
        self.root.bind("<KeyRelease-r>", lambda e: self._on_key_release(0))

    def _build_ui(self):
        screen = tk.LabelFrame(self.root, text="VGA 640x480 @ 60 Hz")
        screen.grid(row=0, column=0, padx=6, pady=6, sticky="n")
        self.canvas = tk.Canvas(screen, width=640, height=480, bg="black", highlightthickness=0)
        self.canvas.pack()
        self.photo = None

        panel = tk.Frame(self.root)
        panel.grid(row=0, column=1, padx=6, pady=6, sticky="n")

        info = tk.LabelFrame(panel, text="Pin Mappings")
        info.pack(fill="x", padx=4, pady=4)
        self.info_lbl = tk.Label(info, justify="left", anchor="w", font=("Courier", 8), text=ports_summary(self.entity_name, self.config))
        self.info_lbl.pack(fill="x")

        sw_box = tk.LabelFrame(panel, text="Switches")
        sw_box.pack(fill="x", padx=4, pady=4)
        self.sw_vars = []
        for i in range(10):
            v = tk.IntVar(value=0)
            lbl = self.config["sw"].get(i, f"SW{i}")
            tk.Checkbutton(sw_box, text=f"SW{i} ({lbl})", variable=v, command=lambda idx=i, var=v: self._set_sw(idx, var.get())).pack(anchor="w")
            self.sw_vars.append(v)

        key_box = tk.LabelFrame(panel, text="Buttons")
        key_box.pack(fill="x", padx=4, pady=4)
        self.key_btns = []
        for i in range(4):
            lbl = self.config["key"].get(i, f"KEY{i}")
            b = tk.Button(key_box, text=f"KEY{i} ({lbl})", width=24, relief="raised", bg="SystemButtonFace")
            b.bind("<ButtonPress-1>", lambda e, idx=i: self._on_key_press(idx))
            b.bind("<ButtonRelease-1>", lambda e, idx=i: self._on_key_release(idx))
            b.pack(pady=1)
            self.key_btns.append(b)

        led_box = tk.LabelFrame(panel, text="LEDs")
        led_box.pack(fill="x", padx=4, pady=4)
        led_row = tk.Frame(led_box); led_row.pack()
        self.led_labels = [None]*10
        for i in range(9, -1, -1):
            col = tk.Frame(led_row); col.pack(side="left", padx=1)
            lamp = tk.Label(col, text="", width=2, height=1, bg="gray", relief="sunken")
            lamp.pack()
            lbl = self.config["led"].get(i, str(i))
            tk.Label(col, text=lbl, font=("TkDefaultFont", 6)).pack()
            self.led_labels[i] = lamp

        st_box = tk.LabelFrame(panel, text="Status")
        st_box.pack(fill="x", padx=4, pady=4)
        self.status = tk.Label(st_box, justify="left", anchor="w", font=("Courier", 9), width=32)
        self.status.pack(fill="x")

    def _set_sw(self, i, val): self.sw[i] = val

    def _on_key_press(self, i):
        self.key[i] = 0
        if self.design_type == "flappy" and i in (1, 2): self.flap_pending = True
        self.key_btns[i].config(relief="sunken", bg="#c8f5c8")

    def _on_key_release(self, i):
        self.key[i] = 1
        self.key_btns[i].config(relief="raised", bg="SystemButtonFace")

    def _tick(self):
        try:
            if self.design_type == "flappy": self._tick_flappy()
            elif self.design_type == "pattern": self._tick_pattern()
            else: self._tick_unknown()
        except Exception as e:
            print("Tick error:", e)
        self.root.after(16, self._tick)

    def _tick_unknown(self):
        self.canvas.delete("all")
        self.canvas.create_text(320, 240, text=f"No Python model for '{self.entity_name}'.\nPlease add a backend class in the script.", fill="white", font=("Arial", 16), justify="center")
        self.status.config(text="Status: Unknown Design")

    def _tick_pattern(self):
        reset  = (self.key[0] == 0)
        freeze = (self.key[1] == 0)
        mode   = f"{self.sw[1]}{self.sw[0]}"
        csel   = f"{self.sw[4]}{self.sw[3]}{self.sw[2]}"
        speed  = (self.sw[9] << 1) | self.sw[8]
        scroll_en = bool(self.sw[5])

        if reset: self.pattern = VGAPattern()
        else: self.pattern.update(freeze, speed)

        rgb_bits = self.pattern.render(mode, csel, scroll_en, self.rows, self.cols)
        idx = ((rgb_bits[...,0] << 2) | (rgb_bits[...,1] << 1) | rgb_bits[...,2]).astype(np.uint8)
        self._show_image(self.COLOR_LUT[idx])

        for i, lbl in enumerate(self.led_labels):
            lbl.config(bg="#ff5050" if self.sw[i] else "gray")

        self.frame_count += 1
        self.status.config(text=f"mode={mode}\nspeed={speed+1}\nscroll={scroll_en}\nfreeze={freeze}\nframes={self.frame_count}")

    def _tick_flappy(self):
        reset     = (self.key[0] == 0)
        speed_sel = (self.sw[1] << 1) | self.sw[0]
        hard      = bool(self.sw[2])
        flap      = self.flap_pending
        self.flap_pending = False

        if reset: self.game.reset()
        else: self.game.tick(flap, speed_sel, hard)

        colors12 = render_flappy(self.game)
        self._show_image(rgb12_to_rgb8(colors12))

        score_val = bcd_value(self.game.score_r)
        for i in range(10):
            self.led_labels[i].config(bg="#ff5050" if ((score_val >> i) & 1) else "gray")

        self.frame_count += 1
        self.status.config(text=f"state={self.game.st}\nscore={score_val}\nbird_y={self.game.bird_y_int()}\nframes={self.frame_count}")

    def _show_image(self, arr8):
        img = Image.fromarray(arr8, mode="RGB")
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)


# ============================================================================
#  Entry point
# ============================================================================
def main():
    vhd_dir = find_vhd_dir()
    config = load_config(vhd_dir)
    
    ports, err = validate_entity(vhd_dir, config)
    if err:
        err_win = tk.Tk(); err_win.withdraw()
        messagebox.showerror("Config Error", f"Could not load '{config['entity']}':\n\n{err}\n\nCheck your config.txt or the VHDL file.", parent=err_win)
        err_win.destroy()
        return

    root = tk.Tk()
    sim = DE1VgaSimulator(root, config, ports, vhd_dir)
    sim._tick()
    root.mainloop()

if __name__ == "__main__":
    main()