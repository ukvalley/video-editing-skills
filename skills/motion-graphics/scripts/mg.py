#!/usr/bin/env python3
"""Minimal, crisp motion-graphics engine (Pillow + numpy → ffmpeg pipe). Copy into a project's edit/ as the starting point
for logo stings, kinetic typography, lower-third packs, animated data, intros/outros and title sequences.

    python3 mg.py demo out.mov [--size 1920x1080] [--fps 30] [--alpha] [--scale 0.5]
    python3 mg.py demo still.png --still 1.2

Your own piece:  from mg import *   then   render(scene_fn, dur, "out.mov", size=(1920,1080), fps=30, alpha=False)
scene_fn(c) draws one frame on c.im (RGBA, full resolution) for time c.t — every value is a pure function of t, so any
frame renders on its own (stills, previews, resumable chunks). Helpers: easing (oc, ob, io, spring), text(), pill(), bar(),
counter(), logo(), stagger(), wipe(). --alpha writes ProRes 4444 with transparency to overlay on footage; else H.264 CRF 14.
"""
import argparse, math, os, subprocess, sys
STUDIO = os.environ.get("VIDEO_STUDIO", os.path.expanduser("~/video-editing"))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(STUDIO, "assets/fonts")
F = {"black": f"{FONTS}/Montserrat-Black.ttf", "xbold": f"{FONTS}/Montserrat-ExtraBold.ttf",
     "anton": f"{FONTS}/Anton-Regular.ttf", "hand": f"{FONTS}/Caveat-VF.ttf", "deva": f"{FONTS}/NotoSansDevanagari-VF.ttf"}
_fc = {}


# ---------- easing (t in 0..1) ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def p(t, t0, d): return clamp((t - t0) / d) if d > 0 else float(t >= t0)          # progress of a beat
def oc(x): return 1 - (1 - x) ** 3                                                  # ease-out cubic (default entrance)
def io(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2               # ease-in-out (camera moves)
def ob(x, s=1.7): return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2              # overshoot (pops, slams)
def spring(x, k=7, damp=5): return 1 - math.exp(-damp * x) * math.cos(k * x) if x > 0 else 0.0
def lerp(a, b, x): return a + (b - a) * x
def stagger(t, t0, i, gap=0.06, d=0.45, ease=oc): return ease(p(t, t0 + i * gap, d))


def font(name, size):
    key = (name, int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(F.get(name, name), int(size))
    return _fc[key]


class Ctx:
    def __init__(self, W, H, t, scale):
        self.W, self.H, self.t, self.s = W, H, t, scale
        self.im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def S(self, v): return v * self.s                                               # design units → pixels

    def paste(self, layer, x, y, alpha=1.0, anchor="mm"):
        if alpha <= 0: return
        if alpha < 1:
            a = layer.getchannel("A").point(lambda v: int(v * alpha)); layer = layer.copy(); layer.putalpha(a)
        w, h = layer.size
        ox = {"l": 0, "m": w / 2, "r": w}[anchor[0]]; oy = {"t": 0, "m": h / 2, "b": h}[anchor[1]]
        self.im.alpha_composite(layer, (int(round(x - ox)), int(round(y - oy))))


def text(c, s, size, fnt="black", fill=(255, 255, 255), track=0, shadow=None, stroke=0, stroke_fill=(0, 0, 0)):
    """Text as an RGBA layer at full res (tracking in px, optional soft shadow for legibility over footage)."""
    f = font(fnt, c.S(size)); tr = c.S(track)
    widths = [f.getbbox(ch)[2] if ch != " " else f.getlength(" ") for ch in s]
    asc, desc = f.getmetrics()
    w = int(sum(widths) + tr * max(0, len(s) - 1) + c.S(stroke) * 2 + 4); h = int(asc + desc + c.S(stroke) * 2 + 4)
    L = Image.new("RGBA", (max(1, w), h), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    x = c.S(stroke)
    if tr == 0:
        d.text((x, c.S(stroke)), s, font=f, fill=fill, stroke_width=int(c.S(stroke)), stroke_fill=stroke_fill)
    else:
        for ch, cw in zip(s, widths):
            d.text((x, c.S(stroke)), ch, font=f, fill=fill, stroke_width=int(c.S(stroke)), stroke_fill=stroke_fill); x += cw + tr
    if shadow:
        sh = Image.new("RGBA", L.size, (0, 0, 0, 0)); sh.putalpha(L.getchannel("A").point(lambda v: int(v * shadow)))
        sh = sh.filter(ImageFilter.GaussianBlur(c.S(10)))
        out = Image.new("RGBA", (L.width, L.height + int(c.S(8))), (0, 0, 0, 0)); out.alpha_composite(sh, (0, int(c.S(8))))
        out.alpha_composite(L); L = out
    return L


def pill(c, w, h, fill, r=None):
    L = Image.new("RGBA", (int(c.S(w)), int(c.S(h))), (0, 0, 0, 0))
    ImageDraw.Draw(L).rounded_rectangle([0, 0, L.width - 1, L.height - 1], radius=int(c.S(r if r is not None else h / 2)), fill=fill)
    return L


def wipe(layer, x):
    """Reveal a layer left→right (x 0..1) — crisp mask, no blur."""
    m = Image.new("L", layer.size, 0); ImageDraw.Draw(m).rectangle([0, 0, int(layer.width * x), layer.height], fill=255)
    out = layer.copy(); out.putalpha(Image.fromarray(np.minimum(np.array(layer.getchannel("A")), np.array(m))))
    return out


def counter(t, t0, d, target, fmt="{:,.0f}"):
    return fmt.format(target * oc(p(t, t0, d)))


def logo(path, height_px):
    im = Image.open(path).convert("RGBA")
    return im.resize((int(im.width * height_px / im.height), int(height_px)), Image.LANCZOS)


def bg_grad(c, top, bottom):
    a = np.linspace(0, 1, c.H)[:, None, None]
    g = (np.array(top)[None, None, :] * (1 - a) + np.array(bottom)[None, None, :] * a).astype(np.uint8)
    c.im.alpha_composite(Image.fromarray(np.repeat(g, c.W, axis=1), "RGB").convert("RGBA"))


# ---------- render ----------
def render(scene, dur, out, size=(1920, 1080), fps=30, alpha=False, scale=1.0, still=None):
    W, H = int(size[0] * scale) // 2 * 2, int(size[1] * scale) // 2 * 2
    if still is not None:
        c = Ctx(W, H, still, W / size[0]); scene(c); c.im.save(out); print(f"wrote {out}"); return
    venc = (["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] if alpha
            else ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p"])
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", *venc, out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(dur * fps))
    for i in range(n):
        c = Ctx(W, H, i / fps, W / size[0]); scene(c)
        if not alpha:
            base = Image.new("RGBA", (W, H), (0, 0, 0, 255)); base.alpha_composite(c.im); c.im = base
        pr.stdin.write(c.im.tobytes())
        if i % fps == 0: print(f"\r{i / fps:.0f}/{dur:.0f}s", end="", flush=True)
    pr.stdin.close(); pr.wait(); print(f"\nwrote {out} ({n} frames)")


# ---------- demo: kinetic title → counter → lower third ----------
def demo(c):
    t = c.t
    bg_grad(c, (14, 14, 18), (30, 24, 40))
    words = ["MAKE", "EVERY", "LEAD", "COUNT"]
    out_k = io(p(t, 2.2, 0.4))
    def row(size):
        return [text(c, w, size, "black", (255, 199, 0) if w == "LEAD" else (255, 255, 255), track=4) for w in words]
    layers, gap = row(130), c.S(40)
    total = sum(L.width for L in layers) + gap * (len(layers) - 1)
    if total > c.W * 0.86:                                                       # always fit inside the title-safe width
        layers = row(130 * c.W * 0.86 / total)
    x = (c.W - sum(L.width for L in layers) - gap * (len(layers) - 1)) / 2      # lay out by measured width, never fixed steps
    for i, L in enumerate(layers):
        k = stagger(t, 0.2, i, gap=0.12, d=0.5, ease=ob)
        c.paste(L, x, c.H * 0.42 + c.S(60) * (1 - k) - c.S(300) * out_k, k * (1 - out_k), "lm")
        x += L.width + gap
    if t > 2.3:
        k = ob(p(t, 2.4, 0.5))
        c.paste(text(c, counter(t, 2.4, 1.2, 12480), 220, "anton", (255, 199, 0)), c.W / 2, c.H * 0.45, k)
        c.paste(text(c, "LEADS FOLLOWED UP", 46, "xbold", (220, 220, 225), track=6), c.W / 2, c.H * 0.6, oc(p(t, 2.7, 0.4)))
    k = oc(p(t, 3.4, 0.5))
    if k > 0:
        bar = pill(c, 640, 120, (255, 199, 0, 255), r=18)
        c.paste(wipe(bar, k), c.S(120), c.H - c.S(200), 1, "lm")
        c.paste(text(c, "Your Name", 50, "black", (12, 12, 14)), c.S(150), c.H - c.S(215), oc(p(t, 3.6, 0.3)), "lm")
        c.paste(text(c, "FOUNDER, YOUR COMPANY", 26, "xbold", (40, 40, 44), track=3), c.S(150), c.H - c.S(165), oc(p(t, 3.7, 0.3)), "lm")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["demo"]); ap.add_argument("out")
    ap.add_argument("--size", default="1920x1080"); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--alpha", action="store_true"); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--still", type=float)
    a = ap.parse_args()
    render(demo, 5.0, a.out, tuple(map(int, a.size.split("x"))), a.fps, a.alpha, a.scale, a.still)
