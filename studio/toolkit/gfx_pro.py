"""Data-driven motion-graphics kinds (reusable across videos). Registered into gfx.GFX on import.
Each kind: f(t, dur, ev, data) -> RGBA 1080x1920 frame. ev = event times (s, local to the graphic), data = texts/items.
Overlay kinds keep to the lower-middle band (y ~ 760-1230) so faces stay clear and captions (y ~ 1250-1350) stay readable;
full-screen kinds (ecosystem, leak, cta) use the branded background.
"""
import math, os
from PIL import Image, ImageDraw, ImageChops
import gfx
from gfx import (W, H, FB, FX, FU, NAVY, PURPLE, YEL, RED, GRN, WHITE, font, clip, p_, out_cubic, out_back, in_cubic,
                 rrect, text_c, tick, cross, scaled, env, bg_full, wipe_in)

BLUE = (52, 152, 219); ORANGE = (243, 156, 18); TEAL = (26, 188, 156); PINK = (232, 67, 147)
PALETTE = [BLUE, ORANGE, TEAL, PINK, GRN, YEL]


def kind(name):
    def deco(f):
        f.takes_data = True; gfx.GFX[name] = f; return f
    return deco


_LOGOS = {}


def _logo(path):
    """brand logo (RGBA), path relative to the studio root; cached"""
    if path not in _LOGOS:
        _LOGOS[path] = Image.open(path if os.path.isabs(path) else os.path.join(gfx.ROOT, path)).convert("RGBA")
    return _LOGOS[path]


def in_out(x):
    x = clip(x); return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def blank():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def layer_at(L, dx=0, dy=0):
    out = blank(); out.paste(L, (int(dx), int(dy)), L); return out


def fade(L, a):
    return scaled(L, 1.0, 0, 0, a)


def card(d, box, r=36, fill=NAVY + (240,), accent=None):
    rrect(d, box, r, fill)
    if accent:
        rrect(d, [box[0], box[1], box[0] + 12, box[3]], 6, accent + (255,))


def fit_font(path, text, max_w, size):
    while size > 20 and font(path, size).getlength(text) > max_w:
        size -= 2
    return font(path, size)


# ---------------------------------------------------------------- puzzle: "you see only one piece"
@kind("puzzle")
def g_puzzle(t, dur, ev, data):
    """2x2 tiles; known tiles light up at ev['k0'], ev['k1']...; unknown '?' tiles at ev['q']; caption tag at ev['tag']"""
    known = data.get("known", ["ADS", "LEADS"]); unknown = data.get("unknown", 2)
    out = blank()
    x0, y0, tw, th, gap = 190, 800, 340, 190, 20
    tiles = [(known[i], "k%d" % i, YEL) for i in range(len(known))] + [("?", "q", (70, 78, 120))] * unknown
    for i, (lab, key, col) in enumerate(tiles):
        t0 = ev.get(key, 0) + (0.12 * (i - len(known)) if key == "q" else 0)
        pr = p_(t, t0, 0.35)
        if pr <= 0: continue
        L = blank(); d = ImageDraw.Draw(L)
        cx = x0 + (i % 2) * (tw + gap); cy = y0 + (i // 2) * (th + gap)
        rrect(d, [cx, cy, cx + tw, cy + th], 28, (col + (255,)) if key != "q" else (30, 36, 70, 235))
        if key == "q":
            d.rounded_rectangle([cx, cy, cx + tw, cy + th], 28, outline=(120, 130, 190, 255), width=4)
            sh = (math.sin(t * 6 + i) + 1) / 2
            text_c(d, cx + tw / 2, cy + th / 2, "?", font(FB, 110), (150 + int(60 * sh), 160 + int(60 * sh), 220, 255), "mm")
        else:
            text_c(d, cx + tw / 2, cy + th / 2, lab, fit_font(FB, lab, tw - 40, 64), NAVY, "mm")
        out.alpha_composite(scaled(L, 0.6 + 0.4 * out_back(pr), cx + tw / 2, cy + th / 2, clip(pr * 3)))
    tg = p_(t, ev.get("tag", 99), 0.35)
    if tg > 0:
        L = blank(); d = ImageDraw.Draw(L)
        txt = data.get("tag", "SIRF 1 HISSA!")
        w = font(FB, 56).getlength(txt) + 70
        rrect(d, [W / 2 - w / 2, 700, W / 2 + w / 2, 784], 42, RED + (255,))
        text_c(d, W / 2, 742, txt, font(FB, 56), WHITE, "mm")
        L = L.rotate(-4, center=(W / 2, 742), resample=Image.BICUBIC)
        out.alpha_composite(scaled(L, out_back(tg), W / 2, 742))
    return fade(out, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- flow: A -> B with particles, then a twist tag
@kind("flow")
def g_flow(t, dur, ev, data):
    a, b = data.get("a", "ADS"), data.get("b", "TRAFFIC")
    L = blank(); d = ImageDraw.Draw(L)
    y = 900
    card(d, [80, y, 400, y + 170], 36, NAVY + (240,))
    text_c(d, 240, y + 85, a, fit_font(FB, a, 280, 64), YEL, "mm")
    bp = p_(t, ev.get("b", 0.5), 0.35)
    if bp > 0:
        B = blank(); bd = ImageDraw.Draw(B)
        card(bd, [W - 420, y, W - 80, y + 170], 36, NAVY + (240,))
        # people icon dots
        for k in range(3):
            cx = W - 340 + k * 34; bd.ellipse([cx - 13, y + 34, cx + 13, y + 60], fill=WHITE); bd.rounded_rectangle([cx - 18, y + 64, cx + 18, y + 92], 10, fill=WHITE)
        text_c(bd, W - 250 + 40, y + 120, b, fit_font(FB, b, 300, 46), WHITE, "mm")
        L.alpha_composite(scaled(B, 0.6 + 0.4 * out_back(bp), W - 250, y + 85, clip(bp * 3)))
    # arrow + particles
    ax0, ax1 = 420, W - 440
    ap = out_cubic(p_(t, ev.get("arrow", 0.2), 0.5))
    if ap > 0:
        d.line([(ax0, y + 85), (ax0 + (ax1 - ax0) * ap, y + 85)], fill=(255, 255, 255, 120), width=6)
        if ap >= 1:
            d.polygon([(ax1, y + 65), (ax1 + 28, y + 85), (ax1, y + 105)], fill=(255, 255, 255, 200))
            for k in range(6):
                ph = ((t * 0.9 + k / 6) % 1)
                px = ax0 + (ax1 - ax0) * ph
                d.ellipse([px - 9, y + 76, px + 9, y + 94], fill=YEL + (int(255 * math.sin(math.pi * ph)),))
    tg = p_(t, ev.get("twist", 99), 0.35)
    if tg > 0:
        T = blank(); td = ImageDraw.Draw(T)
        txt = data.get("twist", "PAR...?")
        w = font(FB, 60).getlength(txt) + 80
        rrect(td, [W / 2 - w / 2, y + 205, W / 2 + w / 2, y + 295], 45, YEL + (255,))
        text_c(td, W / 2, y + 250, txt, font(FB, 60), NAVY, "mm")
        L.alpha_composite(scaled(T, out_back(tg), W / 2, y + 250))
    e = env(t, dur); sc = 0.9 + 0.1 * out_back(p_(t, 0, 0.3))
    return scaled(L, sc, W / 2, y + 85, e)


# ---------------------------------------------------------------- chiplist: labelled chips slide in on their words
@kind("chiplist")
def g_chiplist(t, dur, ev, data):
    items = data["items"]; y0 = data.get("y0", 770); hgt = data.get("h", 96); gap = data.get("gap", 112)
    out = blank()
    for k, it in enumerate(items):
        t0 = ev.get(f"c{k}", 0)
        if t < t0: continue
        L = blank(); d = ImageDraw.Draw(L)
        y = y0 + k * gap; col = tuple(it.get("color", PALETTE[k % len(PALETTE)]))
        rrect(d, [90, y, W - 90, y + hgt], hgt // 2, NAVY + (240,))
        d.ellipse([104, y + 12, 104 + hgt - 24, y + hgt - 12], fill=col + (255,))
        text_c(d, 104 + (hgt - 24) / 2, y + hgt / 2, str(k + 1), font(FB, 44), WHITE, "mm")
        d.text((104 + hgt, y + hgt / 2), it["label"], font=fit_font(FB, it["label"], W - 340, 48), fill=WHITE, anchor="lm")
        a = out_back(p_(t, t0, 0.35), 1.3)
        out.alpha_composite(layer_at(L, -W * (1 - a), 0))
    rp = p_(t, ev.get("result", 99), 0.4)
    if rp > 0:
        L = blank(); d = ImageDraw.Draw(L)
        txt = data.get("result", "CUSTOMER BANEGA?")
        y = y0 + len(items) * gap + 6; w = font(FB, 50).getlength(txt) + 170
        rrect(d, [W / 2 - w / 2, y, W / 2 + w / 2, y + 90], 45, YEL + (255,))
        text_c(d, W / 2 - 40, y + 45, txt, font(FB, 50), NAVY, "mm")
        cx = W / 2 + w / 2 - 60; on = (t - ev.get("result", 0)) % 0.8 < 0.4
        d.ellipse([cx - 32, y + 13, cx + 32, y + 77], fill=(GRN if on else RED) + (255,))
        (tick(d, cx, y + 45, 26, WHITE, 1.0, 8) if on else cross(d, cx, y + 45, 14, WHITE, 8))
        out.alpha_composite(scaled(L, out_back(rp), W / 2, y + 45))
    return fade(out, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- ecosystem: full-screen node ring around a core
@kind("ecosystem")
def g_ecosystem(t, dur, ev, data):
    F = bg_full(t, dur); d = ImageDraw.Draw(F)
    h1 = data.get("head1", "PERFORMANCE MARKETING")
    text_c(d, W / 2, 190, h1, fit_font(FB, h1, W - 120, 64), WHITE)
    # "≠ SIRF EK PROCESS" then struck, replaced by "= ECOSYSTEM"
    sp = p_(t, ev.get("not", 0.3), 0.3)
    if sp > 0:
        L = blank(); ld = ImageDraw.Draw(L)
        txt = data.get("not", "SIRF EK PROCESS")
        text_c(ld, W / 2, 290, txt, font(FB, 58), (200, 205, 240))
        stp = p_(t, ev.get("eco", 99), 0.3)
        if stp > 0:
            w = font(FB, 58).getlength(txt)
            ld.line([(W / 2 - w / 2 - 10, 322), (W / 2 - w / 2 - 10 + (w + 20) * out_cubic(stp), 322)], fill=RED + (255,), width=12)
        a = (1 - p_(t, ev.get("eco", 99) + 0.35, 0.25))
        F.alpha_composite(scaled(L, 1, 0, 0, sp * a))
    ep = p_(t, ev.get("eco", 99) + 0.35, 0.35)
    if ep > 0:
        L = blank(); ld = ImageDraw.Draw(L)
        text_c(ld, W / 2, 285, data.get("eco", "= ECOSYSTEM"), font(FB, 76), YEL)
        F.alpha_composite(scaled(L, 0.7 + 0.3 * out_back(ep), W / 2, 320, clip(ep * 2)))
    cx, cy, R = W / 2, 860, 320
    nodes = data.get("nodes", ["ADS", "OFFER", "LANDING PAGE", "SALES", "CRO", "TRACKING"])
    n = len(nodes); t0, t1 = ev.get("n0", 0.4), ev.get("n1", 2.5)
    rot = 0.08 * max(0, t - ev.get("eco", 99))
    pts = [(cx + R * math.cos(-math.pi / 2 + 2 * math.pi * k / n + rot), cy + R * math.sin(-math.pi / 2 + 2 * math.pi * k / n + rot)) for k in range(n)]
    # ring connections draw in
    for k in range(n):
        tk = t0 + (t1 - t0) * k / max(1, n - 1)
        lp = out_cubic(p_(t, tk + 0.2, 0.4))
        if lp > 0:
            a, b = pts[k], pts[(k + 1) % n]
            d.line([a, (a[0] + (b[0] - a[0]) * lp, a[1] + (b[1] - a[1]) * lp)], fill=(255, 255, 255, 110), width=5)
            d.line([a, (a[0] + (cx - a[0]) * lp, a[1] + (cy - a[1]) * lp)], fill=(255, 196, 0, 70), width=3)
    # core
    cp = p_(t, ev.get("core", 99), 0.45)
    pulse = 1 + 0.03 * math.sin(t * 5)
    if cp > 0:
        L = blank(); ld = ImageDraw.Draw(L); r = 170 * pulse
        for g_ in range(4, 0, -1):
            ld.ellipse([cx - r - g_ * 14, cy - r - g_ * 14, cx + r + g_ * 14, cy + r + g_ * 14], fill=YEL + (18 * g_,))
        ld.ellipse([cx - r, cy - r, cx + r, cy + r], fill=YEL + (255,))
        for i, line in enumerate(data.get("core", ["CUSTOMER", "ACQUISITION", "SYSTEM"])):
            text_c(ld, cx, cy - 62 + i * 62, line, fit_font(FB, line, 2 * r - 40, 46), NAVY, "mm")
        F.alpha_composite(scaled(L, out_back(cp), cx, cy, clip(cp * 3)))
    for k, (lab, (px, py)) in enumerate(zip(nodes, pts)):
        tk = t0 + (t1 - t0) * k / max(1, n - 1); np_ = p_(t, tk, 0.35)
        if np_ <= 0: continue
        L = blank(); ld = ImageDraw.Draw(L)
        col = PALETTE[k % len(PALETTE)]; f = fit_font(FB, lab, 290, 46); w = max(170, f.getlength(lab) + 56)
        rrect(ld, [px - w / 2, py - 48, px + w / 2, py + 48], 48, col + (255,))
        text_c(ld, px, py, lab, f, WHITE, "mm")
        F.alpha_composite(scaled(L, out_back(np_), px, py, clip(np_ * 3)))
    return wipe_in(F, t, dur)


# ---------------------------------------------------------------- checklist: white card, rows tick on their words
@kind("checklist")
def g_checklist(t, dur, ev, data):
    rows = data["rows"]; title = data.get("title", "")
    L = blank(); d = ImageDraw.Draw(L)
    rh = 92; y0 = data.get("y0", 800); hh = 96 if title else 0; hgt = hh + 30 + rh * len(rows)
    rrect(d, [90, y0, W - 90, y0 + hgt], 40, (255, 255, 255, 245))
    if title:
        rrect(d, [90, y0, W - 90, y0 + hh], 40, PURPLE + (255,)); d.rectangle([90, y0 + hh - 40, W - 90, y0 + hh], fill=PURPLE + (255,))
        d.text((140, y0 + hh / 2), title, font=font(FB, 46), fill=WHITE, anchor="lm")
    for k, r in enumerate(rows):
        y = y0 + hh + 20 + k * rh; tk = ev.get(f"r{k}", 0.2 + 0.3 * k); on = t >= tk
        d.rounded_rectangle([140, y + 10, 206, y + 76], 14, fill=GRN if on else (225, 228, 240))
        if on: tick(d, 173, y + 43, 34, WHITE, p_(t, tk, 0.22), 9)
        rf = fit_font(FB if on else FX, r, W - 420, 54)
        d.text((236, y + 43), r, font=rf, fill=NAVY if on else (160, 165, 185), anchor="lm")
        if on and data.get("highlight"):
            sw = out_cubic(p_(t, tk, 0.3)) * rf.getlength(r)
            d.rectangle([236, y + 66, 236 + sw, y + 74], fill=YEL)
    e = env(t, dur); sc = 0.85 + 0.15 * out_back(p_(t, 0, 0.35))
    return scaled(L, sc, W / 2, y0 + hgt / 2, e)


# ---------------------------------------------------------------- bars: analytics card, bars rise, best one selected
@kind("bars")
def g_bars(t, dur, ev, data):
    L = blank(); d = ImageDraw.Draw(L)
    y0, y1 = 790, 1220
    rrect(d, [90, y0, W - 90, y1], 40, NAVY + (242,))
    d.text((140, y0 + 60), data.get("title", "MEASURE → SELECT"), font=font(FB, 46), fill=WHITE, anchor="lm")
    vals = data.get("values", [0.45, 0.7, 0.35, 0.92, 0.55]); labs = data.get("labels", ["A", "B", "C", "D", "E"]); best = vals.index(max(vals))
    bw = 110; gap = (W - 260 - bw * len(vals)) / (len(vals) - 1); base = y1 - 70; top = y0 + 130
    for k, v in enumerate(vals):
        gp = out_cubic(p_(t, ev.get("grow", 0.2) + 0.08 * k, 0.6))
        x = 130 + k * (bw + gap); hgt = (base - top) * v * gp
        sel = t >= ev.get("select", 99)
        col = (GRN if (sel and k == best) else ((90, 100, 160) if sel else BLUE)) + (255,)
        d.rounded_rectangle([x, base - hgt, x + bw, base], 14, fill=col)
        d.text((x + bw / 2, base + 34), labs[k], font=font(FX, 34), fill=(200, 205, 240), anchor="mm")
        if sel and k == best:
            sp = out_back(p_(t, ev["select"], 0.35)); r = 34 * sp
            d.ellipse([x + bw / 2 - r, base - hgt - 60 - r, x + bw / 2 + r, base - hgt - 60 + r], fill=WHITE)
            tick(d, x + bw / 2, base - hgt - 60, 28 * sp, GRN, p_(t, ev["select"] + 0.1, 0.25), 8)
    e = env(t, dur); sc = 0.85 + 0.15 * out_back(p_(t, 0, 0.35))
    return scaled(L, sc, W / 2, (y0 + y1) / 2, e)


# ---------------------------------------------------------------- leak: full-screen pipeline, one stage cracks, money leaks
@kind("leak")
def g_leak(t, dur, ev, data):
    F = bg_full(t, dur); d = ImageDraw.Draw(F)
    stages = data.get("stages", ["ADS", "OFFER", "LANDING PAGE", "SALES", "CRO"]); weak = data.get("weak", 2)
    text_c(d, W / 2, 170, data.get("head", "EK BHI STAGE WEAK?"), font(FB, 66), WHITE)
    x0, x1 = 230, W - 230; y0 = 300; sh = 118; gap = 26
    wk = p_(t, ev.get("weak", 99), 0.3); lk = t >= ev.get("leak", 99)
    shake = (math.sin(t * 70) * 8 * (1 - p_(t, ev.get("weak", 99) + 0.3, 0.5))) if wk > 0 else 0
    for k, s in enumerate(stages):
        sp = p_(t, ev.get("s0", 0.2) + 0.12 * k, 0.3)
        if sp <= 0: continue
        y = y0 + k * (sh + gap); col = PALETTE[k % len(PALETTE)]
        dx = shake if k == weak else 0
        if k == weak and wk > 0:
            col = tuple(int(c * (1 - wk) + r * wk) for c, r in zip(col, RED))
        L = blank(); ld = ImageDraw.Draw(L)
        rrect(ld, [x0 + dx, y, x1 + dx, y + sh], 30, col + (255,))
        text_c(ld, W / 2 + dx, y + sh / 2, s, fit_font(FB, s, x1 - x0 - 60, 50), WHITE, "mm")
        if k == weak and wk > 0:  # crack
            cxp = x1 - 90 + dx
            ld.line([(cxp, y), (cxp - 22, y + 40), (cxp + 10, y + 64), (cxp - 18, y + sh)], fill=(40, 10, 10, 255), width=7)
            tg = out_back(wk); r = 44 * tg
            ld.rounded_rectangle([x1 + 20 + dx, y + sh / 2 - r * 0.9, x1 + 20 + dx + 150 * tg, y + sh / 2 + r * 0.9], 20, fill=RED + (255,))
            if tg > 0.6: text_c(ld, x1 + 95 + dx, y + sh / 2, "WEAK", font(FB, 36), WHITE, "mm")
        F.alpha_composite(scaled(L, 0.8 + 0.2 * out_back(sp), W / 2, y + sh / 2, clip(sp * 3)))
        if k < len(stages) - 1:
            d.polygon([(W / 2 - 18, y + sh + 4), (W / 2 + 18, y + sh + 4), (W / 2, y + sh + gap - 2)], fill=(255, 255, 255, 140))
    # money flow: coins dropping through the pipe, then leaking out of the weak stage
    yw = y0 + weak * (sh + gap) + sh / 2
    for k in range(10):
        ph = (t * 0.55 + k / 10) % 1
        if not lk:
            yy = y0 - 40 + ph * (len(stages) * (sh + gap)); xx = x0 - 70
            if t > ev.get("s0", 0.2) + 0.6:
                d.ellipse([xx - 22, yy - 22, xx + 22, yy + 22], fill=YEL + (230,)); text_c(d, xx, yy, "₹", font(FB, 30), NAVY, "mm")
        else:
            lt0 = t - ev["leak"] - k * 0.11
            if lt0 < 0: continue
            lt = lt0 % 1.1  # continuous stream of coins spilling out of the weak stage
            xx = x1 + 10 + lt * (180 + 70 * (k % 3)); yy = yw + 20 + 520 * lt * lt + (k % 4) * 8
            if yy > H: continue
            d.ellipse([xx - 32, yy - 32, xx + 32, yy + 32], fill=YEL + (245,)); text_c(d, xx, yy, "₹", font(FB, 40), NAVY, "mm")
    if lk:
        bp = out_back(p_(t, ev["leak"] + 0.3, 0.35))
        L = blank(); ld = ImageDraw.Draw(L)
        txt = data.get("leak", "PAISA BARBAAD!")
        w = font(FB, 74).getlength(txt) + 90
        rrect(ld, [W / 2 - w / 2, 1080, W / 2 + w / 2, 1190], 55, RED + (255,))
        text_c(ld, W / 2, 1135, txt, font(FB, 74), WHITE, "mm")
        F.alpha_composite(scaled(L, bp, W / 2, 1135))
    return wipe_in(F, t, dur)


# ---------------------------------------------------------------- growth: line rises then turns erratic + red verdict
@kind("growth")
def g_growth(t, dur, ev, data):
    L = blank(); d = ImageDraw.Draw(L)
    y0, y1 = 790, 1225
    rrect(d, [90, y0, W - 90, y1], 40, NAVY + (242,))
    d.text((140, y0 + 56), data.get("title", "GROWTH"), font=font(FB, 44), fill=WHITE, anchor="lm")
    gx0, gx1, gy0, gy1 = 150, W - 150, y0 + 110, y1 - 50
    for k in range(4):
        yy = gy0 + (gy1 - gy0) * k / 3; d.line([(gx0, yy), (gx1, yy)], fill=(255, 255, 255, 25), width=2)
    pts = [0.15, 0.25, 0.32, 0.45, 0.38, 0.62, 0.3, 0.7, 0.2, 0.55, 0.12, 0.4]
    dp = p_(t, ev.get("draw", 0.2), ev.get("draw_len", 2.0)); n = len(pts)
    shown = dp * (n - 1)
    poly = []
    for k in range(n):
        if k > shown + 1: break
        fx = gx0 + (gx1 - gx0) * k / (n - 1); fy = gy1 - (gy1 - gy0) * pts[k]
        if k > shown:
            pk = shown - (k - 1); px, py = poly[-1]; fx = px + (fx - px) * pk; fy = py + (fy - py) * pk
        poly.append((fx, fy))
    if len(poly) > 1:
        bad = t >= ev.get("verdict", 99)
        d.line(poly, fill=(RED if bad else GRN) + (255,), width=10, joint="curve")
        d.ellipse([poly[-1][0] - 12, poly[-1][1] - 12, poly[-1][0] + 12, poly[-1][1] + 12], fill=WHITE)
    vp = p_(t, ev.get("verdict", 99), 0.35)
    if vp > 0:
        V = blank(); vd = ImageDraw.Draw(V)
        txt = data.get("verdict", "PREDICTABLE GROWTH ✕"); txt = txt.replace(" ✕", "")
        w = font(FB, 48).getlength(txt) + 140
        rrect(vd, [W / 2 - w / 2, y0 - 115, W / 2 + w / 2, y0 - 25], 45, RED + (255,))
        vd.text((W / 2 - w / 2 + 40, y0 - 70), txt, font=font(FB, 48), fill=WHITE, anchor="lm")
        cross(vd, W / 2 + w / 2 - 50, y0 - 70, 16, WHITE, 8)
        L.alpha_composite(scaled(V, out_back(vp), W / 2, y0 - 70))
    e = env(t, dur); sc = 0.85 + 0.15 * out_back(p_(t, 0, 0.35))
    return scaled(L, sc, W / 2, (y0 + y1) / 2, e)


# ---------------------------------------------------------------- versus: bad card crossed, good card ticked
@kind("versus")
def g_versus(t, dur, ev, data):
    out = blank()
    bad, good = data.get("bad", "LEADS"), data.get("good", "BUSINESS GENERATED")
    y = 850
    bp = p_(t, ev.get("bad", 0), 0.35)
    if bp > 0:
        L = blank(); d = ImageDraw.Draw(L)
        dim = p_(t, ev.get("good", 99), 0.3)
        rrect(d, [120, y, W - 120, y + 140], 40, (int(14 + 40 * dim), 22, 58, 240))
        text_c(d, W / 2 - 40, y + 70, bad, fit_font(FB, bad, W - 420, 64), (255, 255, 255, int(255 - 110 * dim)), "mm")
        xp = p_(t, ev.get("bad", 0) + 0.3, 0.3)
        if xp > 0:
            r = 40 * out_back(xp); cx = W - 200
            d.ellipse([cx - r, y + 70 - r, cx + r, y + 70 + r], fill=RED + (255,)); cross(d, cx, y + 70, 16 * xp, WHITE, 9)
        out.alpha_composite(scaled(L, 0.7 + 0.3 * out_back(bp), W / 2, y + 70, clip(bp * 3)))
    gp = p_(t, ev.get("good", 99), 0.4)
    if gp > 0:
        L = blank(); d = ImageDraw.Draw(L)
        rrect(d, [100, y + 170, W - 100, y + 330], 44, YEL + (255,))
        text_c(d, W / 2 - 40, y + 250, good, fit_font(FB, good, W - 400, 60), NAVY, "mm")
        r = 42; cx = W - 180
        d.ellipse([cx - r, y + 250 - r, cx + r, y + 250 + r], fill=GRN + (255,)); tick(d, cx, y + 250, 34, WHITE, p_(t, ev["good"] + 0.25, 0.25), 9)
        out.alpha_composite(scaled(L, 0.6 + 0.4 * out_back(gp), W / 2, y + 250, clip(gp * 3)))
    return fade(out, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- cta: full-screen end card with follow button tap
@kind("cta")
def g_cta(t, dur, ev, data):
    F = bg_full(t, dur); d = ImageDraw.Draw(F)
    brand = data.get("brand", "YOUR BRAND"); sub = data.get("sub", "Practical growth breakdowns")
    lp = p_(t, 0.15, 0.5)
    if data.get("logo"):
        # brand logo image: pops in, then a light sheen sweeps across it
        logo = _logo(data["logo"]); lw = data.get("logo_w", 900); cy = 640
        sc = 0.55 + 0.45 * out_back(lp)
        if lp > 0:
            w_ = int(lw * sc); h_ = int(logo.height * w_ / logo.width)
            L = logo.resize((w_, h_), Image.LANCZOS)
            sp = p_(t, 0.9, 0.7)
            if 0 < sp < 1:
                band = Image.new("L", L.size, 0); bd = ImageDraw.Draw(band); x = -200 + (w_ + 400) * in_out(sp)
                bd.polygon([(x, 0), (x + 90, 0), (x + 90 - h_ * 0.4, h_), (x - h_ * 0.4, h_)], fill=170)
                band = ImageChops.multiply(band, L.getchannel("A"))
                L = L.copy(); L.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", L.size, (255, 255, 240)).split(), band)))
            if lp < 1:
                L.putalpha(L.getchannel("A").point(lambda v: int(v * clip(lp * 2.5))))
            F.alpha_composite(L, (int(W / 2 - w_ / 2), int(cy - h_ / 2)))
        bp = p_(t, 0.45, 0.4)
        if bp > 0:
            L = blank(); ld = ImageDraw.Draw(L)
            text_c(ld, W / 2, 900, sub, font(FX, 50), (215, 220, 245))
            F.alpha_composite(scaled(layer_at(L, 0, 30 * (1 - out_cubic(bp))), 1, 0, 0, bp))
    else:
        # logo mark: rising bars in a circle
        cx, cy = W / 2, 560; r = 150 * out_back(lp)
        if r > 1:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=YEL + (255,))
            for k, hh in enumerate([0.35, 0.6, 0.9]):
                bh = 150 * hh * out_cubic(p_(t, 0.35 + 0.1 * k, 0.4)); bx = cx - 75 + k * 55
                d.rounded_rectangle([bx, cy + 70 - bh, bx + 40, cy + 70], 8, fill=NAVY)
        bp = p_(t, 0.45, 0.4)
        if bp > 0:
            L = blank(); ld = ImageDraw.Draw(L)
            text_c(ld, W / 2, 760, brand, fit_font(FB, brand, W - 120, 96), WHITE)
            text_c(ld, W / 2, 880, sub, font(FX, 46), (200, 205, 240))
            F.alpha_composite(layer_at(L, 0, 40 * (1 - out_cubic(bp))).copy() if bp >= 1 else scaled(layer_at(L, 0, 40 * (1 - out_cubic(bp))), 1, 0, 0, bp))
    fp = p_(t, ev.get("follow", 0.8), 0.35)
    if fp > 0:
        L = blank(); ld = ImageDraw.Draw(L)
        tap = ev.get("tap", 99); tapped = t >= tap
        press = 1 - 0.08 * math.sin(math.pi * p_(t, tap, 0.2)) if tapped else 1
        bw, bh = 520, 130; by = 1010
        rrect(ld, [W / 2 - bw / 2, by, W / 2 + bw / 2, by + bh], 65, (GRN if tapped else (0, 149, 246)) + (255,))
        text_c(ld, W / 2, by + bh / 2, "✓ FOLLOWING" if tapped else "FOLLOW", font(FU if tapped else FB, 56), WHITE, "mm")
        F.alpha_composite(scaled(L, out_back(fp) * press, W / 2, by + bh / 2))
        # cursor tap
        cp = p_(t, tap - 0.5, 0.45)
        if 0 < cp and t < tap + 0.6:
            hx = W / 2 + 140 + 200 * (1 - out_cubic(cp)); hy = by + bh / 2 + 40 + 200 * (1 - out_cubic(cp))
            d2 = ImageDraw.Draw(F)
            d2.ellipse([hx - 30, hy - 30, hx + 30, hy + 30], fill=(255, 255, 255, 230))
            if tapped:
                rr = 30 + 90 * p_(t, tap, 0.4)
                d2.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], outline=(255, 255, 255, int(200 * (1 - p_(t, tap, 0.4)))), width=6)
    return wipe_in(F, t, dur, fin=0.3, fout=0.01)
