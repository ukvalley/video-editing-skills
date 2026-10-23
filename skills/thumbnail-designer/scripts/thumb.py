#!/usr/bin/env python3
"""YouTube thumbnails + Reels/Shorts covers from a frame or photo, with the studio's bold title style.

    python3 thumb.py --src raw/a.mp4 --at 12.4 --title "3X MORE *CALLS*" --out exports/v1_thumb_youtube_1280x720.jpg
    python3 thumb.py --src photo.jpg --title "STOP *LOSING* LEADS" --sub "IN 30 DAYS" --format cover --logo assets/brand/logo.png
                     --out exports/v1_cover_reels_1080x1920.jpg [--side left|right] [--focus 0.6] [--accent FFC700] [--grade punchy]
    python3 thumb.py ... --variants 3        # writes _a/_b/_c with alternate layouts for A/B (YouTube "Test & compare")

--format youtube (1280x720, text on the side opposite the face, subject cut-out glow) | cover (1080x1920, text kept inside the
centre 1080x1440 = Instagram 3:4 grid crop) | square (1080x1080). *word* = accent colour on a highlight bar.
--at: frame time; omit with a video to auto-pick the sharpest of 24 candidate frames (Laplacian variance).
--focus: horizontal centre of the subject (0..1) for the crop; defaults to the face found by face_track's Vision binary.
"""
import argparse, json, os, re, subprocess, tempfile
STUDIO = os.environ.get("VIDEO_STUDIO", os.path.expanduser("~/video-editing"))
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONTS = os.path.join(STUDIO, "assets/fonts")
BLACK, XBOLD = f"{FONTS}/Montserrat-Black.ttf", f"{FONTS}/Montserrat-ExtraBold.ttf"
FACES = os.path.expanduser("~/.cache/vstudio/faces")
SIZES = {"youtube": (1280, 720), "cover": (1080, 1920), "square": (1080, 1080)}


def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def sharpness(im):
    g = np.asarray(im.convert("L").resize((480, int(480 * im.height / im.width))), np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def grab(src, at, td):
    if src.lower().endswith((".jpg", ".jpeg", ".png", ".heic", ".webp")):
        return Image.open(src).convert("RGB")
    if at is not None:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", f"{td}/f.png"], check=True)
        return Image.open(f"{td}/f.png").convert("RGB")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                               capture_output=True, text=True).stdout)
    best = None
    for i in range(24):
        t = dur * (0.04 + 0.92 * i / 23)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(t), "-i", src, "-frames:v", "1", f"{td}/c.png"], check=True)
        im = Image.open(f"{td}/c.png").convert("RGB"); s = sharpness(im)
        if not best or s > best[0]:
            best = (s, im, t)
    print(f"picked frame at {best[2]:.2f}s (sharpest of 24)")
    return best[1]


def face_x(im, td):
    if not os.path.exists(FACES):
        return None
    os.makedirs(f"{td}/fc", exist_ok=True); im.save(f"{td}/fc/frame_00001.jpg")
    try:
        F = json.loads(subprocess.run([FACES, f"{td}/fc"], capture_output=True, text=True, check=True).stdout)["frame_00001.jpg"]
    except Exception:
        return None
    if not F:
        return None
    f = max(F, key=lambda f: f[2] * f[3])
    return f[0] + f[2] / 2, f[1] + f[3] / 2


def cover_crop(im, W, H, fx, target=0.5, zoom=1.0, fy=0.5):
    """Scale to cover W x H (x zoom) and put the subject (fx, fy) at `target` of the width, as far as the frame allows."""
    s = max(W / im.width, H / im.height) * zoom
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = min(max(int(fx * im.width - target * W), 0), im.width - W)
    y = min(max(int(fy * im.height - 0.42 * H), 0), im.height - H) if zoom > 1 else (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def grade(im, kind):
    if kind == "none":
        return im
    im = ImageEnhance.Contrast(im).enhance(1.18); im = ImageEnhance.Color(im).enhance(1.22)
    im = ImageEnhance.Sharpness(im).enhance(1.6)
    if kind == "punchy":
        im = ImageEnhance.Brightness(im).enhance(1.04)
    return im


def wrap(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t.replace("*", "")) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur]


def draw_title(im, title, box, accent, size, align="left", sub=None):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(im)
    while True:
        f = ImageFont.truetype(BLACK, size)
        lines = wrap(title.upper(), f, x1 - x0)
        lh = int(size * 1.08)
        sub_h = int(size * 0.5) if sub else 0
        if (len(lines) * lh + sub_h <= y1 - y0 and all(f.getlength(l.replace("*", "")) <= x1 - x0 for l in lines)) or size < 40:
            break
        size -= 4
    y = y0 + (y1 - y0 - len(lines) * lh - sub_h) / 2
    for line in lines:
        parts = re.split(r"(\*[^*]+\*)", line)
        lw = sum(f.getlength(p.strip("*")) for p in parts)
        x = x0 if align == "left" else x0 + (x1 - x0 - lw) / 2
        for p in parts:
            if not p:
                continue
            hl, word = p.startswith("*"), p.strip("*")
            w = f.getlength(word)
            if hl:
                pad = size * 0.08
                d.rectangle([x - pad, y + size * 0.1, x + w + pad, y + size * 1.02], fill=accent)
                d.text((x, y), word, font=f, fill=(12, 12, 14))
            else:
                d.text((x, y), word, font=f, fill=(255, 255, 255), stroke_width=max(3, size // 18), stroke_fill=(0, 0, 0))
            x += w
        y += lh
    if sub:
        fs = ImageFont.truetype(XBOLD, int(size * 0.42))
        sw = fs.getlength(sub.upper())
        sx = x0 if align == "left" else x0 + (x1 - x0 - sw) / 2
        d.text((sx, y + size * 0.05), sub.upper(), font=fs, fill=accent, stroke_width=3, stroke_fill=(0, 0, 0))


def make(a, im, variant, out):
    W, H = SIZES[a.format]
    fx, fy = a.focus, a.focus_y
    side = a.side or ("left" if fx >= 0.5 else "right")
    if variant == 1:
        side = "right" if side == "left" else "left"
    if a.format == "youtube":
        # subject on the third away from the text; zoom so a same-aspect frame has room to move (big faces win anyway)
        target = 0.74 if side == "left" else 0.26
        base = grade(cover_crop(im, W, H, fx, target, zoom=1.35, fy=fy), a.grade).convert("RGBA")
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = np.zeros((H, W), np.float32)
        ramp = np.linspace(1, 0, W) if side == "left" else np.linspace(0, 1, W)
        g[:] = np.clip(ramp * 1.6 - 0.35, 0, 1) * 0.82
        sh.putalpha(Image.fromarray((g * 255).astype(np.uint8)))
        base.alpha_composite(sh)
        box = (56, 70, int(W * 0.52), H - 70) if side == "left" else (int(W * 0.48), 70, W - 56, H - 70)
        draw_title(base, a.title, box, a.accent_rgb, 150 if variant != 2 else 118, "left", a.sub)
    else:
        base = grade(cover_crop(im, W, H, fx), a.grade).convert("RGBA")
        safe_top = (H - 1440) // 2 if a.format == "cover" else 0
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = np.zeros((H, W), np.float32)
        top = (fy > 0.45) != (variant == 1)            # text on the half away from the face
        ys = np.linspace(0, 1, H)[:, None]
        g[:] = np.clip(((1 - ys) if top else ys) * 2.2 - 0.9, 0, 1) * 0.85
        sh.putalpha(Image.fromarray((g * 255).astype(np.uint8))); base.alpha_composite(sh)
        # title + logo share the half away from the face (logo on the outer edge of that half)
        if top:
            box = (70, safe_top + 150, W - 70, safe_top + 640)
        else:
            box = (70, safe_top + 1440 - 640, W - 70, safe_top + 1440 - 150)
        draw_title(base, a.title, box, a.accent_rgb, 140 if variant != 2 else 112, "center", a.sub)
    if a.logo:
        lg = Image.open(a.logo).convert("RGBA")
        lh = int(H * (0.075 if a.format == "youtube" else 0.04))
        lg = lg.resize((int(lg.width * lh / lg.height), lh), Image.LANCZOS)
        if a.format == "youtube":
            pos = (W - lg.width - 36, 30) if side == "left" else (36, 30)
        else:
            pos = ((W - lg.width) // 2, (H - 1440) // 2 + 50 if top else (H - 1440) // 2 + 1440 - lh - 50)
        base.alpha_composite(lg, pos)
    base.convert("RGB").save(out, quality=94)
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True); ap.add_argument("--at", type=float)
    ap.add_argument("--title", required=True); ap.add_argument("--sub")
    ap.add_argument("--format", default="youtube", choices=list(SIZES)); ap.add_argument("--out", required=True)
    ap.add_argument("--side", choices=["left", "right"]); ap.add_argument("--focus", type=float)
    ap.add_argument("--accent", default="FFC700"); ap.add_argument("--logo")
    ap.add_argument("--grade", default="punchy", choices=["punchy", "clean", "none"])
    ap.add_argument("--variants", type=int, default=1)
    a = ap.parse_args()
    a.accent_rgb = hexrgb(a.accent)
    with tempfile.TemporaryDirectory() as td:
        im = grab(a.src, a.at, td)
        a.focus_y = 0.4
        if a.focus is None:
            a.focus, a.focus_y = face_x(im, td) or (0.5, 0.4)
    if a.variants == 1:
        make(a, im, 0, a.out)
    else:
        stem, ext = os.path.splitext(a.out)
        for v in range(a.variants):
            make(a, im, v, f"{stem}_{'abc'[v % 3]}{ext}")


if __name__ == "__main__":
    main()
