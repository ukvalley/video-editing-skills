"""16:9 podcast graphics (1920x1080, 25 fps): lower thirds, keyword pops, chapter cards and full-screen
B-roll cards (steps, compare, flow, stat, quote, title) on a crisp charcoal + gold canvas.
Everything is drawn at full resolution with Pillow (no upscaled or blurred plates).
Usage (from the project dir): python3 ../../toolkit/gfx_podcast.py edit/gfx_plan.json [names...]
  plan = list of {name, kind, dur, data:{...}}; writes work/gfx/<name>.mov (qtrle argb)
  add "still": t to write work/gfx/<name>_still.png instead (for checking a frame)
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 25
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FB = os.path.join(ROOT, "assets/fonts/Montserrat-Black.ttf")
FX = os.path.join(ROOT, "assets/fonts/Montserrat-ExtraBold.ttf")
FA = os.path.join(ROOT, "assets/fonts/Anton-Regular.ttf")
GOLD = (255, 196, 0)
GOLD2 = (255, 150, 30)
INK = (12, 12, 14)
CHAR = (24, 24, 28)
WHITE = (255, 255, 255)
SOFT = (200, 200, 205)
RED = (235, 64, 52)
GRN = (46, 204, 113)
_fc = {}


def font(p, s):
    if (p, s) not in _fc:
        _fc[(p, s)] = ImageFont.truetype(p, s)
    return _fc[(p, s)]


def clip(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def p_(t, t0, d):
    return clip((t - t0) / d)


def oc(x):
    return 1 - (1 - x) ** 3


def oq(x):
    return 1 - (1 - x) ** 5


def ic(x):
    return x ** 3


def ob(x, s=1.6):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def fade(img, a):
    if a >= 1:
        return img
    img = img.copy()
    img.putalpha(img.split()[3].point(lambda v: int(v * max(0, a))))
    return img


def blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def tw(f, s):
    b = f.getbbox(s)
    return b[2] - b[0]


# ---------------- canvas ----------------
_BG = None
PAD = 160


def _canvas():
    """charcoal studio canvas: warm gold key glow top-left, cool fill bottom-right, fine diagonal lines, grain"""
    global _BG
    if _BG is not None:
        return _BG
    w, h = W + PAD, H + PAD
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.zeros((h, w, 3), np.float32) + np.array((14, 14, 17), np.float32)
    for cx, cy, r, col, k in [(380, 260, 900, (92, 66, 12), 0.75), (1750, 1050, 900, (22, 34, 60), 0.7), (1100, 560, 600, (40, 34, 26), 0.4)]:
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r / 2.2) ** 2)))[..., None] * k
        img = img * (1 - g) + np.array(col, np.float32) * g
    lines = (((xx + yy) % 46) < 1.6).astype(np.float32)[..., None]
    img = img * (1 - 0.035 * lines) + 255 * 0.035 * lines
    v = 1 - 0.45 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)[..., None]
    img *= np.clip(v, 0.5, 1)
    img += np.random.default_rng(7).normal(0, 2.0, img.shape).astype(np.float32)
    _BG = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return _BG


def bg(t):
    ox = int(PAD / 2 + 50 * math.sin(t * 0.35)); oy = int(PAD / 2 + 40 * math.cos(t * 0.3))
    return _canvas().crop((ox, oy, ox + W, oy + H))


def full_env(frame, t, dur, fin=0.35, fout=0.3):
    """full-screen card enters with a fast zoom-settle + fade, leaves with a push"""
    a = oq(p_(t, 0, fin)); b = ic(p_(t, dur - fout, fout))
    sc = 1.08 - 0.08 * a + 0.06 * b
    if abs(sc - 1) > 1e-3:
        lw, lh = int(W * sc), int(H * sc)
        fr = frame.resize((lw, lh), Image.BICUBIC)
        frame = fr.crop(((lw - W) // 2, (lh - H) // 2, (lw - W) // 2 + W, (lh - H) // 2 + H))
    return fade(frame, min(a * 1.4, 1) * (1 - b))


def kicker(d, x, y, s, t, t0=0.15):
    """small gold label with a growing rule"""
    a = oc(p_(t, t0, 0.4))
    f = font(FB, 30)
    d.rectangle((x, y + 14, x + int(60 * a), y + 20), fill=GOLD)
    d.text((x + 80, y), s.upper(), font=f, fill=GOLD + (int(255 * a),))


# ---------------- overlays on the speaker ----------------

def lower_third(t, dur, data):
    """name + role card bottom-left (or right); gold bar wipes, text slides out from behind a mask"""
    im = blank(); d = ImageDraw.Draw(im)
    side = data.get("side", "left")
    name, role = data["name"].upper(), data.get("role", "")
    fn, fr = font(FB, 54), font(FX, 30)
    wbox = max(tw(fn, name), tw(fr, role)) + 90
    a = oq(p_(t, 0, 0.5)); b = ic(p_(t, dur - 0.4, 0.4))
    x0 = 110 if side == "left" else W - 110 - wbox
    y0 = 840
    reveal = int(wbox * a * (1 - b))
    card = blank(); cd = ImageDraw.Draw(card)
    cd.rectangle((x0, y0, x0 + wbox, y0 + 140), fill=(10, 10, 12, 225))
    cd.rectangle((x0, y0, x0 + 12, y0 + 140), fill=GOLD)
    cd.text((x0 + 44, y0 + 18), name, font=fn, fill=WHITE)
    cd.text((x0 + 46, y0 + 88), role, font=fr, fill=GOLD)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rectangle((x0, y0 - 5, x0 + reveal, y0 + 150), fill=255)
    im.paste(card, (0, 0), Image.composite(card, blank(), mask).split()[3])
    if 0 < a < 1 or 0 < b < 1:
        d.rectangle((x0 + reveal - 6, y0 - 6, x0 + reveal, y0 + 146), fill=GOLD)
    return im


def keyword(t, dur, data):
    """big statement pop on the free side of the frame. lines: [[text, gold?], ...]; words pop in one by one
    over a soft dark gradient scrim (gradient alpha only, the picture is never blurred)"""
    side = data.get("side", "left")
    lines = data["lines"]
    size = data.get("size", 104)
    f = font(FA, size)
    im = blank()
    a_in = oc(p_(t, 0, 0.3)); a_out = 1 - ic(p_(t, dur - 0.3, 0.3))
    # scrim
    scrim = np.zeros((H, W, 4), np.uint8)
    if side == "bottom":
        gy = np.linspace(0, 1, H, dtype=np.float32)
        g = np.clip((gy - 0.45) / 0.55, 0, 1) ** 1.3 * 215 * a_in * a_out
        scrim[..., 3] = g[:, None].astype(np.uint8)
    else:
        gx = np.linspace(0, 1, W, dtype=np.float32)
        g = (1 - gx) if side == "left" else gx
        g = np.clip((g - 0.35) / 0.65, 0, 1) ** 1.4 * 190 * a_in * a_out
        scrim[..., 3] = g[None, :].astype(np.uint8)
    im.alpha_composite(Image.fromarray(scrim, "RGBA"))
    d = ImageDraw.Draw(im)
    lh = int(size * 1.08)
    y = H // 2 - lh * len(lines) // 2 - 10
    if side == "bottom":
        y = H - 110 - lh * len(lines)
    xL = 120
    k = 0
    for text, gold in lines:
        xR = W - 120
        x = xL if side == "left" else (W - tw(f, text)) // 2 if side == "bottom" else xR - tw(f, text)
        for wd in text.split(" "):
            pw = oq(p_(t, 0.08 + 0.09 * k, 0.28))
            if pw > 0:
                layer = blank(); ld = ImageDraw.Draw(layer)
                yy = y + int(30 * (1 - pw))
                ld.text((x + 4, yy + 5), wd, font=f, fill=(0, 0, 0, 150))
                ld.text((x, yy), wd, font=f, fill=GOLD if gold else WHITE)
                im.alpha_composite(fade(layer, pw * a_out))
            x += tw(f, wd + " ")
            k += 1
        y += lh
    # gold underline under the block
    ul = oc(p_(t, 0.25 + 0.09 * k, 0.4)) * a_out
    if ul > 0:
        uw = int(220 * ul)
        ux = xL if side == "left" else (W - uw) // 2 if side == "bottom" else W - 120 - uw
        d.rectangle((ux, y + int(size * 0.3), ux + uw, y + int(size * 0.3) + 10), fill=GOLD + (int(255 * a_out),))
    return im


def chapter(t, dur, data):
    """full-screen chapter card: CHAPTER 02 kicker, big two-line title, gold rule"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    num, title = data["num"], data["title"].upper()
    ghost = blank(); ImageDraw.Draw(ghost).text((W - 100, H - 40), f"{num:02d}", font=font(FA, 560), fill=(255, 255, 255, 10), anchor="rd")
    fr.alpha_composite(ghost)
    f = font(FA, 150)
    kicker(d, 160, 330, f"Chapter {num:02d}", t, 0.1)
    words = title.split(" ")
    lines, cur = [], ""
    for w_ in words:
        if tw(f, (cur + " " + w_).strip()) > W - 360 and cur:
            lines.append(cur); cur = w_
        else:
            cur = (cur + " " + w_).strip()
    lines.append(cur)
    y = 400
    for i, ln in enumerate(lines):
        p = oq(p_(t, 0.2 + 0.12 * i, 0.45))
        layer = blank(); ImageDraw.Draw(layer).text((160 + int(80 * (1 - p)), y), ln, font=f, fill=WHITE if i == 0 else GOLD)
        fr.alpha_composite(fade(layer, p))
        y += 165
    return full_env(fr, t, dur)


def title_card(t, dur, data):
    """episode title after the cold open: kicker, huge title, guest line"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    f1, f2 = font(FA, 190), font(FX, 40)
    kicker(d, W // 2 - 260, 290, data.get("kicker", "The Podcast"), t, 0.05)
    for i, (ln, col) in enumerate(data["lines"]):
        p = oq(p_(t, 0.15 + 0.15 * i, 0.5))
        layer = blank(); ImageDraw.Draw(layer).text((W // 2, 360 + 200 * i + int(40 * (1 - p))), ln.upper(), font=f1, fill=GOLD if col else WHITE, anchor="mt")
        fr.alpha_composite(fade(layer, p))
    p = oc(p_(t, 0.7, 0.5))
    d.text((W // 2, 360 + 200 * len(data["lines"]) + 50), data.get("sub", ""), font=f2, fill=SOFT + (int(255 * p),), anchor="mt")
    return full_env(fr, t, dur, fin=0.25)


# ---------------- full-screen B-roll cards ----------------

def steps(t, dur, data):
    """title + numbered rows that land one by one at given times (data.at, seconds local)"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    kicker(d, 160, 150, data.get("kicker", ""), t)
    ft, fi, fn = font(FA, 96), font(FB, 52), font(FA, 64)
    p = oq(p_(t, 0.1, 0.45))
    d.text((160, 200 + int(30 * (1 - p))), data["title"].upper(), font=ft, fill=WHITE + (int(255 * p),))
    items = data["items"]; at = data.get("at") or [0.6 + 0.5 * i for i in range(len(items))]
    rowh = min(130, int(560 / len(items)))
    for i, it in enumerate(items):
        pi = oq(p_(t, at[i], 0.4))
        if pi <= 0:
            continue
        y = 360 + i * rowh
        layer = blank(); ld = ImageDraw.Draw(layer)
        x = 160 + int(70 * (1 - pi))
        ld.rounded_rectangle((x, y, x + 1600, y + rowh - 22), 18, fill=(255, 255, 255, 16), outline=(255, 255, 255, 30), width=2)
        ld.rounded_rectangle((x + 18, y + 14, x + 18 + rowh - 50, y + rowh - 36), 14, fill=GOLD)
        ld.text((x + 18 + (rowh - 50) // 2, y + (rowh - 22) // 2), str(i + 1), font=fn, fill=INK, anchor="mm")
        ld.text((x + rowh + 10, y + (rowh - 22) // 2), it, font=fi, fill=WHITE, anchor="lm")
        fr.alpha_composite(fade(layer, pi))
    return full_env(fr, t, dur)


def compare(t, dur, data):
    """two columns: left (red, crosses) vs right (gold, ticks)"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    kicker(d, 160, 120, data.get("kicker", ""), t)
    ft, fh, fi = font(FA, 88), font(FA, 62), font(FB, 40)
    p = oq(p_(t, 0.1, 0.45))
    d.text((160, 168 + int(30 * (1 - p))), data["title"].upper(), font=ft, fill=WHITE + (int(255 * p),))
    cols = [(data["left"], RED, 160, False), (data["right"], GOLD, 1000, True)]
    at = data.get("at", 0.5)
    col_at = data.get("col_at") or [at, at + 0.9]
    times = data.get("times") or [[col_at[c] + 0.3 + 0.25 * i for i in range(len(cols[c][0]["items"]))] for c in range(2)]
    for c, (col, colr, x, good) in enumerate(cols):
        pc = oq(p_(t, col_at[c], 0.45))
        if pc <= 0:
            continue
        layer = blank(); ld = ImageDraw.Draw(layer)
        y0 = 330 + int(40 * (1 - pc))
        bh = 150 + 105 * len(col["items"])
        ld.rounded_rectangle((x, y0, x + 760, y0 + bh), 26, fill=(255, 255, 255, 14), outline=colr + (200,), width=3)
        ld.rectangle((x, y0, x + 760, y0 + 110), fill=colr + (235,))
        ld.text((x + 380, y0 + 55), col["label"].upper(), font=fh, fill=INK if good else WHITE, anchor="mm")
        for i, it in enumerate(col["items"]):
            pi = oq(p_(t, times[c][i], 0.35))
            yy = y0 + 170 + i * 105
            ld.ellipse((x + 40, yy - 26, x + 92, yy + 26), fill=colr + (int(255 * pi),))
            sym = "✓" if good else "✕"
            ld.text((x + 66, yy), sym, font=font("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 36), fill=(INK if good else WHITE) + (int(255 * pi),), anchor="mm")
            ld.text((x + 120 + int(30 * (1 - pi)), yy), it, font=fi, fill=WHITE + (int(255 * pi),), anchor="lm")
        fr.alpha_composite(fade(layer, pc))
    return full_env(fr, t, dur)


def flow(t, dur, data):
    """horizontal chain of nodes joined by drawing arrows; nodes land at data.at"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    kicker(d, 160, 170, data.get("kicker", ""), t)
    ft, fn, fs = font(FA, 92), font(FA, 54), font(FX, 30)
    p = oq(p_(t, 0.1, 0.45))
    d.text((160, 220 + int(30 * (1 - p))), data["title"].upper(), font=ft, fill=WHITE + (int(255 * p),))
    nodes = data["nodes"]; n = len(nodes)
    at = data.get("at") or [0.6 + 0.6 * i for i in range(n)]
    gap = (W - 320) / n; bw = gap - 90
    for i, nd in enumerate(nodes):
        pi = ob(p_(t, at[i], 0.45)) if t >= at[i] else 0
        if pi <= 0:
            continue
        cx = 160 + gap * i + bw / 2; cy = 620
        layer = blank(); ld = ImageDraw.Draw(layer)
        last = i == n - 1
        ld.rounded_rectangle((cx - bw / 2, cy - 130, cx + bw / 2, cy + 130), 28, fill=GOLD if last else (34, 34, 40, 255), outline=GOLD, width=4)
        lab = nd[0].upper()
        fsz = fn if tw(fn, lab) < bw - 40 else font(FA, 42)
        ld.text((cx, cy - 18), lab, font=fsz, fill=INK if last else WHITE, anchor="mm")
        if len(nd) > 1:
            ld.text((cx, cy + 50), nd[1], font=fs, fill=INK if last else SOFT, anchor="mm")
        sc = clip(pi, 0, 1.2)
        lw_, lh_ = int(W * sc), int(H * sc)
        if abs(sc - 1) > 1e-3 and sc > 0.05:
            sm = layer.resize((lw_, lh_), Image.BICUBIC); layer = blank()
            layer.paste(sm, (int(cx - cx * sc), int(cy - cy * sc)), sm)
        fr.alpha_composite(fade(layer, clip(pi)))
        if i < n - 1:
            pa = oc(p_(t, at[i] + 0.3, 0.35))
            if pa > 0:
                x1 = cx + bw / 2 + 12; x2 = x1 + (66 * pa)
                d.line((x1, cy, x2, cy), fill=GOLD, width=8)
                if pa > 0.9:
                    d.polygon([(x2 + 4, cy), (x2 - 18, cy - 16), (x2 - 18, cy + 16)], fill=GOLD)
    return full_env(fr, t, dur)


def stat(t, dur, data):
    """giant counting number + label"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    kicker(d, W // 2 - 200, 230, data.get("kicker", ""), t)
    v = data["value"]; pre, suf = data.get("prefix", ""), data.get("suffix", "")
    p = oq(p_(t, 0.2, data.get("count", 1.2)))
    num = f"{pre}{int(round(v * p))}{suf}"
    d.text((W // 2, 520), num, font=font(FA, 330), fill=GOLD, anchor="mm")
    pl = oc(p_(t, 0.8, 0.5))
    d.text((W // 2, 780), data["label"].upper(), font=font(FB, 58), fill=WHITE + (int(255 * pl),), anchor="mm")
    return full_env(fr, t, dur)


def quote(t, dur, data):
    """full-screen pull quote, words reveal; gold words marked with *word*"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    f = font(FA, data.get("size", 112))
    d.text((150, 120), "“", font=font(FA, 360), fill=GOLD + (int(255 * oc(p_(t, 0, 0.4))),))
    words = data["text"].split(" ")
    x, y = 200, 330; lh = int(f.size * 1.15)
    for k, w_ in enumerate(words):
        gold = w_.startswith("*")
        w_ = w_.strip("*")
        if x + tw(f, w_) > W - 200:
            x = 200; y += lh
        pw = oq(p_(t, 0.25 + k * data.get("rate", 0.11), 0.3))
        if pw > 0:
            layer = blank(); ImageDraw.Draw(layer).text((x, y + int(25 * (1 - pw))), w_.upper(), font=f, fill=GOLD if gold else WHITE)
            fr.alpha_composite(fade(layer, pw))
        x += tw(f, w_ + " ")
    if data.get("by"):
        pb = oc(p_(t, 0.6 + len(words) * data.get("rate", 0.11), 0.4))
        d.text((200, y + lh + 40), "— " + data["by"], font=font(FX, 40), fill=SOFT + (int(255 * pb),))
    return full_env(fr, t, dur)


def sub_cta(t, dur, data):
    """small subscribe pill bottom-right with bell tap"""
    im = blank(); d = ImageDraw.Draw(im)
    a = oq(p_(t, 0, 0.45)); b = ic(p_(t, dur - 0.35, 0.35))
    x = W - 120 - 520 + int(600 * (1 - a)) + int(600 * b); y = 880
    d.rounded_rectangle((x, y, x + 520, y + 110), 55, fill=(10, 10, 12, 235), outline=GOLD, width=3)
    d.rounded_rectangle((x + 14, y + 14, x + 290, y + 96), 41, fill=RED)
    d.text((x + 152, y + 55), "SUBSCRIBE", font=font(FB, 38), fill=WHITE, anchor="mm")
    d.text((x + 405, y + 55), data.get("text", "& hit 🔔").replace("🔔", ""), font=font(FB, 32), fill=WHITE, anchor="mm")
    tp = p_(t, 1.1, 0.35)
    if 0 < tp < 1:
        r = int(20 + 50 * tp)
        d.ellipse((x + 152 - r, y + 55 - r, x + 152 + r, y + 55 + r), outline=(255, 255, 255, int(220 * (1 - tp))), width=6)
    return im


def tasks(t, dur, data):
    """chips pile up in a grid as each task is spoken (data.at), then a red stamp lands (data.stamp at data.stamp_at)"""
    fr = bg(t).copy(); d = ImageDraw.Draw(fr)
    kicker(d, 160, 110, data.get("kicker", ""), t)
    p = oq(p_(t, 0.1, 0.45))
    d.text((160, 158 + int(30 * (1 - p))), data["title"].upper(), font=font(FA, 86), fill=WHITE + (int(255 * p),))
    items = data["items"]; at = data["at"]; cols = data.get("cols", 3)
    fi = font(FB, 36)
    cw, ch = (W - 320 - 40 * (cols - 1)) / cols, 120
    for i, it in enumerate(items):
        pi = ob(p_(t, at[i], 0.35)) if t >= at[i] else 0
        if pi <= 0:
            continue
        r, c = divmod(i, cols)
        x = 160 + c * (cw + 40); y = 320 + r * (ch + 30)
        layer = blank(); ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((x, y, x + cw, y + ch), 22, fill=(36, 36, 42, 255), outline=(255, 255, 255, 40), width=2)
        ld.ellipse((x + 26, y + ch / 2 - 22, x + 70, y + ch / 2 + 22), fill=GOLD)
        ld.text((x + 48, y + ch / 2), str(i + 1), font=font(FA, 32), fill=INK, anchor="mm")
        ld.text((x + 96, y + ch / 2), it, font=fi, fill=WHITE, anchor="lm")
        cx, cy = x + cw / 2, y + ch / 2; sc = clip(pi, 0, 1.2)
        if abs(sc - 1) > 1e-3 and sc > 0.05:
            sm = layer.resize((int(W * sc), int(H * sc)), Image.BICUBIC); layer = blank()
            layer.paste(sm, (int(cx - cx * sc), int(cy - cy * sc)), sm)
        fr.alpha_composite(fade(layer, clip(pi)))
    if data.get("stamp") and t >= data["stamp_at"]:
        ps = oq(p_(t, data["stamp_at"], 0.25))
        fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(120 * ps))))
        layer = blank(); ld = ImageDraw.Draw(layer)
        fs = font(FA, 124); txt = data["stamp"].upper()
        wbox = tw(fs, txt) + 120
        ld.rounded_rectangle((W / 2 - wbox / 2, H / 2 + 60, W / 2 + wbox / 2, H / 2 + 300), 20, fill=RED + (240,), outline=WHITE, width=8)
        ld.text((W / 2, H / 2 + 180), txt, font=fs, fill=WHITE, anchor="mm")
        layer = layer.rotate(-6 * ps, resample=Image.BICUBIC, center=(W / 2, H / 2 + 180))
        sc = 1.6 - 0.6 * ps
        sm = layer.resize((int(W * sc), int(H * sc)), Image.BICUBIC); l2 = blank()
        l2.paste(sm, (int(W / 2 - W / 2 * sc), int((H / 2 + 180) - (H / 2 + 180) * sc)), sm)
        fr.alpha_composite(fade(l2, ps))
    return full_env(fr, t, dur)


GFX = dict(lower_third=lower_third, keyword=keyword, chapter=chapter, title_card=title_card,
           steps=steps, compare=compare, flow=flow, stat=stat, quote=quote, sub_cta=sub_cta, tasks=tasks)


def render(name, kind, dur, data, out):
    n = int(round(dur * FPS))
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", out], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(GFX[kind](i / FPS, dur, data).tobytes())
    p.stdin.close(); p.wait()
    print(f"{name}: {kind} {dur:.2f}s -> {out}", flush=True)


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1]))
    only = set(sys.argv[2:])
    os.makedirs("work/gfx", exist_ok=True)
    for g in plan:
        if only and g["name"] not in only:
            continue
        if g.get("still") is not None:
            GFX[g["kind"]](g["still"], g["dur"], g["data"]).save(f"work/gfx/{g['name']}_still.png")
            continue
        out = f"work/gfx/{g['name']}.mov"
        render(g["name"], g["kind"], g["dur"], g["data"], out)
