"""Motion-graphics B-roll + overlays for talking-head reels.
Each graphic is rendered as a transparent 1080x1920 30fps .mov (qtrle/argb) from Pillow frames.
Usage (run from the project work/ dir): python3 ../../../toolkit/gfx.py plan.json [names...]
  plan = list of {name, kind, dur, ev:{...}} in seconds local to the graphic; writes gfx/<name>.mov in the cwd
"""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # video-editing/
FB = os.path.join(ROOT, "assets/fonts/Montserrat-Black.ttf")
FX = os.path.join(ROOT, "assets/fonts/Montserrat-ExtraBold.ttf")
FU = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
NAVY = (14, 22, 58)
PURPLE = (52, 40, 170)
YEL = (255, 196, 0)
RED = (235, 64, 52)
GRN = (46, 204, 113)
WHITE = (255, 255, 255)
_fc = {}


def font(p, s):
    k = (p, s)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(p, s)
    return _fc[k]


def clip(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def p_(t, t0, d):
    return clip((t - t0) / d)


def out_cubic(x):
    return 1 - (1 - x) ** 3


def out_back(x, s=1.7):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def in_cubic(x):
    return x ** 3


def rrect(d, box, r, fill):
    d.rounded_rectangle(box, r, fill=fill)


def shadowed(base, layer, blur=18, off=10, alpha=110):
    a = layer.split()[3]
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: v * alpha // 255).filter(ImageFilter.GaussianBlur(blur)))
    base.alpha_composite(sh, (0, off))
    base.alpha_composite(layer)


def text_c(d, cx, y, s, f, fill, anchor="mt"):
    d.text((cx, y), s, font=f, fill=fill, anchor=anchor)


def tick(d, cx, cy, r, col, prog=1.0, w=12):
    pts = [(cx - r * 0.55, cy), (cx - r * 0.15, cy + r * 0.42), (cx + r * 0.6, cy - r * 0.45)]
    L1 = math.dist(pts[0], pts[1]); L2 = math.dist(pts[1], pts[2]); L = (L1 + L2) * prog
    if L <= 0:
        return
    if L <= L1:
        e = (pts[0][0] + (pts[1][0] - pts[0][0]) * L / L1, pts[0][1] + (pts[1][1] - pts[0][1]) * L / L1)
        d.line([pts[0], e], fill=col, width=w, joint="curve")
    else:
        k = (L - L1) / L2
        e = (pts[1][0] + (pts[2][0] - pts[1][0]) * k, pts[1][1] + (pts[2][1] - pts[1][1]) * k)
        d.line([pts[0], pts[1], e], fill=col, width=w, joint="curve")


def cross(d, cx, cy, r, col, w=12):
    d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=col, width=w)
    d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=col, width=w)


def scaled(layer, sc, cx, cy, alpha=1.0):
    """scale a full-frame layer around (cx,cy) and fade it"""
    if sc <= 0.01 or alpha <= 0:
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if abs(sc - 1) > 1e-3:
        lw, lh = int(W * sc), int(H * sc)
        sm = layer.resize((lw, lh), Image.BICUBIC)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.paste(sm, (int(cx - cx * sc), int(cy - cy * sc)), sm)
        layer = out
    if alpha < 1:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    return layer


def env(t, dur, fin=0.25, fout=0.22):
    """in/out envelope 0..1 with eased in and quicker out"""
    return out_cubic(p_(t, 0, fin)) * (1 - in_cubic(p_(t, dur - fout, fout)))


_BG = None
PAD = 120


def _bg_canvas():
    """full-resolution background, built once: smooth radial glows (float math, no upscaling),
    crisp 2px grid with intersection dots, fine grain to stop banding after compression"""
    global _BG
    if _BG is not None:
        return _BG
    import numpy as np
    w, h = W + PAD, H + PAD
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.zeros((h, w, 3), np.float32) + np.array(NAVY, np.float32)
    for (cx, cy, r, col, k) in [(300, 560, 760, (70, 52, 210), 0.95), (820, 1460, 820, (110, 40, 175), 0.85), (980, 180, 520, (30, 90, 200), 0.45)]:
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r / 2.2) ** 2)))[..., None] * k
        img = img * (1 - g) + np.array(col, np.float32) * g
    # vignette
    v = 1 - 0.35 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)[..., None] ** 1.3
    img *= np.clip(v, 0.55, 1)
    # grid (every 90px, 2px wide) + dots at intersections
    gm = np.zeros((h, w), np.float32)
    gm[:, (np.arange(w) % 90) < 2] = 1; gm[(np.arange(h) % 90) < 2, :] = 1
    img = img * (1 - 0.10 * gm[..., None]) + 255 * 0.10 * gm[..., None]
    dots = ((xx % 90) < 6) & ((yy % 90) < 6)
    img[dots] = img[dots] * 0.7 + 255 * 0.3
    img += np.random.default_rng(3).normal(0, 1.6, img.shape).astype(np.float32)  # dither grain
    _BG = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return _BG


def bg_full(t, dur):
    """full-screen branded background for B-roll cards: crisp full-res canvas, slow diagonal drift"""
    ox = int(PAD / 2 + 40 * math.sin(t * 0.6)); oy = int(PAD / 2 + 40 * math.cos(t * 0.5))
    return _bg_canvas().crop((ox, oy, ox + W, oy + H))


def wipe_in(frame, t, dur, fin=0.28, fout=0.25):
    """full-screen card: slides up in, slides up out (pairs with whoosh)"""
    a = out_cubic(p_(t, 0, fin)); b = in_cubic(p_(t, dur - fout, fout))
    y = int(H * (1 - a)) - int(H * b)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(frame, (0, y), frame)
    return out


# ---------------- graphics ----------------

def g_deals(t, dur, ev):
    """'500 BUSINESS DEALS' card, red strike draws on 'bilkul', NAHI stamp"""
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    cy = 1010
    rrect(d, [90, cy - 120, W - 90, cy + 120], 36, NAVY + (238,))
    rrect(d, [90, cy - 120, 104, cy + 120], 6, YEL + (255,))
    st = p_(t, ev["strike"], 0.35)
    col = WHITE if st < 1 else (170, 170, 190)
    text_c(d, W // 2, cy - 92, "500", font(FB, 110), YEL if st < 1 else (170, 150, 90))
    text_c(d, W // 2, cy + 30, "BUSINESS DEALS", font(FB, 66), col)
    if st > 0:
        x0, x1 = 140, 140 + (W - 280) * out_cubic(st)
        d.line([(x0, cy + 10), (x1, cy - 10)], fill=RED + (255,), width=16)
    sp = p_(t, ev["strike"] + 0.25, 0.3)
    if sp > 0:
        s = out_back(sp)
        S = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(S)
        rrect(sd, [W - 380, cy - 200, W - 110, cy - 100], 22, RED + (255,))
        text_c(sd, W - 245, cy - 150, "NAHI!", font(FB, 58), WHITE, "mm")
        S = S.rotate(-8, center=(W - 245, cy - 150), resample=Image.BICUBIC)
        L.alpha_composite(scaled(S, s, W - 245, cy - 150))
    e = env(t, dur); sc = 0.85 + 0.15 * out_back(p_(t, 0, 0.3))
    return scaled(L, sc, W // 2, cy, e)


def chip(d, y, icon_col, icon, label, f_icon=None):
    rrect(d, [80, y, W - 80, y + 112], 56, NAVY + (238,))
    d.ellipse([96, y + 14, 180, y + 98], fill=icon_col + (255,))
    if icon == "x":
        cross(d, 138, y + 56, 18, WHITE, 11)
    else:
        text_c(d, 138, y + 56, icon, f_icon or font(FB, 52), WHITE, "mm")
    d.text((206, y + 56), label, font=font(FB, 50), fill=WHITE, anchor="lm")


def g_chips(t, dur, ev):
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    items = [(ev["c1"], (52, 152, 219), "i", "SIRF INFORMATION", None),
             (ev["c2"], (243, 156, 18), "₹", "PRICE NEGOTIATION", font(FB, 54)),
             (ev["c3"], RED, "x", "IDEAL CUSTOMER NAHI", None)]
    for k, (t0, col, ic, lab, fi) in enumerate(items):
        if t < t0:
            continue
        L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
        y = 840 + k * 132
        chip(d, y, col, ic, lab, fi)
        a = out_back(p_(t, t0, 0.35), 1.3)
        dx = int(-W * (1 - a))
        e = 1 - in_cubic(p_(t, dur - 0.22, 0.22))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.paste(L, (dx, 0), L)
        out.alpha_composite(scaled(sh, 1.0, 0, 0, e))
    return out


def g_funnel(t, dur, ev):
    F = bg_full(t, dur); d = ImageDraw.Draw(F)
    text_c(d, W // 2, 250, "YE COMPARE KARO", font(FB, 72), YEL)
    text_c(d, W // 2, 345, "har stage pe kitne log bache?", font(FX, 44), (210, 210, 235))
    stages = [("INQUIRIES", ev["s0"], 0.98, (90, 110, 255)), ("PRICE POOCHA", ev["s1"], 0.84, (52, 152, 219)),
              ("NEGOTIATION KIYA", ev["s2"], 0.72, (243, 156, 18)), ("KHAREEDA", ev["s3"], 0.5, GRN)]
    top = 470
    for k, (lab, t0, wf, col) in enumerate(stages):
        pr = out_back(p_(t, t0, 0.45), 1.2)
        if pr <= 0:
            continue
        bw = (W - 160) * wf * pr; y = top + k * 175
        x0 = W / 2 - bw / 2
        rrect(d, [x0, y, x0 + bw, y + 140], 30, col + (255,))
        if pr > 0.6:
            a = int(255 * clip((pr - 0.6) / 0.4))
            d.text((W // 2, y + 70), lab, font=font(FB, 48), fill=(255, 255, 255, a), anchor="mm")
        if k == 3 and t > t0 + 0.15:
            # tick badge on the purchase stage
            tp = out_back(p_(t, t0 + 0.15, 0.3))
            r = 58 * tp
            cx, cy = x0 + bw + 82, y + 70
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
            tick(d, cx, cy, 52, GRN, p_(t, t0 + 0.25, 0.3), 13)
    for k in range(3):
        t0 = stages[k + 1][1]
        if t > t0:
            y = top + k * 175 + 140
            d.polygon([(W / 2 - 22, y + 8), (W / 2 + 22, y + 8), (W / 2, y + 32)], fill=(255, 255, 255, 160))
    return wipe_in(F, t, dur)


def g_system(t, dur, ev):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    y0 = 760
    rrect(d, [90, y0, W - 90, y0 + 470], 40, (255, 255, 255, 245))
    rrect(d, [90, y0, W - 90, y0 + 96], 40, PURPLE + (255,)); d.rectangle([90, y0 + 56, W - 90, y0 + 96], fill=PURPLE + (255,))
    d.text((140, y0 + 48), "LEAD TRACKER", font=font(FB, 46), fill=WHITE, anchor="lm")
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([W - 230 + i * 44, y0 + 34, W - 202 + i * 44, y0 + 62], fill=c)
    rows = ["Inquiry aayi", "Price poocha", "Negotiation hua", "Customer bana"]
    for k, r in enumerate(rows):
        y = y0 + 130 + k * 82
        tk = ev["t0"] + 0.18 + k * ev["gap"]
        on = t >= tk
        d.rounded_rectangle([140, y, 196, y + 56], 12, fill=GRN if on else (225, 228, 240))
        if on:
            tick(d, 168, y + 28, 30, WHITE, p_(t, tk, 0.22), 8)
        d.text((226, y + 28), r, font=font(FX, 46), fill=NAVY if on else (150, 155, 175), anchor="lm")
    e = env(t, dur); sc = 0.8 + 0.2 * out_back(p_(t, 0, 0.35))
    return scaled(L, sc, W // 2, y0 + 235, e)


def g_stat(t, dur, ev):
    F = bg_full(t, dur); d = ImageDraw.Draw(F)
    cnt = int(500 * out_cubic(p_(t, ev["count0"], ev["count1"] - ev["count0"])))
    text_c(d, W // 2, 250, f"{cnt}", font(FB, 240), WHITE)
    text_c(d, W // 2, 520, "LEADS AAYI", font(FB, 66), (200, 205, 240))
    rv = p_(t, ev["reveal"], 0.4)
    if rv > 0:
        a = out_cubic(rv)
        ay = 630
        d.line([(W / 2, ay), (W / 2, ay + 150 * a)], fill=YEL, width=14)
        if a > 0.9:
            d.polygon([(W / 2 - 36, ay + 140), (W / 2 + 36, ay + 140), (W / 2, ay + 190)], fill=YEL)
        S = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(S)
        text_c(sd, W // 2, 830, "SIRF 20", font(FB, 150), YEL)
        text_c(sd, W // 2, 1000, "QUALIFIED", font(FB, 84), WHITE)
        F.alpha_composite(scaled(S, 0.6 + 0.4 * out_back(p_(t, ev["reveal"] + 0.15, 0.4)), W // 2, 920, p_(t, ev["reveal"] + 0.15, 0.2)))
        bp = p_(t, ev["reveal"] + 0.6, 0.35)
        if bp > 0:
            B = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(B)
            rrect(bd, [W / 2 - 170, 1120, W / 2 + 170, 1225], 52, RED + (255,))
            text_c(bd, W // 2, 1172, "= 4%", font(FB, 64), WHITE, "mm")
            F.alpha_composite(scaled(B, out_back(bp), W // 2, 1172))
    return wipe_in(F, t, dur)


def g_compare(t, dur, ev):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    y = 930
    rrect(d, [70, y, W - 70, y + 230], 40, NAVY + (240,))
    text_c(d, 280, y + 50, "100", font(FB, 96), WHITE)
    text_c(d, 280, y + 160, "LEADS", font(FX, 40), (200, 205, 240))
    text_c(d, W // 2, y + 70, "→", font(FU, 90), YEL)
    q = p_(t, ev["q"], 0.35)
    if q > 0:
        S = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(S)
        text_c(sd, W - 280, y + 50, "20", font(FB, 96), YEL)
        text_c(sd, W - 280, y + 160, "QUALIFIED", font(FX, 40), (200, 205, 240))
        L.alpha_composite(scaled(S, 0.5 + 0.5 * out_back(q), W - 280, y + 110, clip(q * 3)))
    bp = p_(t, ev["q"] + 0.5, 0.35)
    if bp > 0:
        B = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(B)
        rrect(bd, [W / 2 - 150, y - 60, W / 2 + 150, y + 20], 40, GRN + (255,))
        text_c(bd, W // 2, y - 20, "= 20%", font(FB, 50), WHITE, "mm")
        L.alpha_composite(scaled(B, out_back(bp), W // 2, y - 20))
    e = env(t, dur); sc = 0.85 + 0.15 * out_back(p_(t, 0, 0.3))
    return scaled(L, sc, W // 2, y + 115, e)


GFX = {"deals": g_deals, "chips": g_chips, "funnel": g_funnel, "system": g_system, "stat": g_stat, "compare": g_compare}


def draw(kind, t, dur, ev, data=None):
    """kinds from gfx_pro take a 4th 'data' arg (texts, items, colours) so they are reusable across videos"""
    if kind not in GFX:
        import gfx_pro  # noqa: F401  (registers its kinds into GFX)
    if kind not in GFX:
        import gfx_product  # noqa: F401  (product-ad kinds)
    f = GFX[kind]
    return f(t, dur, ev, data or {}) if getattr(f, "takes_data", False) else f(t, dur, ev)


def render(name, kind, dur, ev, out, data=None):
    n = int(round(dur * FPS))
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", out], stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        p.stdin.write(draw(kind, t, dur, ev, data).tobytes())
    p.stdin.close(); p.wait()
    print(f"{name}: {dur:.2f}s -> {out}", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.modules.setdefault("gfx", sys.modules["__main__"])  # let gfx_pro import this module
    plan = json.load(open(sys.argv[1]))
    only = sys.argv[2:] or None
    os.makedirs("gfx", exist_ok=True)
    for g in plan:
        if only and g["name"] not in only:
            continue
        if g.get("still") is not None:
            draw(g["kind"], g["still"], g["dur"], g["ev"], g.get("data")).save(f"gfx_{g['name']}_still.png"); continue
        render(g["name"], g["kind"], g["dur"], g["ev"], f"gfx/{g['name']}.mov", g.get("data"))
