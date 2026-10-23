"""Upscale a small flat-colour logo (PNG with alpha) into a crisp large version.
Rebuilds the edges with a smoothed alpha threshold instead of plain resampling, so it stays sharp at full-screen size.
    python3 toolkit/upscale_logo.py assets/brand/logo_src.png assets/brand/logo.png --scale 6
"""
import argparse
from PIL import Image, ImageFilter, ImageChops

ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--scale", type=int, default=6)
a = ap.parse_args()
im = Image.open(a.src).convert("RGBA"); w, h = im.size; S = a.scale; U = S * 2
alpha = im.getchannel("A")
# bleed opaque colours into transparent pixels so edges don't resample towards black
rgb = im.convert("RGB"); mask = alpha.point(lambda v: 255 if v > 245 else 0)
for _ in range(10):
    grown = rgb.filter(ImageFilter.MaxFilter(3)); m2 = mask.filter(ImageFilter.MaxFilter(3))
    rgb = Image.composite(rgb, grown, mask); mask = m2
rgb = rgb.resize((w * S, h * S), Image.LANCZOS)
# alpha: oversample, soften, re-threshold with a steep curve (smooth vector-like contour), downsample for AA
A = alpha.resize((w * U, h * U), Image.BICUBIC).filter(ImageFilter.GaussianBlur(U * 0.35))
A = A.point(lambda v: max(0, min(255, int((v - 118) * 5 + 128))))
A = A.resize((w * S, h * S), Image.LANCZOS)
# keep thin details (dotted trails) that the threshold would erase
thin = alpha.resize((w * U, h * U), Image.BICUBIC).point(lambda v: max(0, min(255, int((v - 40) * 1.8))))
thin = thin.resize((w * S, h * S), Image.LANCZOS)
near = A.point(lambda v: 255 if v > 200 else 0).filter(ImageFilter.MaxFilter(S + 1))  # main shapes + margin
A = Image.composite(A, ImageChops.lighter(A, thin), near)
out = rgb.copy(); out.putalpha(A); out.save(a.out)
print(a.out, out.size)
