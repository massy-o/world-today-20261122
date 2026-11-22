#!/usr/bin/env python3
"""Sum up 22 November 2026's world news in one image.

Pure Python 3 standard library. Draws a wire-service front page
(masthead with the date, six full stories, an eight-item "in brief"
column and a "day in numbers" box) and writes it as a deterministic
PNG to /output/entry.png. The drawing engine, stroke typeface and
pictograms are all hand-built in this file; no assets, no network.
"""
import math
import os
import struct
import zlib

SS = 2                      # supersampling factor
W, H = 1024, 1024           # final image size
CW, CH = W * SS, H * SS     # canvas size

# ---------------------------------------------------------------- canvas
buf = bytearray(CW * CH * 3)

PAPER = (246, 241, 231)
CARD = (255, 253, 247)
INK = (17, 19, 24)
GRAY = (74, 78, 86)
RED = (178, 34, 40)
BLUE = (28, 74, 142)
GOLD = (196, 138, 26)
GREEN = (24, 122, 74)
TEAL = (10, 110, 122)
PURPLE = (92, 58, 140)


def px(x, y, color):
    if 0 <= x < CW and 0 <= y < CH:
        i = (y * CW + x) * 3
        buf[i:i + 3] = bytes(color)


def fill_rect(x, y, w, h, color):
    """Filled rectangle in final-image coordinates."""
    x0, y0 = int(x * SS), int(y * SS)
    x1, y1 = int((x + w) * SS), int((y + h) * SS)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, CW), min(y1, CH)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    n = len(row)
    for yy in range(y0, y1):
        i = (yy * CW + x0) * 3
        buf[i:i + n] = row


def fill_circle(cx, cy, r, color):
    """Filled circle in final-image coordinates."""
    cx, cy, r = cx * SS, cy * SS, r * SS
    y0, y1 = int(cy - r), int(cy + r) + 1
    for yy in range(max(y0, 0), min(y1, CH)):
        d = math.sqrt(max(r * r - (yy - cy) ** 2, 0.0))
        x0, x1 = int(cx - d), int(cx + d) + 1
        x0, x1 = max(x0, 0), min(x1, CW)
        if x1 > x0:
            i = (yy * CW + x0) * 3
            buf[i:i + (x1 - x0) * 3] = bytes(color) * (x1 - x0)


def fill_poly(points, color):
    """Scanline polygon fill; points in final-image coordinates."""
    pts = [(x * SS, y * SS) for x, y in points]
    ys = [p[1] for p in pts]
    y0, y1 = int(min(ys)), int(max(ys)) + 1
    n = len(pts)
    for yy in range(max(y0, 0), min(y1, CH)):
        yc = yy + 0.5
        xs = []
        for i in range(n):
            x1, y1p = pts[i]
            x2, y2p = pts[(i + 1) % n]
            if (y1p <= yc < y2p) or (y2p <= yc < y1p):
                xs.append(x1 + (yc - y1p) * (x2 - x1) / (y2p - y1p))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = int(xs[k]), int(xs[k + 1]) + 1
            xa, xb = max(xa, 0), min(xb, CW)
            if xb > xa:
                i = (yy * CW + xa) * 3
                buf[i:i + (xb - xa) * 3] = bytes(color) * (xb - xa)


def line(x1, y1, x2, y2, width, color):
    """Thick line with round caps, final-image coordinates."""
    dist = math.hypot(x2 - x1, y2 - y1)
    steps = max(int(dist / max(width * 0.35, 0.5)), 1)
    for i in range(steps + 1):
        t = i / steps
        fill_circle(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, width / 2, color)


def polyline(points, width, color, close=False):
    pts = list(points)
    if close and pts:
        pts.append(pts[0])
    for a, b in zip(pts, pts[1:]):
        line(a[0], a[1], b[0], b[1], width, color)


def star(cx, cy, r, color, rot=-math.pi / 2):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = rot + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    fill_poly(pts, color)


# ---------------------------------------------------------------- font
# Stroke font on a 4 x 6 grid (y down, 0 = cap top, 6 = baseline).
# Each glyph is a list of strokes; each stroke is a list of (x, y) points.
G = {
    'A': [[(0, 6), (2, 0), (4, 6)], [(0.9, 4.1), (3.1, 4.1)]],
    'B': [[(0, 0), (0, 6)], [(0, 0), (2.5, 0), (3.5, 0.8), (3.5, 2.1), (2.5, 2.9), (0, 2.9)],
          [(0, 2.9), (2.7, 2.9), (3.7, 3.8), (3.7, 5.1), (2.7, 6), (0, 6)]],
    'C': [[(3.7, 1.3), (2.8, 0.2), (1.3, 0), (0.3, 1.1), (0, 3), (0.3, 4.9), (1.3, 6), (2.8, 5.8), (3.7, 4.7)]],
    'D': [[(0, 0), (0, 6)], [(0, 0), (2.3, 0), (3.6, 1.3), (3.9, 3), (3.6, 4.7), (2.3, 6), (0, 6)]],
    'E': [[(3.9, 0), (0, 0), (0, 6), (3.9, 6)], [(0, 3), (3.0, 3)]],
    'F': [[(3.9, 0), (0, 0), (0, 6)], [(0, 3), (3.0, 3)]],
    'G': [[(3.7, 1.3), (2.8, 0.2), (1.3, 0), (0.3, 1.1), (0, 3), (0.3, 4.9), (1.3, 6), (2.8, 5.8), (3.8, 4.9), (3.8, 3.5), (2.5, 3.5)]],
    'H': [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    'I': [[(2, 0), (2, 6)], [(0.7, 0), (3.3, 0)], [(0.7, 6), (3.3, 6)]],
    'J': [[(4, 0), (4, 4.4), (3.2, 5.7), (1.7, 6), (0.6, 5.3), (0.2, 4.2)]],
    'K': [[(0, 0), (0, 6)], [(3.9, 0), (0.3, 3.1)], [(0.9, 2.5), (4, 6)]],
    'L': [[(0, 0), (0, 6), (3.9, 6)]],
    'M': [[(0, 6), (0, 0), (2, 3.1), (4, 0), (4, 6)]],
    'N': [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    'O': [[(1.3, 0), (2.7, 0), (3.8, 1.1), (4, 3), (3.8, 4.9), (2.7, 6), (1.3, 6), (0.2, 4.9), (0, 3), (0.2, 1.1), (1.3, 0)]],
    'P': [[(0, 6), (0, 0)], [(0, 0), (2.6, 0), (3.6, 0.9), (3.6, 2.1), (2.6, 3), (0, 3)]],
    'Q': [[(1.3, 0), (2.7, 0), (3.8, 1.1), (4, 3), (3.8, 4.9), (2.7, 6), (1.3, 6), (0.2, 4.9), (0, 3), (0.2, 1.1), (1.3, 0)], [(2.5, 4.3), (4.2, 6.3)]],
    'R': [[(0, 6), (0, 0)], [(0, 0), (2.6, 0), (3.6, 0.9), (3.6, 2.1), (2.6, 3), (0, 3)], [(2.1, 3), (4, 6)]],
    'S': [[(3.6, 1.1), (2.7, 0.1), (1.2, 0), (0.3, 0.9), (0.4, 2.0), (1.4, 2.9), (2.8, 3.6), (3.7, 4.4), (3.5, 5.4), (2.5, 6), (1.0, 5.9), (0.2, 5.1)]],
    'T': [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    'U': [[(0, 0), (0, 4.3), (0.8, 5.7), (2, 6), (3.2, 5.7), (4, 4.3), (4, 0)]],
    'V': [[(0, 0), (2, 6), (4, 0)]],
    'W': [[(0, 0), (0.8, 6), (2, 3.3), (3.2, 6), (4, 0)]],
    'X': [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    'Y': [[(0, 0), (2, 2.8), (4, 0)], [(2, 2.8), (2, 6)]],
    'Z': [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    '0': [[(1.3, 0), (2.7, 0), (3.6, 1.2), (3.6, 4.8), (2.7, 6), (1.3, 6), (0.4, 4.8), (0.4, 1.2), (1.3, 0)]],
    '1': [[(1.1, 1.3), (2.4, 0), (2.4, 6)], [(0.8, 6), (3.6, 6)]],
    '2': [[(0.4, 1.3), (1.1, 0.2), (2.6, 0), (3.6, 1.0), (3.4, 2.4), (0.2, 6), (3.9, 6)]],
    '3': [[(0.4, 0.9), (1.4, 0), (2.8, 0.2), (3.4, 1.2), (2.8, 2.4), (1.5, 2.9)],
          [(1.5, 2.9), (2.9, 3.3), (3.5, 4.4), (2.9, 5.7), (1.3, 6), (0.3, 5.2)]],
    '4': [[(2.8, 6), (2.8, 0), (0, 4.3), (4, 4.3)]],
    '5': [[(3.8, 0), (0.6, 0), (0.4, 2.6)], [(0.4, 2.6), (2.2, 2.3), (3.5, 3.1), (3.6, 4.6), (2.8, 5.8), (1.2, 6), (0.2, 5.3)]],
    '6': [[(3.4, 0.9), (2.3, 0.1), (1.0, 0.7), (0.3, 2.1), (0.2, 4.3), (0.9, 5.7), (2.2, 6), (3.4, 5.2), (3.7, 3.9), (3.0, 2.9), (1.5, 2.7), (0.3, 3.5)]],
    '7': [[(0.2, 0), (4, 0), (1.7, 6)]],
    '8': [[(1.4, 0.2), (2.6, 0.2), (3.2, 1.0), (2.9, 2.1), (2.0, 2.7), (1.1, 2.1), (0.8, 1.0), (1.4, 0.2)],
          [(1.1, 2.9), (2.9, 2.9), (3.6, 4.0), (3.4, 5.3), (2.7, 6), (1.3, 6), (0.6, 5.3), (0.4, 4.0), (1.1, 2.9)]],
    '9': [[(0.6, 5.1), (1.7, 5.9), (3.0, 5.3), (3.7, 3.9), (3.8, 1.7), (3.1, 0.3), (1.8, 0), (0.6, 0.8), (0.3, 2.1), (1.0, 3.1), (2.5, 3.3), (3.7, 2.5)]],
    '.': [],
    ',': [[(2.3, 5.3), (1.9, 6.5)]],
    ';': [[(2.3, 5.3), (1.9, 6.5)]],
    ':': [],
    "'": [[(2.1, 0), (1.8, 1.5)]],
    '-': [[(0.7, 3), (3.3, 3)]],
    '+': [[(2, 1.6), (2, 4.4)], [(0.6, 3), (3.4, 3)]],
    '/': [[(3.4, 0), (0.6, 6)]],
    '!': [[(2, 0), (2, 4.1)]],
    '?': [[(0.5, 1.1), (1.3, 0.1), (2.7, 0), (3.5, 0.9), (3.3, 2.0), (2.1, 2.9), (2, 4.1)]],
    '&': [[(3.4, 0.8), (2.6, 0), (1.4, 0.4), (1.3, 1.4), (2.2, 2.3), (3.5, 3.9), (2.5, 5.5), (1.1, 5.9), (0.3, 4.9), (0.9, 3.6), (3.5, 3.9)]],
    '$': [[(3.6, 1.1), (2.7, 0.1), (1.2, 0), (0.3, 0.9), (0.4, 2.0), (1.4, 2.9), (2.8, 3.6), (3.7, 4.4), (3.5, 5.4), (2.5, 6), (1.0, 5.9), (0.2, 5.1)], [(2, -0.3), (2, 6.3)]],
    '%': [[(3.4, 0), (0.6, 6)]],
}
DOTS = {'.': [(2, 5.7)], ':': [(2, 1.5), (2, 4.6)], ';': [(2, 1.5)], '!': [(2, 5.7)], '?': [(2, 5.7)]}
CIRCLES = {'%': [(1.1, 1.3, 0.85), (2.9, 4.7, 0.85)]}

ADV = 4.95  # character advance in grid units (4 wide + tracking)


def text_width(text, unit):
    return len(text) * ADV * unit


def draw_text(text, x, y, unit, color, sw=None, align='left'):
    """Draw text; (x, y) is the cap-top-left in final-image coordinates."""
    if sw is None:
        sw = unit * 0.62
    w = text_width(text, unit)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    cx = x
    for ch in text.upper():
        if ch == ' ':
            cx += ADV * unit
            continue
        if ch == '\u2022':
            fill_rect(cx + 1.5 * unit, y + 2.5 * unit, 1.1 * unit, 1.1 * unit, color)
            cx += ADV * unit
            continue
        for stroke in G.get(ch, []):
            pts = [(cx + gx * unit, y + gy * unit) for gx, gy in stroke]
            polyline(pts, sw, color)
        for dx, dy in DOTS.get(ch, []):
            fill_circle(cx + dx * unit, y + dy * unit, sw * 0.62, color)
        for dx, dy, rr in CIRCLES.get(ch, []):
            polyline([(cx + (dx + rr) * unit, y + dy * unit)], sw, color)  # placeholder
            # draw small ring as four arcs of stamps
            for k in range(13):
                a = k * math.pi / 6
                fill_circle(cx + (dx + rr * math.cos(a)) * unit,
                            y + (dy + rr * math.sin(a)) * unit, sw * 0.5, color)
        cx += ADV * unit
    return cx


def wrap(text, unit, max_width):
    words = text.split()
    lines, cur = [], ''
    for wd in words:
        trial = (cur + ' ' + wd).strip()
        if text_width(trial, unit) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_paragraph(text, x, y, unit, color, max_width, line_h, sw=None):
    lines = wrap(text, unit, max_width)
    for i, ln in enumerate(lines):
        draw_text(ln, x, y + i * line_h, unit, color, sw=sw)
    return len(lines)


# ---------------------------------------------------------------- pictograms
def flag_us(x, y, w, h):
    fill_rect(x, y, w, h, (255, 255, 255))
    sh = h / 7
    for i in range(0, 7, 2):
        fill_rect(x, y + i * sh, w, sh, RED)
    fill_rect(x, y, w * 0.44, sh * 4, BLUE)
    for r in range(4):
        for c in range(5):
            fill_circle(x + w * 0.05 + c * w * 0.085, y + sh * 0.55 + r * sh * 0.95, 0.9, (255, 255, 255))


def flag_cn(x, y, w, h):
    fill_rect(x, y, w, h, (222, 41, 16))
    star(x + w * 0.18, y + h * 0.26, w * 0.11, (255, 222, 0))
    for dx, dy in ((0.36, 0.10), (0.40, 0.26), (0.40, 0.42), (0.34, 0.56)):
        star(x + w * dx, y + h * dy, w * 0.05, (255, 222, 0))


def flag_ru(x, y, w, h):
    fill_rect(x, y, w, h / 3, (255, 255, 255))
    fill_rect(x, y + h / 3, w, h / 3, (0, 57, 166))
    fill_rect(x, y + 2 * h / 3, w, h / 3 + 1, (213, 43, 30))


def flag_pl(x, y, w, h):
    fill_rect(x, y, w, h / 2, (255, 255, 255))
    fill_rect(x, y + h / 2, w, h / 2 + 1, (220, 20, 60))


def picto_summit(cx, cy):
    fw, fh, gap = 62, 42, 14
    x0 = cx - (3 * fw + 2 * gap) / 2
    for i, fn in enumerate((flag_us, flag_cn, flag_ru)):
        x = x0 + i * (fw + gap)
        line(x + 2, cy - 30, x + 2, cy + 32, 2.6, GRAY)
        fn(x + 5, cy - 30, fw - 4, fh)
        line(x + 5, cy - 30, x + fw + 1, cy - 30, 1.4, INK)
    line(cx - 95, cy + 34, cx + 95, cy + 34, 3, INK)


def picto_missile(cx, cy):
    # explosion starburst top-left, missile diving to bottom-right, PL flag chip
    bx, by = cx - 58, cy - 18
    for a in range(0, 360, 30):
        r1, r2 = 7, 24 if a % 60 == 0 else 16
        line(bx + r1 * math.cos(math.radians(a)), by + r1 * math.sin(math.radians(a)),
             bx + r2 * math.cos(math.radians(a)), by + r2 * math.sin(math.radians(a)), 3.2, GOLD)
    fill_circle(bx, by, 8, RED)
    body = [(cx - 6, cy - 30), (cx + 26, cy + 2), (cx + 34, cy + 16), (cx + 20, cy + 22),
            (cx + 2, cy + 6), (cx - 14, cy + 8), (cx - 10, cy - 6), (cx - 22, cy - 14)]
    fill_poly(body, GRAY)
    fill_poly([(cx + 20, cy + 22), (cx + 34, cy + 16), (cx + 38, cy + 30), (cx + 26, cy + 32)], RED)
    fill_poly([(cx - 6, cy - 30), (cx - 22, cy - 40), (cx - 16, cy - 14)], GOLD)
    fill_poly([(cx - 6, cy - 30), (cx + 6, cy - 44), (cx + 2, cy - 6)], GOLD)
    flag_pl(cx + 52, cy + 14, 40, 26)
    line(cx + 52, cy + 14, cx + 92, cy + 14, 1.4, INK)
    line(cx + 52, cy + 40, cx + 92, cy + 40, 1.4, INK)


def picto_court(cx, cy):
    fill_poly([(cx - 74, cy - 18), (cx, cy - 42), (cx + 74, cy - 18)], INK)
    fill_circle(cx, cy - 24, 5, PAPER)
    fill_rect(cx - 74, cy - 16, 148, 5, INK)
    for i in range(4):
        x = cx - 58 + i * 36
        fill_rect(x, cy - 8, 13, 30, INK)
        fill_rect(x - 3, cy - 12, 19, 4, INK)
        fill_rect(x - 3, cy + 21, 19, 4, INK)
    fill_rect(cx - 80, cy + 28, 160, 5, INK)
    fill_rect(cx - 88, cy + 35, 176, 5, INK)


def picto_chart(cx, cy, up=False):
    x0, x1, y0, y1 = cx - 88, cx + 88, cy - 36, cy + 30
    for gx in range(4):
        xx = x0 + gx * (x1 - x0) / 3
        line(xx, y0, xx, y1, 0.9, (198, 200, 205))
    for gy in range(3):
        yy = y0 + gy * (y1 - y0) / 2
        line(x0, yy, x1, yy, 0.9, (198, 200, 205))
    if not up:
        pts = [(x0, y0 + 8), (cx - 48, y0 + 16), (cx - 22, y0 + 6), (cx + 8, y0 + 30), (cx + 34, y0 + 22), (x1 - 8, y1 - 2)]
        col = RED
    else:
        pts = [(x0, y1 - 6), (cx - 48, y1 - 14), (cx - 22, y1 - 4), (cx + 8, y0 + 26), (cx + 34, y0 + 32), (x1 - 8, y0 + 4)]
        col = GREEN
    polyline(pts, 4.4, col)
    ex, ey = pts[-1]
    dx, dy = (10, 8) if not up else (10, -8)
    fill_poly([(ex + dx, ey + dy), (ex - 2, ey + (14 if not up else -2)), (ex + (14 if not up else 2), ey - 2 if not up else ey + 2)], col)
    line(x0, y0, x0, y1, 2, INK)
    line(x0, y1, x1, y1, 2, INK)


def picto_ipo(cx, cy):
    base = cy + 36
    heights = [26, 44, 66]
    for i, hh in enumerate(heights):
        x = cx - 76 + i * 46
        fill_rect(x, base - hh, 34, hh, GREEN if i == 2 else (120, 178, 148))
    line(cx - 84, base, cx + 84, base, 2.4, INK)
    pts = [(cx - 78, cy + 2), (cx - 30, cy - 12), (cx + 6, cy - 2), (cx + 62, cy - 34)]
    polyline(pts, 4.2, GOLD)
    fill_poly([(cx + 76, cy - 40), (cx + 50, cy - 38), (cx + 64, cy - 24)], GOLD)
    fill_circle(cx + 58, cy + 16, 17, GOLD)
    draw_text('$', cx + 58 - 2 * 2.6, cy + 16 - 3 * 2.6, 2.6, (255, 255, 255), sw=1.8, align='left')


def picto_mercury(cx, cy):
    fill_circle(cx - 6, cy + 2, 34, (198, 128, 84))
    fill_circle(cx - 20, cy - 10, 7, (172, 104, 64))
    fill_circle(cx + 6, cy + 14, 5.5, (172, 104, 64))
    fill_circle(cx - 2, cy - 22, 4.5, (172, 104, 64))
    fill_circle(cx + 14, cy - 8, 4, (172, 104, 64))
    for k in range(60):
        a = k * math.pi / 30
        ex, ey = cx - 6 + 52 * math.cos(a), cy + 2 + 15 * math.sin(a)
        if ey < cy + 16:
            fill_circle(ex, ey, 1.5, TEAL)
    sx, sy = cx + 52, cy - 26
    fill_rect(sx - 6, sy - 6, 13, 12, GRAY)
    fill_rect(sx - 22, sy - 4, 14, 8, BLUE)
    fill_rect(sx + 9, sy - 4, 14, 8, BLUE)
    line(sx - 2, sy + 6, sx - 10, sy + 14, 2.2, GRAY)
    star(cx - 66, cy - 30, 4.5, GOLD)
    star(cx + 74, cy + 22, 3.8, GOLD)
    star(cx - 52, cy + 30, 3.4, GOLD)


# ---------------------------------------------------------------- scene
# Newspaper-density front page: six story cards with fact lines, a
# numbers strip, and thirty one-line briefs in four columns.
# 58 verified facts from Saturday 21 November 2026.
def build():
    fill_rect(0, 0, W, H, PAPER)
    line(28, 16, W - 28, 16, 3.0, INK)
    draw_text('ONE DAY', 28, 38, 2.2, GRAY, sw=1.5)
    draw_text('ONE PAGE', 28, 56, 2.2, GRAY, sw=1.5)
    draw_text('SIX STORIES', W - 28, 38, 2.2, GRAY, sw=1.5, align='right')
    draw_text('30 BRIEFS', W - 28, 56, 2.2, GRAY, sw=1.5, align='right')
    draw_text('THE WORLD TODAY', W / 2, 26, 8.6, INK, sw=5.9, align='center')
    fill_rect(28, 88, W - 56, 26, RED)
    draw_text('SUNDAY 22 NOVEMBER 2026 \u2022 THE WHOLE DAY ON ONE PAGE', W / 2, 93, 3.1, (255, 255, 255), sw=2.2, align='center')
    line(28, 126, W - 28, 126, 1.3, INK)
    line(28, 131, W - 28, 131, 2.8, INK)

    def card(x, y, w, h, kicker, kcolor, head, sub, facts):
        fill_rect(x, y, w, h, CARD)
        line(x, y, x + w, y, 1.5, INK); line(x, y + h, x + w, y + h, 1.5, INK)
        line(x, y, x, y + h, 1.5, INK); line(x + w, y, x + w, y + h, 1.5, INK)
        fill_rect(x, y, w, 6, kcolor)
        draw_text(kicker, x + 12, y + 12, 3.0, kcolor, sw=2.1)
        inner = w - 24
        longest = max(len(ln) for ln in head)
        unit = min(5.0, inner / (longest * ADV))
        hy = y + 40
        for ln in head:
            draw_text(ln, x + 12, hy, unit, INK, sw=unit * 0.67)
            hy += unit * 7.2
        draw_paragraph(sub, x + 12, hy + 4, 1.95, GRAY, inner, 15, sw=1.3)
        line(x + 12, y + 200, x + w - 12, y + 200, 1.0, kcolor)
        draw_text(facts[0], x + 12, y + 208, 1.8, INK, sw=1.25)
        draw_text(facts[1], x + 12, y + 224, 1.8, INK, sw=1.25)

    cards = [
        ('CONFLICT', RED, ['IRAN HITS', 'PATRIOT RADARS'],
         "MANAMA - IRAN'S GUARDS SAY MISSILES AND DRONES HIT TWO US PATRIOT RADARS IN BAHRAIN. MANAMA REPORTS A FIRE AT A CIVILIAN SITE.",
         ['RADARS AT AL-RIFFA AND AWALI', 'BAHRAIN ASKS UN TO ACT']),
        ('DIPLOMACY', PURPLE, ['NO ROBOT', 'WAR DECISIONS'],
         "SHENZHEN - TRUMP AND XI AGREE MILITARY AI DECISIONS MUST KEEP A HUMAN IN CHARGE, TREASURY SECRETARY BESSENT TELLS CNBC.",
         ['TRADE TRUCE NOT EXTENDED', 'TRUCE LAPSES IN JANUARY']),
        ('UKRAINE', BLUE, ['CRIMEAN BRIDGE', 'STRUCK AGAIN'],
         "KYIV - UKRAINIAN STRIKES ON THE CRIMEAN BRIDGE STRAIN RUSSIAN LOGISTICS. ZELENSKY DEMANDS ANOTHER 115 BILLION EUROS.",
         ['SEOUL DEMANDS AN APOLOGY', 'NK PRISONER MOVE REVEALED']),
        ('FRANCE', GOLD, ['STRIKES', 'PARALYSE FRANCE'],
         "PARIS - STRIKES PARALYSE FRANCE AS PRESIDENT MACRON'S POPULARITY FLATLINES. PROTESTERS RALLY A SIXTH WEEKEND OVER LIVING COSTS.",
         ['SIXTH WEEKEND OF PROTESTS', "LE PEN'S PARTY ENTERS SENATE"]),
        ('MARKETS', TEAL, ['BITCOIN AT', 'TWO-YEAR LOW'],
         "NEW YORK - BITCOIN FALLS 5.1 PERCENT TO 55,533 DOLLARS, ITS LOWEST SINCE SEPTEMBER 2024, AS AI STOCKS SELL OFF.",
         ['OVER $2.4BN LIQUIDATED', 'PEAK WAS $126,000 IN 2025']),
        ('CLIMATE', GREEN, ['COP31 HITS', 'DEADLOCK'],
         "ANTALYA - THE DRAFT DEAL AT THE COP31 CLIMATE SUMMIT DROPS ALL MENTION OF FOSSIL FUELS, DRAWING STRONG CONDEMNATION.",
         ['TALKS RUN INTO OVERTIME', 'PHASE-OUT WORDING BLOCKED']),
    ]
    cw, gap = 312, 16
    for i, s in enumerate(cards):
        x = 28 + (i % 3) * (cw + gap)
        y = 144 + (i // 3) * 252
        card(x, y, cw, 240, *s)

    # numbers strip
    fill_rect(28, 646, W - 56, 52, INK)
    draw_text('$55,533 BITCOIN LOW \u2022 -5.1% IN A DAY \u2022 $2.4BN LIQUIDATED \u2022 $1,538 ETHEREUM \u2022 451,000 HEAT DEATHS AHEAD',
              W / 2, 653, 1.8, (240, 240, 235), sw=1.25, align='center')
    draw_text('115BN EUROS ASKED \u2022 10% CARD CAP VOW \u2022 -10% CHIP INDEX \u2022 146 SAFE IN PLANE SCARE \u2022 6TH PROTEST WEEKEND',
              W / 2, 675, 1.8, GOLD, sw=1.25, align='center')

    # brief zone: 30 items, four columns
    fill_rect(28, 708, W - 56, 30, INK)
    draw_text('IN BRIEF \u2022 THIRTY MORE FACTS FROM SUNDAY', 44, 714, 2.9, GOLD, sw=2.0)
    briefs = [
        'IRAN: HORMUZ MAY REOPEN FOR EASING', 'UAE RUNS OIL SHUTTLE PAST IRAN',
        'HOUTHIS STRIKE AT SAUDI CAPITAL', 'US F-16 DOWN ON GERMAN TRAINING',
        'TRUMP EXPANDS FORCES IN GREENLAND', 'SPACEX CATCHES STARSHIP IN ARMS',
        'MOSCOW: DONBASS TOWN ENCIRCLED', 'CAFE STRIKE KILLS TWO IN RUSSIA',
        'EU SIX SEEK FARM CUTS FOR ARMS', 'ETHIOPIA FACES RETURN TO WAR',
        'CONGO MP KILLED OVER EBOLA STAND', 'CEUTA MIGRANT BEATINGS ON VIDEO',
        'SAUDI NUCLEAR AMBITION QUESTIONED', 'PENTAGON CURBS CANADA TIES',
        'TAIWAN WARNS CANADA ON CHINA', 'AUKUS REMARK IRKS AUSTRALIA',
        'INDIA NSE JOINS WORLD TOP FIVE', 'KIM TOURS FACTORIES POST-SNUB',
        'ROHINGYA HAIL GENOCIDE VERDICT', 'BRAZIL TOWN DIGS OUT AFTER STORM',
        'TAINTED ALCOHOL KILLS 11 IN INDIA', 'AIR NIUGINI JET LANDS SAFE, 146',
        'US RELEASES BIGFOOT FILES', 'UK VILLAGE VOTES TO LEAVE UK',
        'CHRISTIANITY TO LOSE TOP SPOT 2035', 'LDP HINTS AT MINISTER SWAP',
        'SCOTLAND OVERPOWER JAPAN RUGBY', 'IRELAND STUN BOKS IN DUBLIN',
        'MAN CITY SLUMP DEEPENS', 'SHIMADA BOOKS GRAND PRIX FINAL',
    ]
    cols_x = [28, 272, 516, 760]
    spans = [(0, 8), (8, 16), (16, 23), (23, 30)]
    for c, (a, b) in enumerate(spans):
        for r, item in enumerate(briefs[a:b]):
            x = cols_x[c]
            y = 750 + r * 28
            fill_rect(x + 2, y + 3, 5, 5, RED)
            lines = wrap(item, 1.72, 218)
            for j, ln in enumerate(lines[:2]):
                draw_text(ln, x + 13, y + j * 14, 1.72, INK, sw=1.2)
    line(28, 984, W - 28, 984, 1.6, INK)
    draw_text('THE WORLD TODAY \u2022 SUNDAY 22 NOVEMBER 2026 \u2022 COMPILED FROM THE DAY\'S WIRE REPORTS \u2022 PAGE 1 OF 1',
              W / 2, 991, 1.55, GRAY, sw=1.1, align='center')

# ---------------------------------------------------------------- output
def downscale():
    out = bytearray(W * H * 3)
    for yy in range(H):
        for xx in range(W):
            i = (yy * W + xx) * 3
            a = ((2 * yy) * CW + 2 * xx) * 3
            b = a + 3
            c = a + CW * 3
            d = c + 3
            for k in range(3):
                out[i + k] = (buf[a + k] + buf[b + k] + buf[c + k] + buf[d + k]) // 4
    return out


def write_png(path, pixels):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = bytearray()
    stride = W * 3
    for yy in range(H):
        raw.append(0)
        raw += pixels[yy * stride:(yy + 1) * stride]
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)
    return len(png)


def main():
    build()
    pixels = downscale()
    os.makedirs('/output', exist_ok=True)
    size = write_png('/output/entry.png', pixels)
    print(f'wrote /output/entry.png ({size} bytes)')


if __name__ == '__main__':
    main()
