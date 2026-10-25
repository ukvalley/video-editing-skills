#!/usr/bin/env python3
"""Find burned-in text in an edited master (a freelancer's caption pops, name tags) so the recut can frame it out or cover it.

    python3 detect_baked.py raw/ep.mp4 work/baked.json [--band 700 1000] [--mode yellow,gradient,bright]
                            [--fps 4] [--min 25] [--grad-y 950 1000] [--grad-thr 75] [--sheet work/baked.jpg]

Modes (combine with commas):
  yellow    yellow caption text (R>200, G>170, B<90) inside --band (source y range) — counts ≥ --min pixels per sample
  gradient  the darkened bottom gradient captions often sit on: mean luma of rows --grad-y below --grad-thr (any text colour)
  bright    white text pops: near-white pixels in --band well above the median (opt-in: white clothes/walls give false hits)
Output: [[start, end, mode], …] source seconds, merged when < 0.6 s apart. Review --sheet (one still per span, up to 24).
Then: reframe those pieces (a speaker close-up from the split, or a top-anchored ~1.36× punch-in that crops the band away),
or cover them with your own full-screen card. Re-run on the final render to prove nothing is left (v1 of a real recut
still showed captions at 3 spots that only the gradient mode found).
"""
import argparse, json, subprocess, tempfile
import numpy as np


def scan(src, fps, crop, w, h, fmt):
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-vf", f"fps={fps},{crop},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", fmt, "-"], stdout=subprocess.PIPE)
    ch = 3 if fmt == "rgb24" else 1
    i = 0
    while True:
        b = p.stdout.read(w * h * ch)
        if len(b) < w * h * ch:
            break
        yield i / fps, np.frombuffer(b, np.uint8).reshape(h, w, ch).astype(int)
        i += 1


def merge(hits, gap=0.6, pad=0.25):
    spans = []
    for t in hits:
        if spans and t - spans[-1][1] <= gap:
            spans[-1][1] = t + pad
        else:
            spans.append([t, t + pad])
    return spans


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--band", nargs=2, type=int, default=[700, 1000]); ap.add_argument("--mode", default="yellow,gradient")
    ap.add_argument("--fps", type=float, default=4); ap.add_argument("--min", type=int, default=25)
    ap.add_argument("--grad-y", nargs=2, type=int, default=[950, 1000]); ap.add_argument("--grad-thr", type=float, default=75)
    ap.add_argument("--sheet")
    a = ap.parse_args()
    y0, y1 = a.band
    out = []
    modes = a.mode.split(",")
    if "yellow" in modes or "bright" in modes:
        yel, bri, base = [], [], []
        for t, f in scan(a.src, a.fps, f"crop=iw:{y1 - y0}:0:{y0}", 480, max(8, (y1 - y0) // 4), "rgb24"):
            yel.append((t, int(((f[..., 0] > 200) & (f[..., 1] > 170) & (f[..., 2] < 90)).sum())))
            bri.append((t, int((f.min(2) > 235).sum())))
        if "yellow" in modes:
            out += [s + ["yellow"] for s in merge([t for t, n in yel if n >= a.min])]
        if "bright" in modes:
            med = np.median([n for _, n in bri]) if bri else 0
            out += [s + ["bright"] for s in merge([t for t, n in bri if n >= max(a.min * 3, med * 4 + a.min)])]
    if "gradient" in modes:
        g0, g1 = a.grad_y
        hits = [t for t, f in scan(a.src, a.fps, f"crop=iw:{g1 - g0}:0:{g0}", 480, max(4, (g1 - g0) // 4), "gray")
                if f.mean() < a.grad_thr]
        out += [s + ["gradient"] for s in merge(hits)]
    out.sort()
    out = [[round(s, 2), round(e, 2), m] for s, e, m in out]
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}: {len(out)} spans ({', '.join(f'{m} {sum(1 for x in out if x[2] == m)}' for m in modes)})")
    if a.sheet and out:
        with tempfile.TemporaryDirectory() as td:
            ims = []
            for j, (s, e, m) in enumerate(out[:24]):
                fn = f"{td}/b{j:02d}.jpg"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{(s + e) / 2:.2f}", "-i", a.src, "-frames:v", "1",
                                "-vf", "scale=320:-2", fn], check=True)
                ims.append(fn)
            n = len(ims)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f"{td}/b%02d.jpg", "-vf",
                            f"tile={min(n, 6)}x{(n + 5) // 6}", "-frames:v", "1", a.sheet], check=True)
        print(f"sheet {a.sheet}")


if __name__ == "__main__":
    main()
