"""ui_kit.py: the drawing toolbox used by gui.py.

Normal Tk widgets cannot do gradients, glow or rounded transparent corners, so everything here is
drawn on a Canvas: gradient pill buttons are tiny PNG images generated in pure Python (fast and
smooth), glow cards are stacked outlines, and the animations are small `after` loops.
Only the Python standard library is used, so nothing needs to be installed.
"""
import base64
import math
import queue
import random
import struct
import threading
import time
import tkinter as tk
import zlib
from tkinter import font as tkfont

# ------------------------------------------------------------------------- palette
BG = "#0a0520"             # window background (deep purple-black)
BACKDROP_MID = "#180a46"   # roughly the colour of the soft glow behind the cards
CARD_FILL = "#140a3a"
CARD_EDGE = "#6f72ff"
GLOW = "#6c3df0"
TEXT = "#f7f4ff"
MUTED = "#a99ad9"
DIM = "#6f64b0"
VIOLET = "#7c4dff"
BLUE = "#5aa7ff"
ACCENT = "#a86bff"        # the purple used for highlighted words
PINK = "#ff5ea8"
GOLD = "#ffc83d"
GOLD_LIGHT = "#ffe27d"
ORANGE = "#ff8a3d"
GREEN = "#2ee6a0"
RED = "#ff5c7a"
DARK_TEXT = "#24104f"
FONT = "Segoe UI"         # init_fonts() picks another font if this one is missing


def init_fonts(root):
    """Choose the first nice font that exists on this computer."""
    global FONT
    available = set(tkfont.families(root))
    for name in ("Segoe UI", "SF Pro Display", "Helvetica Neue", "Inter", "Ubuntu", "DejaVu Sans", "Arial"):
        if name in available:
            FONT = name
            return


def font(size, bold=False):
    """Sizes are in pixels (negative numbers) so the layout looks the same on every computer."""
    return (FONT, -max(8, int(round(size))), "bold" if bold else "normal")


_FONTS = {}


def text_width(text, size, bold=True):
    key = (FONT, int(size), bold)
    measure = _FONTS.get(key)
    if measure is None:
        measure = _FONTS[key] = tkfont.Font(family=FONT, size=-int(size), weight="bold" if bold else "normal")
    return measure.measure(text)


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def mix(first, second, amount):
    """Blend two #rrggbb colours: amount 0 gives `first`, 1 gives `second`."""
    a, b = hex_to_rgb(first), hex_to_rgb(second)
    return "#%02x%02x%02x" % tuple(round(a[i] * (1 - amount) + b[i] * amount) for i in range(3))


def shorten(text, limit=14):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


# ---------------------------------------------------------------- generated images
_IMAGES = {}


def clear_cache():
    """Forget every generated image (they belong to one Tk window)."""
    _IMAGES.clear()
    _FONTS.clear()


def encode_png(width, height, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def photo(key, make_png):
    """A cached tk.PhotoImage built from PNG bytes, or None if this Tk cannot show PNG images."""
    image = _IMAGES.get(key)
    if image is None:
        try:
            image = tk.PhotoImage(data=base64.b64encode(make_png()).decode("ascii"))
        except tk.TclError:
            image = False
        _IMAGES[key] = image
    return image or None


def pill_png(width, height, left, right, border=None, glossy=True):
    """A fully rounded button: colour fades left to right, lighter on top, soft edge, thin border."""
    r = height / 2.0
    lc, rc = hex_to_rgb(left), hex_to_rgb(right)
    bc = hex_to_rgb(border) if border else None
    span = max(1, width - 1)
    grad = [tuple(lc[i] + (rc[i] - lc[i]) * x / span for i in range(3)) for x in range(width)]
    hx, hy = width / 2.0, height / 2.0
    inner = hx - r
    transparent = b"\x00\x00\x00\x00"
    rows = []
    for y in range(height):
        py = y + 0.5 - hy
        t = y / max(1, height - 1)
        lift = 0.20 * max(0.0, 1.0 - t * 2.1) if glossy else 0.0
        keep = 1.0 - (0.16 * max(0.0, (t - 0.5) / 0.5) if glossy else 0.0)
        row = bytearray()
        for x in range(width):
            qx = abs(x + 0.5 - hx) - inner
            d = (math.hypot(qx, py) if qx > 0 else abs(py)) - r
            if d >= 0.5:
                row += transparent
                continue
            alpha = 255 if d <= -0.5 else int((0.5 - d) * 255)
            cr, cg, cb = grad[x]
            cr, cg, cb = (cr + (255 - cr) * lift) * keep, (cg + (255 - cg) * lift) * keep, (cb + (255 - cb) * lift) * keep
            if bc is not None and d > -2.0:
                m = min(1.0, d + 2.0)
                cr, cg, cb = cr + (bc[0] - cr) * m, cg + (bc[1] - cg) * m, cb + (bc[2] - cb) * m
            row += bytes((min(255, int(cr)), min(255, int(cg)), min(255, int(cb)), alpha))
        rows.append(row)
    return encode_png(width, height, rows)


def backdrop_png(cols=240, rows_n=150):
    """The soft purple glow behind everything (small image, enlarged 6x by Tk)."""
    base, core, side = hex_to_rgb(BG), hex_to_rgb("#34127f"), hex_to_rgb("#4d20b8")
    rows = []
    for y in range(rows_n):
        v = y / (rows_n - 1)
        row = bytearray()
        for x in range(cols):
            u = x / (cols - 1)
            i1 = max(0.0, 1.0 - math.hypot((u - 0.5) * 1.3, v - 0.40) / 0.72) ** 2
            i2 = max(0.0, 1.0 - math.hypot((u - 0.93) * 1.1, v - 0.10) / 0.36) ** 2 * 0.8
            i3 = max(0.0, 1.0 - math.hypot((u - 0.06) * 1.1, v - 0.92) / 0.36) ** 2 * 0.7
            edge = min(1.0, min(u, 1 - u, v, 1 - v) / 0.03)
            pixel = [min(255, int(base[k] + ((core[k] - base[k]) * i1 + (side[k] - base[k]) * (i2 + i3) * 0.7) * edge))
                     for k in range(3)]
            row += bytes((pixel[0], pixel[1], pixel[2], 255))
        rows.append(row)
    return encode_png(cols, rows_n, rows)


def backdrop_image():
    image = _IMAGES.get("backdrop")
    if image is None:
        try:
            small = tk.PhotoImage(data=base64.b64encode(backdrop_png()).decode("ascii"))
            image = small.zoom(6, 6)
        except tk.TclError:
            image = False
        _IMAGES["backdrop"] = image
    return image or None


# --------------------------------------------------------------------- drawing helpers
def round_rect(canvas, x1, y1, x2, y2, radius, **options):
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, **options)


def star_points(cx, cy, radius, points=4, inner=0.38, rotation=-90):
    coords = []
    for i in range(points * 2):
        r = radius if i % 2 == 0 else radius * inner
        angle = math.radians(rotation + i * 180 / points)
        coords += [cx + r * math.cos(angle), cy + r * math.sin(angle)]
    return coords


def question_mark(canvas, x, y, size, depth=10):
    """A big 3D-looking question mark: a dark extruded body with a lit face (like the design)."""
    for k in range(depth, 0, -1):
        shade = mix("#14063a", "#4a1fb4", 1 - k / depth)
        canvas.create_text(x + k * 1.7, y + k * 1.7, text="?", font=font(size, True), fill=shade, tags="decor")
    canvas.create_text(x - 2, y - 2, text="?", font=font(size, True), fill="#d8c0ff", tags="decor")
    canvas.create_text(x, y, text="?", font=font(size, True), fill="#9a5df5", tags="decor")


def draw_backdrop(canvas, width, height, marks=True):
    """Soft purple glow plus three big 3D question marks peeking in from the corners."""
    image = backdrop_image()
    if image is not None:
        canvas.create_image(width / 2, height / 2, image=image, tags="decor")
    if marks:
        question_mark(canvas, width - 70, 80, 360)
        question_mark(canvas, width - 10, height * 0.58, 130, depth=7)
        question_mark(canvas, 56, height - 40, 320)
    canvas.tag_lower("decor")


def glow_card(canvas, x1, y1, x2, y2, tags, radius=30, fill=CARD_FILL, edge=CARD_EDGE, glow=GLOW, rings=9,
              strength=0.55):
    """A rounded panel with a soft glowing edge (the framed options box in the design)."""
    for i in range(rings, 0, -1):
        grow = i * 2.4
        k = ((rings - i + 1) / (rings + 1)) ** 2.2 * strength
        round_rect(canvas, x1 - grow, y1 - grow, x2 + grow, y2 + grow, radius + grow, fill="",
                   outline=mix(BACKDROP_MID, glow, k), width=3, tags=tags)
    round_rect(canvas, x1, y1, x2, y2, radius, fill=fill, outline=edge, width=2, tags=tags)


def chip(canvas, x, cy, text, fill, fg, tags, size=12, pad=14, height=24, anchor="w"):
    """A small rounded label. `x` is its left edge (anchor "w"), centre ("center") or right edge ("e")."""
    width = text_width(text, size) + 2 * pad
    left = x if anchor == "w" else x - width / 2 if anchor == "center" else x - width
    round_rect(canvas, left, cy - height / 2, left + width, cy + height / 2, height / 2, fill=fill, outline="", tags=tags)
    canvas.create_text(left + width / 2, cy, text=text, font=font(size, True), fill=fg, tags=tags)
    return left + width


def fit_lines(text, max_width, sizes, max_lines=3):
    """Choose the biggest font size that wraps the text into at most `max_lines` lines."""
    words = text.split()
    for size in sizes:
        lines, current = [], []
        for word in words:
            if current and text_width(" ".join(current + [word]), size) > max_width:
                lines.append(current)
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(current)
        if len(lines) <= max_lines:
            return size, lines
    return sizes[-1], lines


def draw_rich_text(canvas, cx, cy, text, max_width, sizes=(34, 30, 27, 24), accent_words=2, tags="ui",
                   base=TEXT, accent=ACCENT, max_lines=3):
    """Bold centred text whose last few words are purple, like 'digital strategy?' in the design."""
    size, lines = fit_lines(text, max_width, sizes, max_lines)
    gap = int(size * 1.25)
    space = text_width(" ", size)
    total = sum(len(line) for line in lines)
    first_accent = max(0, total - accent_words)
    y = cy - (len(lines) - 1) * gap / 2
    index = 0
    for line in lines:
        widths = [text_width(word, size) for word in line]
        x = cx - (sum(widths) + space * (len(line) - 1)) / 2
        for word, width in zip(line, widths):
            canvas.create_text(x, y, text=word, anchor="w", font=font(size, True),
                               fill=accent if index >= first_accent else base, tags=tags)
            x += width + space
            index += 1
        y += gap
    return size, len(lines)


# ------------------------------------------------------------------------- buttons
BUTTON_STYLES = {
    #  name:            (left,      right,     border,    text colour)
    "primary": ("#7c4dff", "#5aa7ff", "#cbbcff", "#ffffff"),
    "primary_hover": ("#9468ff", "#78bbff", "#ffffff", "#ffffff"),
    "option": ("#7c4dff", "#5aa7ff", "#cbbcff", "#ffffff"),
    "option_hover": ("#9468ff", "#78bbff", "#ffffff", "#ffffff"),
    "gold": ("#ffb21e", "#ffe27d", "#fff1b8", DARK_TEXT),
    "gold_hover": ("#ffc03d", "#fff0a0", "#ffffff", DARK_TEXT),
    "ghost": ("#170c40", "#170c40", "#5a49b8", TEXT),
    "ghost_hover": ("#23125c", "#23125c", "#9a86ff", "#ffffff"),
    "correct": ("#0fa968", "#4ee3b0", "#c6ffe6", "#ffffff"),
    "wrong": ("#d61f4d", "#ff7a93", "#ffd0d9", "#ffffff"),
    "dim": ("#1b1050", "#1d2158", "#2d2670", "#7e72b8"),
    "disabled": ("#241a58", "#262a62", "#332c70", "#7e72b8"),
}
FLAT_STYLES = ("ghost", "ghost_hover", "dim", "disabled")
BADGE_FILL = {"correct": "#0a6b47", "wrong": "#8a1635", "dim": "#241658", "disabled": "#2d2266",
              "ghost": "#2b1a78", "ghost_hover": "#3a2494"}


def pill_image(width, height, style):
    left, right, border, _ = BUTTON_STYLES[style]
    return photo(("pill", width, height, style),
                 lambda: pill_png(width, height, left, right, border, glossy=style not in FLAT_STYLES))


class CanvasButton:
    """A clickable pill drawn on a canvas, with hover and press effects.

    Set text / style / enabled / badge / mark with config(); draw(cx, cy) places it. Style names are in
    BUTTON_STYLES; `mark` ("check" or "cross") replaces the letter badge with a tick or a cross.
    """
    _counter = 0

    def __init__(self, canvas, text, command, style="primary", width=340, height=54, size=18, badge=None,
                 align="center", bold=True, group="ui"):
        CanvasButton._counter += 1
        self.canvas, self.text, self.command = canvas, text, command
        self.style, self.width, self.height, self.size = style, width, height, size
        self.badge, self.align, self.bold, self.group = badge, align, bold, group
        self.mark = None
        self.enabled = True
        self.hover = self.pressed = self.drawn = False
        self.tag = f"button{CanvasButton._counter}"
        self.cx = self.cy = 0
        self.items = {}

    # ---- state
    def config(self, **options):
        for key, value in options.items():
            setattr(self, key, value)
        self._apply()

    def invoke(self):
        if self.enabled and self.command:
            self.command()

    def _style_now(self):
        if self.hover and self.enabled and f"{self.style}_hover" in BUTTON_STYLES:
            return f"{self.style}_hover"
        return self.style

    # ---- drawing
    def draw(self, cx, cy):
        c = self.canvas
        self.cx, self.cy = cx, cy
        c.delete(self.tag)
        tags = (self.tag, self.group)
        w, h = self.width, self.height
        left_edge = cx - w / 2
        image = pill_image(w, h, self._style_now())
        if image is not None:
            self.items["bg"] = c.create_image(cx, cy, image=image, tags=tags)
        else:
            self.items["bg"] = round_rect(c, left_edge, cy - h / 2, left_edge + w, cy + h / 2, h / 2, fill="#7c4dff",
                                          outline="#cbbcff", width=2, tags=tags)
        if self.badge:
            bx = left_edge + h / 2 + 10
            r = h * 0.36
            self.items["badge"] = c.create_oval(bx - r, cy - r, bx + r, cy + r, width=2, tags=tags)
            self.items["letter"] = c.create_text(bx, cy, font=font(r * 1.05, True), tags=tags)
            u = r / 16
            self.items["check"] = c.create_line(bx - 7 * u, cy, bx - 2 * u, cy + 6 * u, bx + 8 * u, cy - 6 * u,
                                                fill="white", width=3 * u + 1, capstyle="round", joinstyle="round",
                                                tags=tags, state="hidden")
            self.items["cross1"] = c.create_line(bx - 6 * u, cy - 6 * u, bx + 6 * u, cy + 6 * u, fill="white",
                                                 width=3 * u + 1, capstyle="round", tags=tags, state="hidden")
            self.items["cross2"] = c.create_line(bx - 6 * u, cy + 6 * u, bx + 6 * u, cy - 6 * u, fill="white",
                                                 width=3 * u + 1, capstyle="round", tags=tags, state="hidden")
            text_x, anchor, wrap = left_edge + h + 14, "w", w - h - 36
        elif self.align == "left":
            text_x, anchor, wrap = left_edge + 26, "w", w - 52
        else:
            text_x, anchor, wrap = cx, "center", w - 36
        self.items["text"] = c.create_text(text_x, cy, anchor=anchor, width=wrap, justify="left" if anchor == "w" else "center",
                                           font=font(self.size, self.bold), tags=tags)
        for sequence, handler in (("<Enter>", self._enter), ("<Leave>", self._leave),
                                  ("<ButtonPress-1>", self._press), ("<ButtonRelease-1>", self._release)):
            c.tag_bind(self.tag, sequence, handler)
        self.drawn = True
        self._apply()

    def _apply(self):
        """Update the look of an already drawn button (no items are deleted, so hover never flickers)."""
        if not self.drawn:
            return
        c, style = self.canvas, self._style_now()
        left, right, border, text_color = BUTTON_STYLES[style]
        try:
            image = pill_image(self.width, self.height, style)
            if image is not None:
                c.itemconfigure(self.items["bg"], image=image)
            else:
                c.itemconfigure(self.items["bg"], fill=left, outline=border)
            c.itemconfigure(self.items["text"], text=self.text, fill=text_color)
            if self.badge:
                fill = BADGE_FILL.get(style, "#2a0f78")
                c.itemconfigure(self.items["badge"], fill=fill, outline=mix(fill, "#ffffff", 0.35))
                c.itemconfigure(self.items["letter"], text=str(self.badge), fill="#ffffff",
                                state="hidden" if self.mark or not self.text else "normal")
                c.itemconfigure(self.items["check"], state="normal" if self.mark == "check" else "hidden")
                for key in ("cross1", "cross2"):
                    c.itemconfigure(self.items[key], state="normal" if self.mark == "cross" else "hidden")
        except tk.TclError:
            pass

    # ---- events
    def _enter(self, _event):
        self.hover = True
        if self.enabled:
            self.canvas.configure(cursor="hand2")
        self._apply()

    def _leave(self, _event):
        self.hover = self.pressed = False
        self.canvas.configure(cursor="")
        self._apply()

    def _press(self, _event):
        if self.enabled:
            self.pressed = True
            self.canvas.move(self.tag, 0, 1)

    def _release(self, _event):
        if self.pressed:
            self.pressed = False
            self.canvas.move(self.tag, 0, -1)
            if self.tag in self.canvas.gettags("current"):
                self.invoke()


class IconButton:
    """A small round icon button: "pause", "play", "sound_on" or "sound_off"."""
    _counter = 0

    def __init__(self, canvas, kind, command, size=44, group="ui"):
        IconButton._counter += 1
        self.canvas, self.kind, self.command, self.size, self.group = canvas, kind, command, size, group
        self.tag = f"icon{IconButton._counter}"
        self.hover = self.drawn = False
        self.cx = self.cy = 0
        self.bg_item = None

    def draw(self, cx, cy):
        c, r = self.canvas, self.size / 2
        self.cx, self.cy = cx, cy
        c.delete(self.tag)
        self.bg_item = c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#1a0e47", outline="#4b3aa8", width=2,
                                     tags=(self.tag, self.group))
        self._draw_icon()
        for sequence, handler in (("<Enter>", self._enter), ("<Leave>", self._leave),
                                  ("<ButtonRelease-1>", self._release)):
            c.tag_bind(self.tag, sequence, handler)
        self.drawn = True

    def set_kind(self, kind):
        self.kind = kind
        if self.drawn:
            self.canvas.delete(self.tag + "i")
            self._draw_icon()

    def invoke(self):
        if self.command:
            self.command()

    def _draw_icon(self):
        c, cx, cy = self.canvas, self.cx, self.cy
        tags = (self.tag, self.group, self.tag + "i")
        white, u = "#f4f0ff", self.size / 44
        if self.kind == "pause":
            for dx in (-6, 3):
                round_rect(c, cx + (dx - 1) * u, cy - 9 * u, cx + (dx + 5) * u, cy + 9 * u, 2 * u, fill=white, outline="", tags=tags)
        elif self.kind == "play":
            c.create_polygon(cx - 5 * u, cy - 9 * u, cx + 9 * u, cy, cx - 5 * u, cy + 9 * u, fill=white, outline="", tags=tags)
        else:
            c.create_polygon(cx - 10 * u, cy - 4 * u, cx - 5 * u, cy - 4 * u, cx + 1 * u, cy - 9 * u, cx + 1 * u, cy + 9 * u,
                             cx - 5 * u, cy + 4 * u, cx - 10 * u, cy + 4 * u, fill=white, outline="", tags=tags)
            if self.kind == "sound_on":
                for k in (1, 2):
                    rr = (3 + 4 * k) * u
                    c.create_arc(cx + 1 * u - rr, cy - rr, cx + 1 * u + rr, cy + rr, start=-45, extent=90, style="arc",
                                 outline=white, width=max(2, 2 * u), tags=tags)
            else:
                c.create_line(cx + 6 * u, cy - 6 * u, cx + 14 * u, cy + 6 * u, fill=RED, width=max(2, 2.4 * u),
                              capstyle="round", tags=tags)
                c.create_line(cx + 6 * u, cy + 6 * u, cx + 14 * u, cy - 6 * u, fill=RED, width=max(2, 2.4 * u),
                              capstyle="round", tags=tags)

    def _enter(self, _event):
        self.hover = True
        self.canvas.configure(cursor="hand2")
        self.canvas.itemconfigure(self.bg_item, fill="#2c1a78", outline="#8f7bff")

    def _leave(self, _event):
        self.hover = False
        self.canvas.configure(cursor="")
        self.canvas.itemconfigure(self.bg_item, fill="#1a0e47", outline="#4b3aa8")

    def _release(self, _event):
        if self.tag in self.canvas.gettags("current"):
            self.invoke()


class TimerRing:
    """A circle that empties as time runs out, with the seconds left in the middle."""

    def __init__(self, canvas, size=92):
        self.canvas, self.size = canvas, size
        self.center = (0, 0)
        self.left, self.total, self.off = 1.0, 1.0, True
        self.value_text = ""

    def draw(self, cx, cy):
        self.center = (cx, cy)
        self._redraw()

    def set(self, left, total):
        self.left, self.total, self.off = left, total, False
        self._redraw()

    def set_off(self):
        self.off = True
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("ring")
        cx, cy = self.center
        r, tags = self.size / 2 - 8, ("ring", "ui")
        fraction = 1.0 if self.off else max(0.0, min(1.0, self.left / self.total))
        color = BLUE if fraction > 0.5 else GOLD if fraction > 0.25 else RED
        for grow, amount in ((11, 0.10), (6, 0.20)):
            c.create_oval(cx - r - grow, cy - r - grow, cx + r + grow, cy + r + grow, outline=mix(BACKDROP_MID, color, amount),
                          width=3, tags=tags)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#26165f", width=9, tags=tags, fill=CARD_FILL)
        if self.off:
            self.value_text = "∞"
            c.create_text(cx, cy, text="∞", font=font(34, True), fill=MUTED, tags=tags)
            return
        if fraction > 0:
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-max(1.0, 359.9 * fraction), style="arc",
                         outline=color, width=9, tags=tags)
        self.value_text = str(math.ceil(self.left)) if self.left > 0 else "0"
        pulse = fraction <= 0.25 and int(self.left * 3) % 2 == 0
        c.create_text(cx, cy, text=self.value_text, font=font(34 if pulse else 30, True), fill=color, tags=tags)


# ---------------------------------------------------------------------------- sound
class Sound:
    """Short beeps through the standard winsound module (Windows only). Silent on other systems."""

    PATTERNS = {
        "correct": [(660, 80), (880, 80), (1175, 170)],
        "wrong": [(260, 190), (196, 320)],
        "timeup": [(330, 150), (262, 300)],
        "tick": [(1000, 35)],
        "count": [(600, 110)],
        "go": [(880, 260)],
        "win": [(523, 130), (659, 130), (784, 130), (1047, 380)],
        "tie": [(523, 150), (523, 220)],
        "click": [(740, 25)],
        "swoosh": [(500, 30), (700, 30), (950, 45)],
    }

    def __init__(self):
        self.enabled = True
        try:
            import winsound
            self._beep = winsound.Beep
        except ImportError:
            self._beep = None
        self._queue = queue.Queue()
        if self._beep is not None:
            threading.Thread(target=self._worker, daemon=True).start()

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

    def play(self, name):
        if self.enabled and self._beep is not None and name in self.PATTERNS and self._queue.qsize() < 4:
            self._queue.put(name)

    def _worker(self):
        while True:
            name = self._queue.get()
            for frequency, milliseconds in self.PATTERNS[name]:
                try:
                    self._beep(frequency, milliseconds)
                except Exception:
                    break


# -------------------------------------------------------------------------- effects
class Effects:
    """Animations drawn above everything on a canvas (tag "fx"): a big word popping up, star bursts,
    floating points and confetti. cancel() stops and removes all of them at once."""

    COLORS = [GOLD, PINK, "#3de0ff", GREEN, "#c9a2ff", ORANGE, "#ffffff"]

    def __init__(self, canvas):
        self.canvas = canvas
        self.jobs = set()
        self.pieces = []
        self.counter = 0
        self.confetti_left = 0

    def _later(self, ms, fn):
        job = None

        def run():
            self.jobs.discard(job)
            try:
                fn()
            except tk.TclError:
                pass        # the window was closed

        job = self.canvas.after(ms, run)
        self.jobs.add(job)

    def cancel(self):
        for job in list(self.jobs):
            try:
                self.canvas.after_cancel(job)
            except tk.TclError:
                pass
        self.jobs.clear()
        self.pieces = []
        try:
            self.canvas.delete("fx")
        except tk.TclError:
            pass

    def banner(self, cx, cy, text, color=GOLD, sub=None, sub_color="#ffffff", size=54, shake=False, hold=1000,
               on_done=None):
        """A big word that pops in, stays for `hold` ms, then drifts up and fades."""
        c = self.canvas
        self.counter += 1
        tag = f"banner{self.counter}"
        started = time.monotonic()
        pop_ms, fade_ms = 340, 320
        total = pop_ms + hold + fade_ms

        def frame():
            t = (time.monotonic() - started) * 1000
            c.delete(tag)
            if t >= total:
                if on_done:
                    on_done()
                return
            scale = 0.45 + 0.55 * ease_out_back(t / pop_ms) if t < pop_ms else 1.0
            fade = max(0.0, (t - pop_ms - hold) / fade_ms)
            px = cx + (math.sin(t / 38.0) * 9 * max(0.0, 1 - t / 420.0) if shake else 0)
            py = cy - fade * 18
            fsize = max(10, int(size * scale))
            tags = (tag, "fx")
            outline = mix("#2a0b6e", BACKDROP_MID, fade)
            c.create_text(px, py + fsize * 0.10, text=text, font=font(fsize, True), fill=mix("#12043a", BACKDROP_MID, fade), tags=tags)
            r = max(2, fsize * 0.05)
            for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (r, -r), (-r, r), (r, r)):
                c.create_text(px + dx, py + dy, text=text, font=font(fsize, True), fill=outline, tags=tags)
            c.create_text(px, py, text=text, font=font(fsize, True), fill=mix(color, BACKDROP_MID, fade), tags=tags)
            if sub and t > 200:
                c.create_text(px, py + fsize * 0.80, text=sub, font=font(max(12, int(size * 0.34)), True),
                              fill=mix(sub_color, BACKDROP_MID, fade), tags=tags)
            self._later(33, frame)

        frame()

    def burst(self, cx, cy, count=22, power=7.5):
        """Sparkle stars flying out from a point."""
        c = self.canvas
        particles = []
        for _ in range(count):
            angle, speed = random.uniform(0, 2 * math.pi), random.uniform(2.5, power)
            item = c.create_polygon(star_points(cx, cy, random.uniform(5, 11)), fill=random.choice(self.COLORS),
                                    outline="", tags="fx")
            particles.append([item, math.cos(angle) * speed, math.sin(angle) * speed - 2.0])
        step_count = [0]

        def step():
            step_count[0] += 1
            for p in particles:
                c.move(p[0], p[1], p[2])
                p[2] += 0.35
                p[1] *= 0.97
            if step_count[0] >= 28:
                for p in particles:
                    c.delete(p[0])
                return
            self._later(30, step)

        step()

    def float_text(self, x, y, text, color=GREEN, size=30):
        """A short text (like +10) that rises and fades."""
        c = self.canvas
        self.counter += 1
        tag = f"float{self.counter}"
        started = time.monotonic()

        def frame():
            t = (time.monotonic() - started) / 0.8
            c.delete(tag)
            if t >= 1:
                return
            fade = max(0.0, (t - 0.55) / 0.45)
            y_now = y - 44 * t
            c.create_text(x + 2, y_now + 2, text=text, font=font(size, True), fill=mix("#12043a", BACKDROP_MID, fade), tags=(tag, "fx"))
            c.create_text(x, y_now, text=text, font=font(size, True), fill=mix(color, BACKDROP_MID, fade), tags=(tag, "fx"))
            self._later(33, frame)

        frame()

    def confetti(self, width, count=130, frames=190):
        c = self.canvas
        for _ in range(count):
            x, y, size = random.randint(0, int(width)), random.randint(-520, 0), random.randint(7, 13)
            item = (c.create_polygon(star_points(x, y, size * 0.8), fill=random.choice(self.COLORS), outline="", tags="fx")
                    if random.random() < 0.2 else
                    c.create_rectangle(x, y, x + size, y + size * 0.6, outline="", fill=random.choice(self.COLORS), tags="fx"))
            self.pieces.append((item, random.uniform(-1.2, 1.2), random.uniform(3.0, 6.5)))
        self.confetti_left = frames
        self._confetti_step()

    def _confetti_step(self):
        self.confetti_left -= 1
        for item, dx, dy in self.pieces:
            self.canvas.move(item, dx, dy)
        if self.confetti_left <= 0:
            for item, _dx, _dy in self.pieces:
                self.canvas.delete(item)
            self.pieces = []
        else:
            self._later(30, self._confetti_step)
