#!/usr/bin/env python3
"""Shot map of an edited podcast master (e.g. a freelancer's cut): split-screen / single cameras / graphics, as runs.

    python3 classify_shots.py raw/ep.mp4 work/shot_runs.json [--fps 5] [--singles 2] [--sheet work/shots.jpg]
                              [--divider auto|<x px>] [--range 0 600]

Classes:
  S   split-screen (two people side by side, a vertical divider line/hard edge near the middle)
  C0, C1, …  single-camera shots, clustered by look (centre-crop colour) into --singles groups — usually guest vs host.
             Look at --sheet to see which cluster is who, then name them in your EDL.
  X   graphics / title cards / black / flat frames (freelancer infographics, stingers) — never cut to these.
Output: {"divider_x": px, "runs": [[class, start, end], …]} in source seconds. 1-2 sample blips are smoothed away.
Why: a recut of an edited master needs to know where each camera framing lives (close-ups come from the split's halves,
singles get reused for reactions, X spans must be covered by our own cards).
"""
import argparse, json, subprocess, sys
import numpy as np

W, H = 480, 270


def frames(src, fps, rng):
    cmd = ["ffmpeg", "-nostdin", "-v", "error"] + (["-ss", str(rng[0]), "-t", str(rng[1] - rng[0])] if rng else []) + \
          ["-i", src, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)


def divider_score(f):
    """per column in the middle 30-70 %: a divider is a column that is uniform top-to-bottom and differs from its neighbours"""
    g = f.mean(2)
    xs = np.arange(int(W * .3), int(W * .7))
    vstd = g[:, xs].std(0)
    edge = np.abs(g[:, xs + 3] - g[:, xs - 3]).mean(0)
    s = edge - vstd * 0.6
    return xs, s


def kmeans(X, k, it=30):
    rng = np.random.default_rng(0)
    C = X[rng.choice(len(X), k, replace=False)]
    for _ in range(it):
        lab = ((X[:, None, :] - C[None]) ** 2).sum(2).argmin(1)
        C = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
    return lab, C


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=4); ap.add_argument("--singles", type=int, default=2)
    ap.add_argument("--divider", default="auto"); ap.add_argument("--range", nargs=2, type=float)
    ap.add_argument("--sheet")
    a = ap.parse_args()
    t0 = a.range[0] if a.range else 0.0
    feats = []
    for f in frames(a.src, a.fps, a.range):
        g = f.mean(2)
        xs, s = divider_score(f)
        k = int(s.argmax())
        texture = np.abs(np.diff(g, axis=1)).mean()
        centre = f[int(H * .35):int(H * .8), int(W * .3):int(W * .7)]
        white = float((f.min(2) > 215).mean())               # infographics on white/light cards
        feats.append(dict(dx=int(xs[k]), ds=float(s[k]), lum=float(g.mean()), tex=float(texture), white=white,
                          col=np.concatenate([centre.mean((0, 1)), [centre.mean()]]) / 255))
    if not feats:
        sys.exit("no frames decoded")
    ds = np.array([x["ds"] for x in feats])
    if a.divider == "auto":
        strong = [x["dx"] for x in feats if x["ds"] > max(12, np.percentile(ds, 90) * 0.6)]
        dx = int(np.median(strong)) if strong else None
    else:
        dx = int(int(a.divider) * W / 1920)
    cls = []
    for x in feats:
        if x["lum"] < 25 or x["tex"] < 2.0 or x["white"] > 0.5:
            cls.append("X")                                   # black, flat card or white-background infographic
        elif dx is not None and abs(x["dx"] - dx) <= 2 and x["ds"] > 12:
            cls.append("S")
        else:
            cls.append("C")
    idx = [i for i, c in enumerate(cls) if c == "C"]
    if idx and a.singles > 1:
        X = np.array([feats[i]["col"] for i in idx])
        lab, _ = kmeans((X - X.mean(0)) / (X.std(0) + 1e-6), min(a.singles, len(idx)))
        for i, l in zip(idx, lab):
            cls[i] = f"C{l}"
    else:
        cls = ["C0" if c == "C" else c for c in cls]
    for i in range(1, len(cls) - 1):                          # smooth 1-sample blips (dissolves, flashes)
        if cls[i - 1] == cls[i + 1] != cls[i]:
            cls[i] = cls[i - 1]
    runs = []
    for i, c in enumerate(cls):
        t = round(t0 + i / a.fps, 2)
        if runs and runs[-1][0] == c:
            runs[-1][2] = round(t + 1 / a.fps, 2)
        else:
            runs.append([c, t, round(t + 1 / a.fps, 2)])
    out = {"divider_x": round(dx * 1920 / W) if dx is not None else None, "runs": runs}
    json.dump(out, open(a.out, "w"), indent=1)
    tot = {}
    for c, s, e in runs:
        tot[c] = tot.get(c, 0) + e - s
    print(f"wrote {a.out}: {len(runs)} runs, divider x≈{out['divider_x']}, " +
          ", ".join(f"{c} {v:.0f}s" for c, v in sorted(tot.items())))
    if a.sheet:
        picks = {}
        for c, s, e in sorted(runs, key=lambda r: r[1] - r[2]):
            picks.setdefault(c, (s + e) / 2)
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            names = []
            for j, (c, t) in enumerate(sorted(picks.items())):
                fn = f"{td}/s{j}.jpg"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", a.src, "-frames:v", "1", "-vf",
                                f"scale=480:-2,drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:text='{c}':x=12:y=12:"
                                f"fontsize=40:fontcolor=yellow:box=1:boxcolor=black@0.6", fn], check=True)
                names.append(fn)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y"] + sum([["-i", n] for n in names], []) +
                           ["-filter_complex", f"hstack=inputs={len(names)}" if len(names) > 1 else "null", a.sheet], check=True)
        print(f"sheet {a.sheet} (one still per class: name C0/C1 as guest/host)")


if __name__ == "__main__":
    main()
