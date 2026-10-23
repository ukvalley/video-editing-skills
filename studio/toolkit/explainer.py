"""16:9 SaaS-explainer motion-graphics engine (no footage): light canvas with drifting gradient orbs, floating UI
cards with soft shadows, kinetic type, icon bubbles, counters, hand-cursor taps.

All coordinates are in a 1920x1080 design space; init(scale) sets the render scale (0.5 -> 960x540 animatic).
Sprites are cached at render scale, so static elements cost one paste per frame.

    import explainer as X
    X.init(0.5)
    im = X.background(t)
    X.place(im, X.text("Hello", 90, "black"), 960, 540, a=0.8)

Another brand: X.brand(a="#hex", b="#hex", ink=..., mute=..., accent3=...) before anything is drawn re-colours
gradients, canvas, orbs, shadows and the explainer_fx momentum layer (defaults = violet->blue).

Fonts: Montserrat Black/ExtraBold (assets/fonts) for headlines, Avenir Next (system) for UI/body text.
Emoji icons come from Apple Color Emoji. Images are paths relative to the studio root.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1920, 1080
S = 1.0; RW, RH = W, H
TVA = (104, 60, 236); TVB = (24, 92, 232); INK = (22, 24, 52); MUTE = (110, 116, 150)
RED = (236, 72, 86); GRN = (24, 178, 120); AMB = (245, 158, 11); WHITE = (255, 255, 255)
ACC3 = (236, 110, 220)  # third accent (particles, orbs); pink by default
BG = ((246, 245, 255), (234, 232, 252))  # canvas top / bottom
SHADOW = (40, 30, 110)  # drop-shadow tint
BLOB = (150, 110, 255)  # light blob that sweeps across scene changes
_C = {}


def hexrgb(c): return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if isinstance(c, str) else tuple(c)


def _mix(c, d, k): return tuple(int(round(x + (y - x) * k)) for x, y in zip(c, d))


def brand(a=None, b=None, ink=None, mute=None, accent3=None, bg=None, orbs=None):
    """re-colour the engine for another brand (call before init/render). Defaults are violet->blue.
    a/b = gradient pair (headline highlights, pills, rings, grid), ink = text, mute = secondary text,
    accent3 = third accent, bg = (top, bottom) canvas colours (default: a very light tint of a),
    orbs = list of 4 orb colours (default: derived from a, b, accent3). Colours are '#rrggbb' or (r, g, b)."""
    global TVA, TVB, INK, MUTE, ACC3, BG, SHADOW, BLOB
    if a: TVA = hexrgb(a)
    if b: TVB = hexrgb(b)
    if ink: INK = hexrgb(ink)
    if mute: MUTE = hexrgb(mute)
    if accent3: ACC3 = hexrgb(accent3)
    if bg: BG = tuple(hexrgb(c) for c in bg)
    elif a: BG = (_mix(TVA, WHITE, 0.955), _mix(TVA, WHITE, 0.9))
    if a: SHADOW = _mix(TVA, (0, 0, 0), 0.6); BLOB = _mix(TVA, WHITE, 0.3)
    if orbs: ORBS[:] = [(hexrgb(c),) + o[1:] for c, o in zip(orbs, ORBS)]
    elif a or b or accent3:
        cols = [_mix(TVA, WHITE, 0.25), _mix(TVB, WHITE, 0.2), _mix(ACC3, WHITE, 0.05), _mix(TVA, WHITE, 0.35)]
        ORBS[:] = [(c,) + o[1:] for c, o in zip(cols, ORBS)]
    _C.clear()
    try:
        import explainer_fx; explainer_fx.PINK = ACC3
    except ImportError:
        pass


def init(scale=1.0, w=1920, h=1080):
    """render scale and canvas (design px): 1920x1080 landscape, 1080x1920 for 9:16"""
    global S, RW, RH, W, H
    W, H = w, h; S = scale; RW, RH = int(W * S), int(H * S); _C.clear()


def sx(v): return v * W / 1920   # map a landscape-designed decorative x/y onto the current canvas
def sy(v): return v * H / 1080


def px(v): return int(round(v * S))


# ---------------------------------------------------------------- easing / timing
def clip(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def prog(t, t0, d): return clip((t - t0) / d) if d > 0 else float(t >= t0)
def out_cubic(x): return 1 - (1 - x) ** 3
def in_cubic(x): return x ** 3
def inout(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def out_back(x, s=1.6): x -= 1; return 1 + (s + 1) * x ** 3 + s * x ** 2
def out_expo(x): return 1 if x >= 1 else 1 - 2 ** (-10 * x)
def lerp(a, b, k): return a + (b - a) * k


def life(t, t0, t1=None, din=0.45, dout=0.35):
    """0..1 in-progress (eased later by caller) and 0..1 visibility; returns (k_in, alpha)"""
    k = prog(t, t0, din)
    a = k if t1 is None else min(k, 1 - prog(t, t1 - dout, dout))
    return k, a


def cached(key, fn):
    if key not in _C: _C[key] = fn()
    return _C[key]


# ---------------------------------------------------------------- fonts / text
FONTS = {"black": (f"{ROOT}/assets/fonts/Montserrat-Black.ttf", 0), "xbold": (f"{ROOT}/assets/fonts/Montserrat-ExtraBold.ttf", 0),
         "heavy": ("/System/Library/Fonts/Avenir Next.ttc", 8), "bold": ("/System/Library/Fonts/Avenir Next.ttc", 0),
         "demi": ("/System/Library/Fonts/Avenir Next.ttc", 2), "med": ("/System/Library/Fonts/Avenir Next.ttc", 5),
         "reg": ("/System/Library/Fonts/Avenir Next.ttc", 7)}


def font(weight, size):
    f, i = FONTS[weight]
    return cached(("F", weight, px(size)), lambda: ImageFont.truetype(f, max(4, px(size)), index=i))


def grad_img(w, h, a=None, b=None, angle=0):
    a = TVA if a is None else a; b = TVB if b is None else b
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]; y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    k = np.clip(x * math.cos(angle) + y * math.sin(angle), 0, 1) if angle else np.repeat(x, h, 0)
    k = k / max(1e-6, k.max())
    arr = np.array(a, np.float32)[None, None] * (1 - k[..., None]) + np.array(b, np.float32)[None, None] * k[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def text(s, size, weight="black", color=INK, track=0, grad=None):
    """tight RGBA sprite of one line of text; grad=(a,b) fills with a horizontal gradient"""
    def mk():
        f = font(weight, size); tr = px(track)
        if tr:
            ws = [f.getbbox(c)[2] - f.getbbox(c)[0] if c != " " else f.getlength(" ") for c in s]
            tw = int(sum(f.getlength(c) for c in s) + tr * (len(s) - 1)) + 4
        else:
            tw = int(f.getlength(s)) + 4
        asc, desc = f.getmetrics(); h = asc + desc
        m = Image.new("L", (tw + px(8), h + px(8)), 0); d = ImageDraw.Draw(m)
        if tr:
            x = px(2)
            for c in s:
                d.text((x, px(2)), c, font=f, fill=255); x += f.getlength(c) + tr
        else:
            d.text((px(2), px(2)), s, font=f, fill=255)
        bb = m.getbbox() or (0, 0, 1, 1)
        top = px(2) + int(asc * 0.18)  # crop to font metrics (not glyph bbox) so words share a baseline
        m = m.crop((bb[0], top, bb[2], px(2) + asc + int(desc * 0.6)))
        fill = grad_img(m.width, m.height, *grad) if grad else Image.new("RGBA", m.size, color + (255,))
        fill.putalpha(m); return fill
    return cached(("T", s, size, weight, color, track, grad), mk)


def para(lines, size, weight="demi", color=INK, lh=1.25, align="center"):
    def mk():
        sps = [text(l, size, weight, color) for l in lines]
        w = max(s.width for s in sps); step = px(size * lh); h = step * (len(sps) - 1) + sps[-1].height
        im = Image.new("RGBA", (w, h))
        for i, s in enumerate(sps):
            x = (w - s.width) // 2 if align == "center" else 0
            im.alpha_composite(s, (x, i * step))
        return im
    return cached(("P", tuple(lines), size, weight, color, lh, align), mk)


EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"


def emoji(ch, size):
    def mk():
        f = ImageFont.truetype(EMOJI, 160)
        im = Image.new("RGBA", (200, 200)); ImageDraw.Draw(im).text((20, 20), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox()); k = px(size) / max(im.size)
        return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    return cached(("E", ch, size), mk)


# ---------------------------------------------------------------- shapes / sprites
def shadowed(content, blur=26, dy=18, op=0.16, pad=None, tint=None):
    """content sprite on a soft drop shadow; result is centred on the content (symmetric padding)"""
    tint = tint or SHADOW
    pad = px(pad if pad is not None else blur * 2 + dy)
    w, h = content.width + 2 * pad, content.height + 2 * pad
    a = content.getchannel("A").point(lambda v: int(v * op))
    sh = Image.new("RGBA", (w, h), tint + (0,)); sm = Image.new("L", (w, h), 0); sm.paste(a, (pad, pad + px(dy)))
    sh.putalpha(sm.filter(ImageFilter.GaussianBlur(px(blur))))
    sh.alpha_composite(content, (pad, pad)); return sh


def rrect(w, h, r, fill=WHITE, outline=None, ow=2, grad=None):
    w, h = px(w), px(h)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], px(r), fill=255)
    im = grad_img(w, h, *grad) if grad else Image.new("RGBA", (w, h), fill + (255,) if len(fill) == 3 else fill)
    im.putalpha(m)
    if outline:
        ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], px(r), outline=outline, width=max(1, px(ow)))
    return im


def card(w, h, r=28, fill=WHITE, shadow=True, **kw):
    return cached(("CARD", w, h, r, fill, shadow, tuple(kw.items())),
                  lambda: shadowed(rrect(w, h, r, fill, **kw)) if shadow else rrect(w, h, r, fill, **kw))


def circle(d, fill=WHITE, grad=None):
    d = px(d); m = Image.new("L", (d * 4, d * 4), 0); ImageDraw.Draw(m).ellipse([0, 0, d * 4 - 1, d * 4 - 1], fill=255)
    m = m.resize((d, d), Image.LANCZOS)
    im = grad_img(d, d, *grad, angle=0.8) if grad else Image.new("RGBA", (d, d), fill + (255,))
    im.putalpha(m); return im


def bubble(ch, d=120, fill=WHITE, icon_k=0.5, grad=None):
    """emoji icon in a white (or gradient) circle with shadow"""
    def mk():
        c = circle(d, fill, grad); e = emoji(ch, d * icon_k)
        c.alpha_composite(e, ((c.width - e.width) // 2, (c.height - e.height) // 2)); return shadowed(c, 18, 12, 0.18)
    return cached(("BUB", ch, d, fill, icon_k, grad), mk)


def pill(label, size=34, weight="demi", fg=WHITE, grad=None, fill=None, padx=34, pady=16, icon=None, shadow=True):
    grad = grad or (TVA, TVB)
    def mk():
        t = text(label, size, weight, fg); ic = emoji(icon, size * 1.1) if icon else None
        iw = ic.width + px(14) if ic else 0
        w = t.width + iw + px(padx * 2); h = t.height + px(pady * 2)
        m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=255)
        bg = grad_img(w, h, *grad) if fill is None else Image.new("RGBA", (w, h), fill + (255,))
        bg.putalpha(m)
        if ic: bg.alpha_composite(ic, (px(padx), (h - ic.height) // 2))
        bg.alpha_composite(t, (px(padx) + iw, (h - t.height) // 2))
        return shadowed(bg, 14, 8, 0.2) if shadow else bg
    return cached(("PILL", label, size, weight, fg, grad, fill, padx, pady, icon, shadow), mk)


def image(path, w=None, h=None):
    def mk():
        im = Image.open(path if os.path.isabs(path) else os.path.join(ROOT, path)).convert("RGBA")
        k = px(w) / im.width if w else px(h) / im.height
        return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    return cached(("IMG", path, w, h), mk)


APP_URL = "app.example.com"  # url pill on browser frames; scenes set it per region (e.g. app.example.ca)
STRIP_BAR = False  # True: crop the screenshots' own captured address bar (top 44/1600 of width) so only our url pill shows


def browser(path, w=1200, crop=None, url=None):
    """screenshot inside a light browser window (title bar with traffic lights + url pill), with shadow"""
    url = url or APP_URL

    def mk():
        src = Image.open(os.path.join(ROOT, path)).convert("RGBA")
        if crop: src = src.crop(crop)
        elif STRIP_BAR: src = src.crop((0, round(src.width * 44 / 1600), src.width, src.height))
        bw = px(w); k = bw / src.width; sh = int(src.height * k); bar = px(44); r = px(18)
        win = Image.new("RGBA", (bw, sh + bar), (255, 255, 255, 255))
        win.paste(src.resize((bw, sh), Image.LANCZOS), (0, bar))
        d = ImageDraw.Draw(win)
        d.rectangle([0, 0, bw, bar], fill=(246, 246, 252, 255)); d.line([0, bar - 1, bw, bar - 1], fill=(225, 225, 240, 255), width=max(1, px(1.5)))
        for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
            cx = px(26 + i * 24); d.ellipse([cx - px(7), bar // 2 - px(7), cx + px(7), bar // 2 + px(7)], fill=c)
        pw = px(360); d.rounded_rectangle([bw // 2 - pw // 2, px(9), bw // 2 + pw // 2, bar - px(9)], px(14), fill=(232, 232, 245))
        u = text(url, 17, "med", MUTE); win.alpha_composite(u, (bw // 2 - u.width // 2, bar // 2 - u.height // 2))
        m = Image.new("L", win.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, win.width - 1, win.height - 1], r, fill=255)
        win.putalpha(m)
        return shadowed(win, 34, 26, 0.22)
    return cached(("BROWSER", path, w, crop, url, STRIP_BAR), mk)


def phone_screen(path, h=760):
    """raw app screenshot inside a drawn phone bezel, with shadow"""
    def mk():
        src = Image.open(os.path.join(ROOT, path)).convert("RGBA")
        ph = px(h); bez = px(16); r = px(54)
        sh = ph - 2 * bez; sw = int(src.width * sh / src.height)
        body = Image.new("RGBA", (sw + 2 * bez, ph))
        ImageDraw.Draw(body).rounded_rectangle([0, 0, body.width - 1, ph - 1], r, fill=(26, 26, 40, 255))
        scr = src.resize((sw, sh), Image.LANCZOS)
        m = Image.new("L", scr.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], r - bez, fill=255)
        body.paste(scr, (bez, bez), m)
        ImageDraw.Draw(body).rounded_rectangle([body.width // 2 - px(46), bez + px(10), body.width // 2 + px(46), bez + px(34)], px(12), fill=(20, 20, 30, 255))
        return shadowed(body, 34, 26, 0.25)
    return cached(("PHONE", path, h), mk)


# ---------------------------------------------------------------- compositing
def place(im, spr, cx, cy, sc=1.0, a=1.0, rot=0.0, blur=0.0, anchor="c"):
    """paste sprite centred at design (cx, cy) with scale, opacity, rotation (deg) and gaussian blur (design px)"""
    if a <= 0.003 or sc <= 0.01: return
    s = spr
    if abs(sc - 1) > 0.004:
        s = s.resize((max(1, int(s.width * sc)), max(1, int(s.height * sc))), Image.BILINEAR)
    if rot: s = s.rotate(rot, Image.BILINEAR, expand=True)
    if blur > 0.3: s = s.filter(ImageFilter.GaussianBlur(px(blur)))
    if a < 0.997:
        s = s.copy(); s.putalpha(s.getchannel("A").point(lambda v: int(v * a)))
    x = px(cx) - (s.width // 2 if anchor[0] in "c" else 0 if anchor == "l" else s.width)
    y = px(cy) - s.height // 2
    if x >= im.width or y >= im.height or x + s.width <= 0 or y + s.height <= 0: return
    im.alpha_composite(s, dest=(max(0, x), max(0, y)), source=(max(0, -x), max(0, -y)))


def _band(w, h):
    x = np.linspace(-1, 1, w, dtype=np.float32)[None, :]; y = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    d = np.abs(x - y * 0.35)
    return Image.fromarray((np.clip(1 - d / 0.22, 0, 1) ** 1.5 * 255).astype(np.uint8), "L")


def sheen(spr, k, strength=0.45):
    """sprite with a diagonal light sweep at position k (0..1), masked to its alpha"""
    if not 0 < k < 1: return spr
    from PIL import ImageChops
    w, h = spr.size; bw = max(2, int(min(w, px(700)) * 0.6))
    band = cached(("BAND", bw, h), lambda: _band(bw, h))
    m = Image.new("L", (w, h), 0); m.paste(band, (int(lerp(-bw, w, k)), 0))
    m = ImageChops.multiply(m, spr.getchannel("A")).point(lambda v: int(v * strength))
    out = spr.copy(); wh = Image.new("RGBA", (w, h), (255, 255, 255, 0)); wh.putalpha(m); out.alpha_composite(wh); return out


MICRO = {"float": 5.0, "breathe": 0.022, "sheen": True}


def reveal(im, spr, cx, cy, t, t0, t1=None, dy=36, blur=10, sc0=0.96, din=0.5, dout=0.35):
    """standard blur+rise entrance (and fade-out before t1), then a gentle float and one light sweep"""
    k, a = life(t, t0, t1, din, dout)
    if a <= 0: return
    e = out_cubic(k)
    fl = MICRO["float"] * math.sin((t - t0) * 1.9 + cx * 0.01) * prog(t, t0 + din, 0.8)
    if MICRO["sheen"]: spr = sheen(spr, prog(t, t0 + din * 0.8, 0.75))
    place(im, spr, cx, cy + dy * (1 - e) + fl, lerp(sc0, 1, e), a, blur=blur * (1 - e))


def pop(im, spr, cx, cy, t, t0, t1=None, din=0.45, dout=0.3, rot=0):
    """overshoot pop-in, then a subtle 2% breathing pulse and one light sweep"""
    k, a = life(t, t0, t1, din, dout)
    if a <= 0: return
    br = 1 + MICRO["breathe"] * math.sin((t - t0) * 2.6 + cx * 0.02) * prog(t, t0 + din, 0.6)
    if MICRO["sheen"]: spr = sheen(spr, prog(t, t0 + din, 0.6))
    place(im, spr, cx, cy, max(0.02, out_back(k)) * br, min(1, a * 1.6), rot=rot * (1 - k))


# ---------------------------------------------------------------- background
ORBS = [  # colour, design diameter, base x, base y, drift x, drift y, speed, phase
    ((140, 92, 255), 760, 1700, 120, 120, 70, 0.09, 0.0),
    ((60, 130, 255), 680, 140, 980, 110, 80, 0.07, 1.7),
    ((236, 110, 220), 460, 1640, 1010, 90, 60, 0.11, 3.1),
    ((120, 100, 255), 380, 260, 120, 70, 50, 0.13, 4.4)]


def _orb(col, d):
    d = px(d); r = np.linspace(-1, 1, d, dtype=np.float32)
    rr = np.sqrt(r[None, :] ** 2 + r[:, None] ** 2)
    a = np.clip(1 - rr, 0, 1) ** 1.8 * 0.55
    im = Image.new("RGBA", (d, d), col + (0,)); im.putalpha(Image.fromarray((a * 255).astype(np.uint8), "L")); return im


def background(t, orb_gain=1.0):
    base = cached("BG", lambda: _bg_base())
    im = base.copy()
    for col, d, x, y, dx, dy, sp, ph in ORBS:
        o = cached(("ORB", col, d), lambda: _orb(col, d))
        cx = sx(x) + dx * math.sin(t * sp * 2 * math.pi * 0.35 + ph); cy = sy(y) + dy * math.cos(t * sp * 2 * math.pi * 0.3 + ph)
        place(im, o, cx, cy, a=orb_gain)
    return im


def _bg_base():
    y = np.linspace(0, 1, RH, dtype=np.float32)[:, None, None]; x = np.linspace(0, 1, RW, dtype=np.float32)[None, :, None]
    top = np.array(BG[0], np.float32); bot = np.array(BG[1], np.float32)
    arr = top * (1 - y) + bot * y + (x - 0.5) * 4
    im = Image.fromarray(np.clip(np.broadcast_to(arr, (RH, RW, 3)), 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(im)  # faint rings like the reference
    for cx, cy, r in [(sx(250), sy(860), 300), (sx(1720), sy(230), 360)]:
        d.ellipse([px(cx - r), px(cy - r), px(cx + r), px(cy + r)], outline=(255, 255, 255, 255), width=max(1, px(2)))
    return im


# ---------------------------------------------------------------- composite pieces
def headline(im, words, cx, cy, size, t, t_out=None, weight="black", color=INK, hi=(), maxw=1500, lh=1.18, stagger=None):
    """kinetic headline: words = [(word, t_appear)]; words whose index is in hi get the brand gradient.
    Each word rises + un-blurs on its own time. Lines wrap at maxw and the block is centred on (cx, cy)."""
    sps = [text(w, size, weight, color, grad=(TVA, TVB) if i in hi else None) for i, (w, _) in enumerate(words)]
    sp = px(size * 0.28); lines = [[]]; lw = 0
    for i, s in enumerate(sps):
        if lines[-1] and lw + sp + s.width > px(maxw): lines.append([]); lw = 0
        lines[-1].append(i); lw += (sp if lw else 0) + s.width
    step = size * lh; y0 = cy - step * (len(lines) - 1) / 2
    for li, ln in enumerate(lines):
        tw = sum(sps[i].width for i in ln) + sp * (len(ln) - 1); x = px(cx) - tw / 2
        for i in ln:
            s = sps[i]; t0 = words[i][1]
            k, a = life(t, t0, t_out, 0.42, 0.3)
            if a > 0:
                e = out_cubic(k); yy = y0 + li * step + 30 * (1 - e)
                place(im, s, (x + s.width / 2) / S, yy, lerp(0.92, 1, e), a, blur=8 * (1 - e))
            x += s.width + sp
        # draw-on underline under each run of highlighted words in this line
        runs = []; xx = px(cx) - tw / 2
        for i in ln:
            if i in hi:
                if runs and runs[-1][3] == i - 1: runs[-1][1] = xx + sps[i].width; runs[-1][3] = i; runs[-1][2] = max(runs[-1][2], words[i][1])
                else: runs.append([xx, xx + sps[i].width, words[i][1], i])
            xx += sps[i].width + sp
        for x0, x1, tl, _ in runs:
            k = out_cubic(prog(t, tl + 0.25, 0.45)); _, a = life(t, tl, t_out, 0.3, 0.3)
            if k > 0 and a > 0:
                bar = cached(("ULINE", int(x1 - x0), size), lambda: rrect((x1 - x0) / S, max(4, size * 0.085), size * 0.04, grad=(TVA, TVB)))
                wv = max(1, int(bar.width * k)); seg = bar.crop((0, 0, wv, bar.height))
                place(im, seg, (x0 + wv / 2) / S, y0 + li * step + size * 0.62, a=a * 0.9)


def cursor_tap(im, x, y, t, t_tap, t_out=None, travel=(140, 160)):
    """hand cursor glides in from (x+travel) and taps at t_tap with a ripple"""
    hand = emoji("👆", 92)
    k, a = life(t, t_tap - 0.55, t_out, 0.5, 0.3)
    if a <= 0: return
    e = inout(k); hx = x + travel[0] * (1 - e); hy = y + 52 + travel[1] * (1 - e)
    press = math.sin(math.pi * prog(t, t_tap, 0.22))
    rp = prog(t, t_tap, 0.6)
    if 0 < rp < 1:
        ring = cached(("RING",), lambda: _ring(160))
        place(im, ring, x, y, 0.3 + 0.9 * out_cubic(rp), (1 - rp) * 0.9)
    place(im, hand, hx + 10, hy, 1 - 0.12 * press, a)


def _ring(d):
    d = px(d); im = Image.new("RGBA", (d, d)); ImageDraw.Draw(im).ellipse([2, 2, d - 3, d - 3], outline=TVA + (255,), width=max(2, px(6)))
    return im


def counter(value, fmt, size, weight="black", grad=None):
    return text(fmt.format(value), size, weight, grad=grad or (TVA, TVB))


def to_rgb_bytes(im):
    return im.convert("RGB").tobytes()
