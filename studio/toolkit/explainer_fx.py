"""Momentum layer for explainer.py: decorative motion that keeps the frame alive (~30% of the motion budget).

    import explainer_fx as M
    M.setup(scene_spans, bpm=105, chapters=[...])
    M.back(im, t)                 # grid, network lines, rings, shapes, far/mid particles, beat rings (behind content)
    layer = M.camera(layer, t, i, s, e)   # 2-5% push + drift on a scene's content layer
    M.composite_scene(im, layer, t, s, e) # with exit/entry smear around scene boundaries
    M.front(im, t)                # near particles, depth blobs, transition streaks, chapter label, progress, grain

Everything stays low-opacity so it never competes with the information layer.
"""
import math
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
import explainer as X
from explainer import px, place, prog, out_cubic, in_cubic, inout, lerp, clip

PINK = X.ACC3  # brand colours are read from explainer at draw time (X.TVA / X.TVB / PINK), so X.brand() re-colours this layer
CFG = {"spans": [], "bpm": 105.0, "chapters": [], "beat0": 0.0, "drums_from": 4.6,
       "cam": 0.035, "drift": 24, "out": (0.3, 0.42, -260), "in": (0.5, 200), "streak": 0.55, "hud": True}


def setup(spans, bpm=105.0, chapters=(), beat0=0.0, drums_from=4.6, **pace):
    """pace overrides (fast ad cuts): cam=push amount, drift=px, out=(lead, dur, px), in=(dur, px), streak=dur, hud=bool"""
    CFG.update(spans=list(spans), bpm=bpm, chapters=list(chapters), beat0=beat0, drums_from=drums_from, **pace)


def rnd(seed):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------- sprites
def _dot(r, col, soft=0.0):
    def mk():
        d = max(3, px(r * 2 + soft * 4)); im = Image.new("RGBA", (d * 4, d * 4))
        c = d * 2; rr = px(r) * 4
        ImageDraw.Draw(im).ellipse([c - rr, c - rr, c + rr, c + rr], fill=col + (255,))
        im = im.resize((d, d), Image.LANCZOS)
        if soft: im = im.filter(ImageFilter.GaussianBlur(px(soft)))
        return im
    return X.cached(("DOT", r, col, soft), mk)


def _shape(kind, size, col, lw=3):
    def mk():
        s = px(size); pad = px(lw) + 2; d = s + 2 * pad; k = 4
        im = Image.new("RGBA", (d * k, d * k)); dr = ImageDraw.Draw(im); w = max(1, int(px(lw) * k))
        a, b = pad * k, (pad + s) * k; m = (a + b) / 2; c = col + (255,)
        if kind == "plus":
            dr.line([m, a, m, b], fill=c, width=w); dr.line([a, m, b, m], fill=c, width=w)
        elif kind == "cross":
            dr.line([a, a, b, b], fill=c, width=w); dr.line([a, b, b, a], fill=c, width=w)
        elif kind == "square":
            dr.rectangle([a, a, b, b], outline=c, width=w)
        elif kind == "tri":
            dr.polygon([(m, a), (b, b), (a, b)], outline=c, width=w)
        elif kind == "ring":
            dr.ellipse([a, a, b, b], outline=c, width=w)
        elif kind == "bracket":
            q = (b - a) * 0.3
            dr.line([a + q, a, a, a, a, b, a + q, b], fill=c, width=w, joint="curve")
        return im.resize((d, d), Image.LANCZOS)
    return X.cached(("SHAPE", kind, size, col, lw), mk)


def _dashed_ring(r, col, dashes=48, lw=2.5, frac=0.55):
    def mk():
        d = max(12, px(r * 2 + 10)); k = 3; im = Image.new("RGBA", (d * k, d * k)); dr = ImageDraw.Draw(im)
        for i in range(dashes):
            a0 = 360 * i / dashes; a1 = a0 + 360 / dashes * frac
            dr.arc([k * 4, k * 4, d * k - k * 4, d * k - k * 4], a0, a1, fill=col + (255,), width=max(1, int(px(lw) * k)))
        return im.resize((d, d), Image.LANCZOS)
    return X.cached(("DRING", r, col, dashes, lw, frac), mk)


def _thin_ring(r, col, lw=2):
    def mk():
        d = max(12, px(r * 2 + 8)); k = 3; im = Image.new("RGBA", (d * k, d * k))
        ImageDraw.Draw(im).ellipse([k * 4, k * 4, d * k - k * 4, d * k - k * 4], outline=col + (255,), width=max(1, int(px(lw) * k)))
        return im.resize((d, d), Image.LANCZOS)
    return X.cached(("TRING", r, col, lw), mk)


def _streak(length, thick, col):
    def mk():
        w, h = px(length), max(2, px(thick))
        x = np.linspace(0, 1, w, dtype=np.float32)
        a = np.clip(x * 1.6, 0, 1) * np.clip((1 - x) * 5, 0, 1)  # long tail, bright head
        y = np.linspace(-1, 1, h, dtype=np.float32)[:, None]; a = a[None, :] * (1 - y ** 2) ** 0.5
        im = Image.new("RGBA", (w, h), col + (0,)); im.putalpha(Image.fromarray((a * 255).astype(np.uint8), "L")); return im
    return X.cached(("STREAK", length, thick, col), mk)


# ---------------------------------------------------------------- grid / network / grain
SP = 54


def _grid_tile():
    sp = px(SP); w, h = X.RW + sp * 2, X.RH + sp * 2
    im = Image.new("RGBA", (w, h), X.TVA + (0,)); dr = ImageDraw.Draw(im); r = max(1, px(1.8))
    for y in range(0, h, sp):
        for x in range(0, w, sp):
            dr.ellipse([x - r, y - r, x + r, y + r], fill=X.TVA + (255,))
    return im


def _grid_mask(gain):
    y = np.linspace(-1, 1, X.RH, dtype=np.float32)[:, None]; x = np.linspace(-1, 1, X.RW, dtype=np.float32)[None, :]
    d = np.sqrt((x * 0.9) ** 2 + (y * 1.1) ** 2)
    a = np.clip(1.15 - d, 0, 1) ** 1.3 * gain  # centre-weighted, fades at the edges
    return Image.fromarray((a * 255).astype(np.uint8), "L")


def grid(im, t, gain=0.16):
    tile = X.cached("GRIDT", _grid_tile); sp = px(SP)
    ox = int(px(t * 14)) % sp; oy = int(px(t * 7)) % sp
    g = tile.crop((ox, oy, ox + X.RW, oy + X.RH))
    beat = beat_env(t, 5.0)
    m = X.cached(("GRIDM", round(gain, 3)), lambda: _grid_mask(gain))
    a = ImageChops.multiply(g.getchannel("A"), m)
    if beat > 0.02: a = a.point(lambda v: min(255, int(v * (1 + 1.2 * beat))))
    g.putalpha(a); im.alpha_composite(g)


NODES = None


def network(im, t, alpha=0.22):
    global NODES
    if NODES is None:
        r = rnd(11); NODES = [(r.uniform(80, 1840), r.uniform(80, 1000), r.uniform(30, 90), r.uniform(0.05, 0.12), r.uniform(0, 6.28)) for _ in range(16)]
    pts = [(X.sx(x) + a * math.sin(t * sp + ph), X.sy(y) + a * 0.7 * math.cos(t * sp * 1.3 + ph)) for x, y, a, sp, ph in NODES]
    lay = Image.new("RGBA", im.size); dr = ImageDraw.Draw(lay); lw = max(1, px(1.6))
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.dist(pts[i], pts[j])
            if d < 420:
                dr.line([px(pts[i][0]), px(pts[i][1]), px(pts[j][0]), px(pts[j][1])], fill=X.TVA + (int(255 * alpha * (1 - d / 420)),), width=lw)
    im.alpha_composite(lay)
    for i, (x, y) in enumerate(pts):
        place(im, _dot(4, X.TVA if i % 2 else X.TVB), x, y, a=0.45)


def _grain_tiles():
    r = rnd(3); out = []
    for _ in range(6):
        n = r.integers(0, 255, (X.RH, X.RW), dtype=np.uint8)
        g = Image.fromarray(n, "L").convert("RGBA"); g.putalpha(Image.new("L", (X.RW, X.RH), 6)); out.append(g)
    return out


def grain(im, t):
    tiles = X.cached("GRAIN", _grain_tiles)
    im.alpha_composite(tiles[int(t * 24) % len(tiles)])


# ---------------------------------------------------------------- beat
def beats():
    b = 60.0 / CFG["bpm"]
    return b


def beat_env(t, decay=6.0, every=1):
    """1 on each beat (every N beats), decaying exponentially"""
    if t < CFG["drums_from"]: return 0.0
    b = beats() * every; ph = (t - CFG["beat0"]) % b
    return math.exp(-ph * decay)


def beat_rings(im, t):
    if t < CFG["drums_from"]: return
    bar = beats() * 4; n = int((t - CFG["beat0"]) // bar); ph = (t - CFG["beat0"]) - n * bar
    spots = [(X.sx(1690), X.sy(190)), (X.sx(230), X.sy(880)), (X.sx(1650), X.sy(900)), (X.sx(260), X.sy(200))]
    k = ph / 1.4
    if k < 1:
        x, y = spots[n % 4]
        place(im, _thin_ring(120, X.TVA, 3), x, y, sc=0.4 + 1.6 * out_cubic(k), a=0.32 * (1 - k))


# ---------------------------------------------------------------- particles / shapes / rings
PARTS = None


def _parts():
    r = rnd(7); out = []
    for depth, n, rad, a, sp in [(0, 22, (1.6, 3.0), 0.35, 8), (1, 14, (3.5, 6.0), 0.4, 18), (2, 5, (14, 26), 0.16, 60)]:
        for _ in range(n):
            out.append(dict(d=depth, x=r.uniform(0, 1920), y=r.uniform(0, 1080), r=float(r.uniform(*rad)), a=a, sp=sp * r.uniform(0.7, 1.3),
                            ph=r.uniform(0, 6.28), col=[X.TVA, X.TVB, PINK][int(r.integers(0, 3))]))
    return out


def particles(im, t, depths):
    global PARTS
    if PARTS is None: PARTS = _parts()
    for p in PARTS:
        if p["d"] not in depths: continue
        x = (X.sx(p["x"]) + t * p["sp"] * 0.6) % (X.W + 120) - 60; y = (X.sy(p["y"]) - t * p["sp"]) % (X.H + 80) - 40
        x += 12 * math.sin(t * 0.7 + p["ph"])
        tw = 0.75 + 0.25 * math.sin(t * 2.1 + p["ph"])
        place(im, _dot(p["r"], p["col"], soft=p["r"] * 0.6 if p["d"] == 2 else 0), x, y, a=p["a"] * tw)


SHAPES = None


def shapes(im, t):
    global SHAPES
    if SHAPES is None:
        r = rnd(21); kinds = ["plus", "cross", "square", "tri", "ring", "plus", "bracket", "square", "tri", "plus", "ring", "cross"]
        SHAPES = [dict(k=k, x=r.uniform(60, 1860), y=r.uniform(60, 1020), s=float(r.uniform(20, 36)), rot=r.uniform(-25, 25),
                       ph=r.uniform(0, 6.28), col=[X.TVA, X.TVB, PINK][i % 3]) for i, k in enumerate(kinds)]
    for s in SHAPES:
        x = X.sx(s["x"]) + 26 * math.sin(t * 0.21 + s["ph"]); y = X.sy(s["y"]) + 20 * math.cos(t * 0.17 + s["ph"])
        place(im, _shape(s["k"], s["s"], s["col"]), x, y, sc=1 + 0.05 * math.sin(t * 1.3 + s["ph"]), a=0.32, rot=s["rot"] + t * 9 * (1 if s["ph"] > 3 else -1))


def rings(im, t):
    for cx, cy, r, sp, col in [(1720, 180, 250, 6, X.TVA), (200, 900, 210, -8, X.TVB), (1760, 930, 120, 14, PINK)]:
        place(im, _dashed_ring(r, col), X.sx(cx), X.sy(cy), a=0.3, rot=t * sp)


def depth_blobs(im, t):
    """large out-of-focus orbs drifting through the foreground now and then"""
    for i, (period, y, col, d) in enumerate([(23.0, 860, X.TVB, 300), (31.0, 220, PINK, 240)]):
        k = ((t + i * 9) % period) / 7.0
        if k < 1:
            x = lerp(-250, X.W + 250, k)
            place(im, X.cached(("BLOB", col, d), lambda: X._orb(col, d)), x, X.sy(y) + 60 * math.sin(k * 3), a=0.55)


# ---------------------------------------------------------------- camera & transitions
def camera(layer, t, idx, s, e):
    """slow 3.5% push-in with a gentle alternating drift over the scene"""
    k = inout(prog(t, s, max(0.5, e - s)))
    z = 1 + CFG["cam"] * k; dx = (CFG["drift"] if idx % 2 else -CFG["drift"]) * (k - 0.5); dy = 10 * math.sin(k * math.pi)
    if z < 1.002 and abs(dx) < 0.5: return layer
    w, h = layer.size; cx, cy = w / 2 + px(dx), h / 2 + px(dy)
    a = 1 / z
    return layer.transform(layer.size, Image.AFFINE, (a, 0, cx - a * w / 2, 0, a, cy - a * h / 2), resample=Image.BILINEAR)


def composite_scene(im, layer, t, s, e, first=False, last=False):
    """exit: layer slides left with a motion smear over [e-0.3, e+0.12]; entry: slides in from the right over [s, s+0.5]"""
    (lo, do, po), (di, pi) = CFG["out"], CFG["in"]
    ko = 0 if last else in_cubic(prog(t, e - lo, do))
    ki = 0 if first else 1 - out_cubic(prog(t, s, di))
    shift = po * ko + pi * ki
    if abs(shift) < 1:
        im.alpha_composite(layer); return
    sm = abs(shift) * 0.25; sgn = -1 if shift < 0 else 1
    for j, w in ((2, 0.18), (1, 0.3), (0, 0.75)):
        off = px(shift - sgn * sm * j)
        L = layer.copy(); L.putalpha(L.getchannel("A").point(lambda v, w=w: int(v * w)))
        im.alpha_composite(L, dest=(max(0, off), 0), source=(max(0, -off), 0))


def streaks(im, t):
    for s, e in CFG["spans"][:-1]:
        k = prog(t, e - CFG["streak"] * 0.4, CFG["streak"])
        if 0 < k < 1:
            r = rnd(int(e * 100))
            for j in range(7):
                y = X.sy(r.uniform(140, 940)); L = r.uniform(500, 1000) * min(1, X.W / 1920 * 1.4); th = r.uniform(3, 9); dl = r.uniform(0, 0.25)
                kk = clip((k - dl) / 0.75)
                if 0 < kk < 1:
                    x = lerp(-L, X.W + L, in_cubic(kk) * 0.5 + kk * 0.5)
                    place(im, _streak(L, th, [X.TVA, X.TVB, PINK][j % 3]), x - L / 2, y, a=0.7 * math.sin(math.pi * kk))
            kb = clip((k - 0.05) / 0.8)
            if 0 < kb < 1:
                place(im, X.cached(("BLOBT", X.BLOB), lambda: X._orb(X.BLOB, 700)), lerp(-400, X.W + 380, inout(kb)), X.H / 2 + 140 * math.sin(e), a=0.8 * math.sin(math.pi * kb))


# ---------------------------------------------------------------- HUD: chapter label + progress
def chapter_label(im, t):
    for i, ((s, e), name) in enumerate(zip(CFG["spans"], CFG["chapters"])):
        if not name or not (s <= t < e + 0.1): continue
        k = out_cubic(prog(t, s + 0.2, 0.6)); a = min(k, 1 - prog(t, e - 0.3, 0.35))
        if a <= 0: continue
        num = X.text(f"{i + 1:02d}", 20, "xbold", X.TVA, track=2); lab = X.text(name.upper(), 18, "demi", X.MUTE, track=4)
        x0 = 86; y = 1042
        bar = X.cached(("CHB",), lambda: X.grad_img(px(44), max(2, px(3))))
        wb = max(1, int(bar.width * k)); im.alpha_composite(bar.crop((0, 0, wb, bar.height)), (px(x0 + 34), px(y) - bar.height // 2))
        place(im, num, x0 + num.width / X.S / 2, y, a=a)
        if k > 0.05:
            wl = max(1, int(lab.width * k)); place(im, lab.crop((0, 0, wl, lab.height)), x0 + 92 + wl / X.S / 2, y, a=a)


def progress(im, t, dur):
    x0, x1, y = 1500, 1840, 1042
    a = 0.85 * min(prog(t, 1.0, 0.8), 1 - prog(t, dur - 2.5, 1.0))
    if a <= 0: return
    dr = ImageDraw.Draw(im); lw = max(1, px(3))
    dr.line([px(x0), px(y), px(x1), px(y)], fill=(205, 200, 240, int(255 * a)), width=lw)
    for s, _ in CFG["spans"]:
        xx = x0 + (x1 - x0) * s / dur; dr.ellipse([px(xx) - lw, px(y) - lw, px(xx) + lw, px(y) + lw], fill=(190, 184, 236, int(255 * a)))
    xe = x0 + (x1 - x0) * clip(t / dur)
    g = X.cached(("PRG",), lambda: X.grad_img(px(x1 - x0), lw))
    im.alpha_composite(g.crop((0, 0, max(1, px(xe - x0)), g.height)), (px(x0), px(y) - lw // 2))
    place(im, _dot(5, X.TVA), xe, y, sc=1 + 0.35 * beat_env(t, 7), a=a)
    place(im, _thin_ring(12, X.TVA, 2), xe, y, sc=1 + 0.6 * (1 - beat_env(t, 3)), a=a * 0.6 * beat_env(t, 3))


# ---------------------------------------------------------------- entry points
def back(im, t):
    grid(im, t); network(im, t); rings(im, t); shapes(im, t); particles(im, t, (0, 1)); beat_rings(im, t)


def front(im, t, dur):
    particles(im, t, (2,)); depth_blobs(im, t); streaks(im, t)
    if CFG["hud"]: chapter_label(im, t); progress(im, t, dur)
    grain(im, t)
