"""Product-ad motion-graphics kinds (SaaS / app promos). Registered into gfx.GFX on import, like gfx_pro.
Each kind: f(t, dur, ev, data) -> RGBA 1080x1920 frame. ev = event times local to the graphic, data = texts/images/colours.
Brand colours come from data["brand"] = {"a": [r,g,b], "b": [r,g,b]} (gradient start/end); defaults are violet->blue.
Overlay kinds keep to the band y ~ 760-1300 (face clear, captions below); full-screen kinds use bg_light() and keep
content above y ~ 1360 so the karaoke captions stay readable.
Images in data are paths relative to the studio root (e.g. assets/brand/<client>/phone_dashboard.png).
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter
import gfx
from gfx import (W, H, FB, FX, FU, NAVY, YEL, RED, GRN, WHITE, font, clip, p_, out_cubic, out_back, in_cubic,
                 rrect, text_c, tick, cross, scaled, env)
from gfx_pro import kind, blank, layer_at, fade, fit_font, in_out

TVA = (104, 60, 236); TVB = (24, 92, 232); INK = (20, 22, 48); MUTE = (120, 126, 160)


def cols(data):
    b = data.get("brand", {})
    return tuple(b.get("a", TVA)), tuple(b.get("b", TVB))


_IM = {}


def img(path):
    if path not in _IM:
        _IM[path] = Image.open(path if os.path.isabs(path) else os.path.join(gfx.ROOT, path)).convert("RGBA")
    return _IM[path]


def fit_h(path, h):
    """image scaled (LANCZOS, cached) to height h"""
    key = (path, int(h))
    if key not in _IM:
        im = img(path); w = int(im.width * h / im.height)
        _IM[key] = im.resize((w, int(h)), Image.LANCZOS)
    return _IM[key]


def fit_w(path, w):
    key = (path, "w", int(w))
    if key not in _IM:
        im = img(path); h = int(im.height * w / im.width)
        _IM[key] = im.resize((int(w), h), Image.LANCZOS)
    return _IM[key]


def grad(w, h, a, b, r=0):
    """horizontal gradient RGBA tile, optional rounded corners"""
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    arr = np.array(a, np.float32) * (1 - x) + np.array(b, np.float32) * x
    arr = np.repeat(arr, h, axis=0)
    im = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    if r:
        m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255); im.putalpha(m)
    return im


def gpill(L, box, a, b, r=None):
    x0, y0, x1, y1 = [int(v) for v in box]
    g = grad(x1 - x0, y1 - y0, a, b, r if r is not None else (y1 - y0) // 2)
    L.alpha_composite(g, (x0, y0))


def soft_shadow(L, box, r, blur=28, alpha=90, off=14):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0 + off, x1, y1 + off], r, fill=(30, 20, 90, alpha))
    L.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


_BGL = {}
PAD = 120


def _bgl_canvas(a, b):
    """light branded canvas: white -> lavender with soft brand glows, crisp dot grid, fine dither (full-res, no upscaling)"""
    key = (a, b)
    if key in _BGL:
        return _BGL[key]
    w, h = W + PAD, H + PAD
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img_ = np.zeros((h, w, 3), np.float32) + np.array((246, 245, 255), np.float32)
    for (cx, cy, r, col, k) in [(160, 260, 900, a, 0.22), (1080, 1500, 1000, b, 0.20), (900, 120, 500, (190, 170, 255), 0.35)]:
        g = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r / 2.2) ** 2)))[..., None] * k
        img_ = img_ * (1 - g) + np.array(col, np.float32) * g
    dots = ((xx % 60) < 4) & ((yy % 60) < 4)
    img_[dots] = img_[dots] * 0.86 + np.array(a, np.float32) * 0.14
    img_ += np.random.default_rng(5).normal(0, 1.2, img_.shape).astype(np.float32)
    _BGL[key] = Image.fromarray(np.clip(img_, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return _BGL[key]


def bg_light(t, data):
    a, b = cols(data)
    ox = int(PAD / 2 + 40 * math.sin(t * 0.5)); oy = int(PAD / 2 + 40 * math.cos(t * 0.45))
    return _bgl_canvas(a, b).crop((ox, oy, ox + W, oy + H))


def wipe(frame, t, dur, fin=0.3, fout=0.25, up=True):
    a = out_cubic(p_(t, 0, fin)); b = in_cubic(p_(t, dur - fout, fout)) if fout > 0.02 else 0
    y = int(H * (1 - a)) - int(H * b)
    out = blank(); out.paste(frame, (0, y), frame); return out


def paste_c(L, im, cx, cy, sc=1.0, alpha=1.0, rot=0):
    if sc <= 0.01 or alpha <= 0:
        return
    if abs(sc - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    L.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def sheen(im, sp):
    """light band sweeping across an RGBA image, sp 0..1"""
    if not 0 < sp < 1:
        return im
    w_, h_ = im.size
    band = Image.new("L", im.size, 0); bd = ImageDraw.Draw(band); x = -200 + (w_ + 400) * in_out(sp)
    bd.polygon([(x, 0), (x + 110, 0), (x + 110 - h_ * 0.4, h_), (x - h_ * 0.4, h_)], fill=150)
    band = ImageChops.multiply(band, im.getchannel("A"))
    out = im.copy(); out.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", im.size, (255, 255, 255)).split(), band)))
    return out


def stamp(L, text, cx, cy, t, t0, col=RED, size=64, rot=-8):
    """rubber-stamp slam: scales down from 1.6x, slight rotation"""
    sp = p_(t, t0, 0.22)
    if sp <= 0:
        return
    f = font(FB, size); tw = f.getlength(text); pad = 28
    S = Image.new("RGBA", (int(tw + pad * 2 + 20), size + pad * 2 + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(S)
    d.rounded_rectangle([10, 10, S.width - 10, S.height - 10], 18, fill=col + (235,), outline=WHITE + (255,), width=6)
    d.text((S.width / 2, S.height / 2), text, font=f, fill=WHITE, anchor="mm")
    paste_c(L, S, cx, cy, 1.6 - 0.6 * out_cubic(sp), clip(sp * 2.5), rot)


def x_badge(d, cx, cy, r, prog):
    if prog <= 0:
        return
    rr = r * out_back(prog)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=RED + (255,)); cross(d, cx, cy, rr * 0.42, WHITE, max(4, int(rr * 0.22)))


def ok_badge(d, cx, cy, r, prog, t, t0):
    if prog <= 0:
        return
    rr = r * out_back(prog)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=GRN + (255,)); tick(d, cx, cy, rr * 0.8, WHITE, p_(t, t0 + 0.08, 0.22), max(4, int(rr * 0.2)))


def phone_glyph(d, cx, cy, s, col):
    """simple smartphone outline icon"""
    d.rounded_rectangle([cx - s * 0.32, cy - s * 0.5, cx + s * 0.32, cy + s * 0.5], int(s * 0.1), outline=col, width=max(3, int(s * 0.08)))
    d.line([cx - s * 0.08, cy + s * 0.36, cx + s * 0.08, cy + s * 0.36], fill=col, width=max(3, int(s * 0.07)))


def overlay_env(L, t, dur, cy):
    e = env(t, dur); sc = 0.86 + 0.14 * out_back(p_(t, 0, 0.35))
    return scaled(L, sc, W / 2, cy, e)


# ---------------------------------------------------------------- pains: rows of time-wasters crossed out, then a stamp
@kind("pains")
def g_pains(t, dur, ev, data):
    a, b = cols(data); rows = data["rows"]; title = data.get("title", "")
    L = blank(); d = ImageDraw.Draw(L)
    y0 = data.get("y0", 780); rh = 104; hh = 100; hgt = hh + 24 + rh * len(rows)
    soft_shadow(L, (90, y0, W - 90, y0 + hgt), 40)
    rrect(d, [90, y0, W - 90, y0 + hgt], 40, (255, 255, 255, 248))
    gpill(L, (90, y0, W - 90, y0 + hh), a, b, 40)
    L.alpha_composite(grad(W - 180, 40, a, b), (90, y0 + hh - 40))   # square off the header's bottom corners
    d = ImageDraw.Draw(L)
    d.text((140, y0 + hh / 2), title, font=fit_font(FB, title, W - 300, 48), fill=WHITE, anchor="lm")
    for k, r in enumerate(rows):
        y = y0 + hh + 16 + k * rh; tk = ev.get(f"r{k}", 0.2 + 0.4 * k); rp = p_(t, tk, 0.3)
        if rp <= 0:
            continue
        dx = 60 * (1 - out_cubic(rp))
        rf = fit_font(FB, r, W - 400, 54)
        d.text((150 + dx, y + rh / 2), r, font=rf, fill=INK + (int(255 * clip(rp * 2)),), anchor="lm")
        # strike + red badge shortly after it appears
        sp = p_(t, tk + 0.35, 0.3)
        if sp > 0:
            sw = rf.getlength(r) * out_cubic(sp)
            d.line([150, y + rh / 2 + 2, 150 + sw, y + rh / 2 + 2], fill=RED + (230,), width=8)
        x_badge(d, W - 170, y + rh / 2, 34, p_(t, tk + 0.35, 0.3))
    if "stamp" in ev:
        stamp(L, data.get("stamp", "ATKI HUI TEAM"), W / 2 + 140, y0 + hgt + 60, t, ev["stamp"], RED, 58, -6)
    return overlay_env(L, t, dur, y0 + hgt / 2)


# ---------------------------------------------------------------- timepie: where the salesperson's day goes
@kind("timepie")
def g_timepie(t, dur, ev, data):
    a, b = cols(data)
    L = blank(); d = ImageDraw.Draw(L)
    y0, y1 = 760, 1290
    soft_shadow(L, (90, y0, W - 90, y1), 44)
    rrect(d, [90, y0, W - 90, y1], 44, NAVY + (245,))
    title = data.get("title", "SALESPERSON KA DIN")
    d.text((W / 2, y0 + 62), title, font=fit_font(FB, title, W - 260, 50), fill=WHITE, anchor="mm")
    cx, cy, R = 300, y0 + 300, 165
    waste = data.get("waste", 0.8)
    dp = out_cubic(p_(t, ev.get("draw", 0.2), 0.9))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(40, 48, 92, 255))
    if dp > 0:
        d.pieslice([cx - R, cy - R, cx + R, cy + R], -90, -90 + 360 * waste * dp, fill=RED + (255,))
    tp = p_(t, ev.get("talk", 99), 0.4)
    if tp > 0:
        rr = R + 18 * math.sin(math.pi * clip(tp * 1.5)) * (1 if tp < 0.67 else 0)
        d.pieslice([cx - rr, cy - rr, cx + rr, cy + rr], -90 + 360 * waste, 270, fill=GRN + (255,))
    d.ellipse([cx - R * 0.56, cy - R * 0.56, cx + R * 0.56, cy + R * 0.56], fill=NAVY + (255,))
    pct = int(round(waste * 100 * dp))
    d.text((cx, cy), f"{pct}%", font=font(FB, 70), fill=WHITE, anchor="mm")
    # legend
    lx = 520
    lp = p_(t, ev.get("admin", 0.6), 0.35)
    if lp > 0:
        d.rounded_rectangle([lx, cy - 120, lx + 40, cy - 80], 10, fill=RED + (int(255 * lp),))
        for i, ln in enumerate(data.get("waste_label", ["ADMIN KAAM", "dialing · excel · follow-up"])):
            d.text((lx + 60, cy - 100 + i * 52), ln, font=font(FB if i == 0 else FX, 42 if i == 0 else 27),
                   fill=(255, 255, 255, int(255 * lp)) if i == 0 else (190, 196, 235, int(255 * lp)), anchor="lm")
    if tp > 0:
        d.rounded_rectangle([lx, cy + 50, lx + 40, cy + 90], 10, fill=GRN + (int(255 * clip(tp * 2)),))
        for i, ln in enumerate(data.get("talk_label", ["CUSTOMER TALK", "sirf thoda sa"])):
            d.text((lx + 60, cy + 70 + i * 52), ln, font=font(FB if i == 0 else FX, 42 if i == 0 else 27),
                   fill=(255, 255, 255, int(255 * clip(tp * 2))) if i == 0 else (190, 196, 235, int(255 * clip(tp * 2))), anchor="lm")
    return overlay_env(L, t, dur, (y0 + y1) / 2)


# ---------------------------------------------------------------- counter: big number with a label, then a question tag
@kind("counter")
def g_counter(t, dur, ev, data):
    a, b = cols(data)
    L = blank(); d = ImageDraw.Draw(L)
    cy = data.get("cy", 1010)
    np_ = p_(t, ev.get("n", 0.1), 0.45)
    if np_ > 0:
        C = blank(); cd = ImageDraw.Draw(C)
        soft_shadow(C, (150, cy - 190, W - 150, cy + 110), 50)
        rrect(cd, [150, cy - 190, W - 150, cy + 110], 50, (255, 255, 255, 248))
        lo, hi = data.get("from", 0), data.get("to", 40)
        v = int(lo + (hi - lo) * out_cubic(np_))
        num = data.get("fmt", "{lo}-{v}").format(lo=data.get("lo", 30), v=v)
        G = blank(); gd = ImageDraw.Draw(G)
        gd.text((W / 2, cy - 70), num, font=font(FB, 190), fill=WHITE, anchor="mm")
        g_ = grad(W, H, a, b); g_.putalpha(G.getchannel("A")); C.alpha_composite(g_)
        phone_glyph(cd, 300, cy + 52, 56, MUTE)
        cd.text((W / 2 + 30, cy + 52), data.get("label", "CALLS / DAY"), font=font(FB, 50), fill=INK, anchor="mm")
        L.alpha_composite(scaled(C, 0.7 + 0.3 * out_back(np_), W / 2, cy, clip(np_ * 3)))
    if "q" in ev:
        qp = p_(t, ev["q"], 0.35)
        if qp > 0:
            Q = blank(); qd = ImageDraw.Draw(Q); q = data.get("q", "ZYADA POSSIBLE?")
            qf = font(FB, 64); qw = qf.getlength(q) + 90
            gpill(Q, (W / 2 - qw / 2, cy + 150, W / 2 + qw / 2, cy + 270), YEL, (255, 160, 0))
            qd.text((W / 2, cy + 210), q, font=qf, fill=NAVY, anchor="mm")
            L.alpha_composite(scaled(Q, 0.6 + 0.4 * out_back(qp), W / 2, cy + 210, clip(qp * 3)))
    return fade(L, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- boost: full-screen, phone + before/after calls bars
@kind("boost")
def g_boost(t, dur, ev, data):
    a, b = cols(data)
    F = bg_light(t, data); d = ImageDraw.Draw(F)
    hp = p_(t, 0.15, 0.4)
    head = data.get("head", "SAME PHONE.")
    if hp > 0:
        L = blank(); ld = ImageDraw.Draw(L)
        ld.text((W / 2, 230), head, font=fit_font(FB, head, W - 160, 92), fill=INK, anchor="mm")
        sub = data.get("sub", "SAME SALESPERSON.")
        ld.text((W / 2, 340), sub, font=fit_font(FB, sub, W - 160, 64), fill=a, anchor="mm")
        F.alpha_composite(scaled(layer_at(L, 0, 30 * (1 - out_cubic(hp))), 1, 0, 0, hp))
    # phone floats in from the left
    pp = p_(t, ev.get("phone", 0.25), 0.55)
    if pp > 0:
        ph = fit_h(data["phone"], 820)
        bob = 10 * math.sin(t * 2.2)
        paste_c(F, ph, 300 - 260 * (1 - out_cubic(pp)), 860 + bob, 1.0, clip(pp * 2))
    # bars: before (grey) vs after (gradient), numbers counting
    base = 1170; top = 520; bx0 = 600; bw = 170; gap = 70
    mx = data.get("after", 150)
    for k, (key, val, lab) in enumerate([("before", data.get("before", 40), data.get("before_label", "PEHLE")),
                                          ("after", data.get("after", 150), data.get("after_label", "WITH US"))]):
        bp = out_cubic(p_(t, ev.get(key, 1.0 + k), 0.7))
        if bp <= 0:
            continue
        x = bx0 + k * (bw + gap); hgt = (base - top) * val / mx * bp
        if k == 0:
            d.rounded_rectangle([x, base - hgt, x + bw, base], 22, fill=(178, 182, 205, 255))
        else:
            gb = grad(bw, max(2, int(hgt)), a, b, 22) if hgt > 4 else None
            if gb: F.alpha_composite(gb, (x, int(base - hgt)))
        v = int(round(val * bp))
        d.text((x + bw / 2, base - hgt - 52), str(v), font=font(FB, 72), fill=INK if k else MUTE, anchor="mm")
        d.text((x + bw / 2, base + 44), lab, font=fit_font(FB, lab, bw + 60, 34), fill=INK if k else MUTE, anchor="mm")
    d.line([bx0 - 20, base, bx0 + 2 * bw + gap + 20, base], fill=(200, 200, 225), width=4)
    if "x" in ev:
        xp = p_(t, ev["x"], 0.35)
        if xp > 0:
            B = blank(); bd = ImageDraw.Draw(B); txt = data.get("badge", "3.75X CALLS")
            bf = font(FB, 60); bw2 = bf.getlength(txt) + 100
            gpill(B, (W / 2 - bw2 / 2, 1255, W / 2 + bw2 / 2, 1365), a, b)
            bd.text((W / 2, 1310), txt, font=bf, fill=WHITE, anchor="mm")
            F.alpha_composite(scaled(B, 0.5 + 0.5 * out_back(xp), W / 2, 1310, clip(xp * 3)))
    return wipe(F, t, dur, 0.3, 0.25)


# ---------------------------------------------------------------- logo_reveal: full-screen brand reveal
@kind("logo_reveal")
def g_logo_reveal(t, dur, ev, data):
    F = bg_light(t, data); a, b = cols(data)
    mark = fit_h(data["mark"], 430); word = fit_w(data["word"], 860)
    mp = p_(t, 0.05, 0.5)
    if mp > 0:
        m_ = sheen(mark, p_(t, 0.55, 0.6))
        paste_c(F, m_, W / 2, 700, 0.4 + 0.6 * out_back(mp), clip(mp * 2.5))
    wp = p_(t, 0.3, 0.45)
    if wp > 0:
        paste_c(F, word, W / 2, 1090 + 40 * (1 - out_cubic(wp)), 1.0, wp)
    # expanding ring
    rp = p_(t, 0.1, 0.7)
    if 0 < rp < 1:
        d = ImageDraw.Draw(F); r = 200 + 520 * out_cubic(rp)
        d.ellipse([W / 2 - r, 700 - r, W / 2 + r, 700 + r], outline=a + (int(150 * (1 - rp)),), width=8)
    return fade(F, 1 - in_cubic(p_(t, dur - 0.2, 0.2)))


# ---------------------------------------------------------------- features: phone carousel + feature pills on spoken words
def pill_icon(d, cx, cy, ic, col):
    if ic == "rec":
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=RED + (255,))
    elif ic == "dash":
        for k, hh in enumerate([12, 22, 32]):
            d.rounded_rectangle([cx - 18 + k * 13, cy + 16 - hh, cx - 8 + k * 13, cy + 16], 3, fill=col)
    else:
        d.text((cx, cy), ic, font=font(FU, 36), fill=col, anchor="mm")


@kind("features")
def g_features(t, dur, ev, data):
    a, b = cols(data)
    F = bg_light(t, data); d = ImageDraw.Draw(F)
    feats = data["features"]                # [{"label", "icon", "screen"}]
    times = [ev[f"f{k}"] for k in range(len(feats))]
    merge = ev.get("merge", 99)
    # phone: shows the screen of the latest feature, slide-swaps between screens
    cur = max([k for k, tt in enumerate(times) if t >= tt - 0.1] or [0])
    scr = feats[cur]["screen"]; prev = feats[max(0, cur - 1)]["screen"]
    sp = p_(t, times[cur] - 0.1, 0.35) if cur else 1
    ph_h = 900; cx, cy = W / 2, 760
    enter = out_back(p_(t, 0, 0.45))
    mp = p_(t, merge, 0.45)
    pulse = 1 + 0.05 * math.sin(math.pi * clip(p_(t, merge + 0.35, 0.35)))
    if prev != scr and sp < 1:
        paste_c(F, fit_h(prev, ph_h), cx - 700 * out_cubic(sp), cy, 0.85 + 0.15 * enter, 1 - sp)
        paste_c(F, fit_h(scr, ph_h), cx + 700 * (1 - out_cubic(sp)), cy, (0.85 + 0.15 * enter) * pulse, sp)
    else:
        paste_c(F, fit_h(scr, ph_h), cx, cy + 300 * (1 - enter), (0.85 + 0.15 * enter) * pulse, clip(p_(t, 0, 0.3) * 2))
    # pills alternate left / right around the phone, stacked
    slots = [(250, 420), (830, 560), (250, 740), (830, 900), (250, 1060), (830, 1200)]
    for k, f in enumerate(feats):
        fp = p_(t, times[k], 0.35)
        if fp <= 0:
            continue
        sx, sy = slots[k % len(slots)]
        if mp > 0:      # fly into the phone
            q = in_out(mp); sx = sx + (cx - sx) * q; sy = sy + (cy - sy) * q
        alpha = clip(fp * 3) * (1 - clip(mp * 1.3))
        if alpha <= 0:
            continue
        P = Image.new("RGBA", (440, 120), (0, 0, 0, 0)); pd = ImageDraw.Draw(P)
        lab = f["label"]; lf = fit_font(FB, lab, 300, 40)
        pw = int(lf.getlength(lab) + 130)
        x0 = (440 - pw) // 2
        sh = Image.new("RGBA", P.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([x0, 22, x0 + pw, 110], 44, fill=(40, 20, 120, 80))
        P.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
        on = k == cur and t < merge
        if on:
            gpill(P, (x0, 12, x0 + pw, 100), a, b, 44)
        else:
            pd.rounded_rectangle([x0, 12, x0 + pw, 100], 44, fill=(255, 255, 255, 250), outline=a + (90,), width=3)
        pd.ellipse([x0 + 14, 22, x0 + 82, 90], fill=(255, 255, 255, 255) if on else a + (30,))
        pill_icon(pd, x0 + 48, 56, f.get("icon", "✓"), a + (255,))
        pd.text((x0 + 98, 56), lab, font=lf, fill=WHITE if on else INK, anchor="lm")
        paste_c(F, P, sx, sy, (0.5 + 0.5 * out_back(fp)) * (1 - 0.5 * clip(mp)), alpha)
    # merge banner
    if mp > 0:
        B = blank(); bd = ImageDraw.Draw(B); txt = data.get("merge_text", "EK HI MOBILE MEIN")
        bf = fit_font(FB, txt, W - 220, 72); bw = bf.getlength(txt) + 110
        gpill(B, (W / 2 - bw / 2, 1185, W / 2 + bw / 2, 1300), a, b)
        bd.text((W / 2, 1242), txt, font=bf, fill=WHITE, anchor="mm")
        F.alpha_composite(scaled(B, 0.6 + 0.4 * out_back(p_(t, merge + 0.25, 0.4)), W / 2, 1242, clip(p_(t, merge + 0.25, 0.3) * 3)))
    return wipe(F, t, dur, 0.3, 0.25)


# ---------------------------------------------------------------- workflow: numbered steps connected by a drawing line
@kind("workflow")
def g_workflow(t, dur, ev, data):
    a, b = cols(data); steps = data["steps"]
    L = blank(); d = ImageDraw.Draw(L)
    y0, y1 = 800, 1270
    soft_shadow(L, (70, y0, W - 70, y1), 44)
    rrect(d, [70, y0, W - 70, y1], 44, (255, 255, 255, 248))
    title = data.get("title", "ONE APP = COMPLETE WORKFLOW")
    d.text((W / 2, y0 + 70), title, font=fit_font(FB, title, W - 220, 50), fill=INK, anchor="mm")
    n = len(steps); x0, x1 = 170, W - 170; cy = y0 + 250
    xs = [x0 + (x1 - x0) * k / (n - 1) for k in range(n)]
    ts = [ev.get(f"s{k}", 0.2 + 0.25 * k) for k in range(n)]
    # line drawing between steps
    lp = p_(t, ts[0], ts[-1] - ts[0] + 0.01)
    d.line([x0, cy, x1, cy], fill=(225, 226, 240), width=10)
    G = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(G).line([x0, cy, x0 + (x1 - x0) * lp, cy], fill=WHITE, width=10)
    gg = grad(W, H, a, b); gg.putalpha(G.getchannel("A")); L.alpha_composite(gg); d = ImageDraw.Draw(L)
    for k, (s, x) in enumerate(zip(steps, xs)):
        sp = p_(t, ts[k], 0.3)
        r = 62 * (out_back(sp) if sp > 0 else 0)
        if r > 1:
            C = blank(); gpill(C, (x - r, cy - r, x + r, cy + r), a, b, int(r)); L.alpha_composite(C); d = ImageDraw.Draw(L)
            if k == n - 1:
                tick(d, x, cy, r * 0.8, WHITE, p_(t, ts[k] + 0.1, 0.25), 9)
            else:
                d.text((x, cy), str(k + 1), font=font(FB, int(54 * r / 62) + 1), fill=WHITE, anchor="mm")
        if sp > 0:
            lab = s; lf = fit_font(FB, lab, 190, 30)
            d.text((x, cy + 110), lab, font=lf, fill=INK + (int(255 * clip(sp * 2)),), anchor="mm")
    return overlay_env(L, t, dur, (y0 + y1) / 2)


# ---------------------------------------------------------------- noskip: a chip, then an ad "Skip" button gets X'd
@kind("noskip")
def g_noskip(t, dur, ev, data):
    a, b = cols(data)
    L = blank(); d = ImageDraw.Draw(L)
    cp = p_(t, ev.get("chip", 0.1), 0.35)
    if cp > 0:
        C = blank(); cd = ImageDraw.Draw(C); txt = data.get("chip", "MANUAL DIALING?")
        cf = font(FB, 58); cw = cf.getlength(txt) + 170
        soft_shadow(C, (W / 2 - cw / 2, 820, W / 2 + cw / 2, 940), 60)
        rrect(cd, [W / 2 - cw / 2, 820, W / 2 + cw / 2, 940], 60, NAVY + (245,))
        phone_glyph(cd, W / 2 - cw / 2 + 70, 880, 58, YEL)
        cd.text((W / 2 + 40, 880), txt, font=cf, fill=WHITE, anchor="mm")
        L.alpha_composite(scaled(C, 0.6 + 0.4 * out_back(cp), W / 2, 880, clip(cp * 3)))
    sp = p_(t, ev.get("skip", 99), 0.3)
    if sp > 0:
        S = blank(); sd = ImageDraw.Draw(S)
        bx0, by0, bx1, by1 = 300, 1000, 780, 1130
        shake = 10 * math.sin(t * 60) * (1 - clip(p_(t, ev.get("x", 99), 0.3))) if t >= ev.get("x", 99) else 0
        rrect(sd, [bx0 + shake, by0, bx1 + shake, by1], 18, (20, 20, 24, 225))
        sd.text(((bx0 + bx1) / 2 + shake - 20, (by0 + by1) / 2), "Skip Ad  ▶|", font=font(FU, 54), fill=WHITE, anchor="mm")
        xp = p_(t, ev.get("x", 99), 0.25)
        if xp > 0:
            sd.line([bx0 - 20, by0 - 10, bx0 - 20 + (bx1 - bx0 + 40) * out_cubic(xp), by0 - 10 + (by1 - by0 + 20) * out_cubic(xp)], fill=RED + (255,), width=16)
            sd.line([bx1 + 20, by0 - 10, bx1 + 20 - (bx1 - bx0 + 40) * out_cubic(xp), by0 - 10 + (by1 - by0 + 20) * out_cubic(xp)], fill=RED + (255,), width=16)
        L.alpha_composite(scaled(S, 0.7 + 0.3 * out_back(sp), W / 2, (by0 + by1) / 2, clip(sp * 3)))
        if "x" in ev:
            stamp(L, data.get("stamp", "MAT KARO!"), W / 2 + 170, by1 + 75, t, ev["x"] + 0.15, RED, 56, -6)
    return fade(L, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- learnmore: ad CTA bar slides up, arrow, cursor tap
@kind("learnmore")
def g_learnmore(t, dur, ev, data):
    a, b = cols(data)
    L = blank(); d = ImageDraw.Draw(L)
    bp = p_(t, ev.get("bar", 0.1), 0.4)
    by = 1110; bh = 150; bx0, bx1 = 110, W - 110
    tap = ev.get("tap", 99); tapped = t >= tap
    if bp > 0:
        B = blank(); bd = ImageDraw.Draw(B)
        soft_shadow(B, (bx0, by, bx1, by + bh), 40, 30, 120)
        press = 1 - 0.06 * math.sin(math.pi * p_(t, tap, 0.22)) if tapped else 1
        if tapped:
            gpill(B, (bx0, by, bx1, by + bh), (46, 204, 113), (30, 170, 95), 40)
        else:
            gpill(B, (bx0, by, bx1, by + bh), a, b, 40)
        lab = data.get("label", "Learn More")
        bd.text((bx0 + 70, by + bh / 2), lab, font=font(FB, 64), fill=WHITE, anchor="lm")
        bd.text((bx1 - 70, by + bh / 2), "›", font=font(FB, 96), fill=WHITE, anchor="rm")
        B = scaled(B, press, W / 2, by + bh / 2)
        L.alpha_composite(layer_at(B, 0, 260 * (1 - out_cubic(bp))) if bp < 1 else B)
        # bouncing arrow + "NEECHE" tag above the bar
        ap = p_(t, ev.get("bar", 0.1) + 0.3, 0.3)
        if ap > 0 and not tapped:
            bounce = 18 * abs(math.sin(t * 6))
            d.text((W / 2, by - 150 + bounce), "↓", font=font(FU, 110), fill=YEL + (int(255 * ap),), anchor="mm")
            tag = data.get("tag", "NEECHE CLICK KARO")
            tf = font(FB, 44); tw = tf.getlength(tag) + 60
            rrect(d, [W / 2 - tw / 2, by - 300, W / 2 + tw / 2, by - 225], 36, NAVY + (int(235 * ap),))
            d.text((W / 2, by - 262), tag, font=tf, fill=(255, 255, 255, int(255 * ap)), anchor="mm")
    # cursor tap
    cp = p_(t, tap - 0.5, 0.45)
    if 0 < cp and t < tap + 0.7:
        hx = W / 2 + 160 + 220 * (1 - out_cubic(cp)); hy = by + bh / 2 + 30 + 220 * (1 - out_cubic(cp))
        d.ellipse([hx - 32, hy - 32, hx + 32, hy + 32], fill=(255, 255, 255, 235), outline=(0, 0, 0, 60), width=3)
        if tapped:
            rr = 32 + 100 * p_(t, tap, 0.45)
            d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], outline=(255, 255, 255, int(220 * (1 - p_(t, tap, 0.45)))), width=7)
    return fade(L, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- tagchip: small branded chip (e.g. "PART 2: FULL DEMO")
@kind("tagchip")
def g_tagchip(t, dur, ev, data):
    a, b = cols(data)
    L = blank(); d = ImageDraw.Draw(L)
    cp = p_(t, ev.get("in", 0.1), 0.35); y = data.get("y", 1000)
    if cp > 0:
        C = blank(); cd = ImageDraw.Draw(C)
        top = data.get("top", "AGLE VIDEO MEIN"); txt = data.get("text", "PART 2: FULL DEMO")
        f1 = font(FB, 38); f2 = font(FB, 66); w_ = max(f1.getlength(top), f2.getlength(txt) + 90) + 120
        soft_shadow(C, (W / 2 - w_ / 2, y, W / 2 + w_ / 2, y + 200), 44)
        rrect(cd, [W / 2 - w_ / 2, y, W / 2 + w_ / 2, y + 200], 44, (255, 255, 255, 248))
        cd.text((W / 2, y + 50), top, font=f1, fill=MUTE, anchor="mm")
        G = blank(); gd = ImageDraw.Draw(G)
        gd.text((W / 2 + 45, y + 128), txt, font=f2, fill=WHITE, anchor="mm")
        g_ = grad(W, H, a, b); g_.putalpha(G.getchannel("A")); C.alpha_composite(g_)
        tx = W / 2 + 45 - f2.getlength(txt) / 2 - 70
        gpill(C, (tx - 34, y + 94, tx + 34, y + 162), a, b, 34)
        cd.polygon([(tx - 10, y + 110), (tx - 10, y + 146), (tx + 18, y + 128)], fill=WHITE)
        L.alpha_composite(scaled(C, 0.6 + 0.4 * out_back(cp), W / 2, y + 100, clip(cp * 3)))
    return fade(L, 1 - in_cubic(p_(t, dur - 0.22, 0.22)))


# ---------------------------------------------------------------- endcard_light: brand end card with CTA button + tap
@kind("endcard_light")
def g_endcard_light(t, dur, ev, data):
    a, b = cols(data)
    F = bg_light(t, data); d = ImageDraw.Draw(F)
    lp = p_(t, 0.15, 0.5)
    if lp > 0:
        logo = sheen(fit_w(data["logo"], 900), p_(t, 0.8, 0.7))
        paste_c(F, logo, W / 2, 620, 0.6 + 0.4 * out_back(lp), clip(lp * 2.5))
    sp = p_(t, 0.45, 0.4)
    if sp > 0:
        L = blank(); ld = ImageDraw.Draw(L)
        for i, ln in enumerate(data.get("lines", [])):
            ld.text((W / 2, 880 + i * 74), ln, font=fit_font(FB if i == 0 else FX, ln, W - 160, 56 if i == 0 else 42),
                    fill=INK if i == 0 else MUTE, anchor="mm")
        F.alpha_composite(scaled(layer_at(L, 0, 30 * (1 - out_cubic(sp))), 1, 0, 0, sp))
    bp = p_(t, ev.get("button", 0.7), 0.35)
    if bp > 0:
        B = blank(); bd = ImageDraw.Draw(B)
        tap = ev.get("tap", 99); tapped = t >= tap
        press = 1 - 0.07 * math.sin(math.pi * p_(t, tap, 0.2)) if tapped else 1
        bw, bh, by = 600, 140, 1110
        soft_shadow(B, (W / 2 - bw / 2, by, W / 2 + bw / 2, by + bh), 70, 26, 110)
        gpill(B, (W / 2 - bw / 2, by, W / 2 + bw / 2, by + bh), *(((46, 204, 113), (30, 170, 95)) if tapped else (a, b)))
        lab = data.get("button", "LEARN MORE")
        bd.text((W / 2, by + bh / 2), ("✓ " if tapped else "") + lab, font=font(FU if tapped else FB, 60), fill=WHITE, anchor="mm")
        F.alpha_composite(scaled(B, out_back(bp) * press, W / 2, by + bh / 2))
        cp = p_(t, tap - 0.5, 0.45)
        if 0 < cp and t < tap + 0.7:
            hx = W / 2 + 150 + 200 * (1 - out_cubic(cp)); hy = by + bh / 2 + 40 + 200 * (1 - out_cubic(cp))
            d.ellipse([hx - 30, hy - 30, hx + 30, hy + 30], fill=(255, 255, 255, 240), outline=(0, 0, 0, 70), width=3)
            if tapped:
                rr = 30 + 90 * p_(t, tap, 0.4)
                d.ellipse([hx - rr, hy - rr, hx + rr, hy + rr], outline=a + (int(200 * (1 - p_(t, tap, 0.4))),), width=6)
    return wipe(F, t, dur, 0.3, 0.01)
