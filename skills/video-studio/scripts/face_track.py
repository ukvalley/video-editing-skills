#!/usr/bin/env python3
"""Face-follow reframing (e.g. 16:9 podcast → 9:16 short) with Apple Vision; writes a crop timeline for keep_render.py.

    python3 face_track.py raw/ep.mp4 work/crops.json [--aspect 9:16] [--range 600 690] [--sample 4] [--zoom 1.0]
                          [--mode biggest|left|right|both] [--deadzone 0.12] [--hold 0.6] [--sheet work/crops.jpg]

Behaves like a camera operator, not a jittery tracker: the crop stays LOCKED until the subject has been outside the
dead zone (fraction of crop width) for --hold seconds, then it cuts to the new position. That reads as an intentional
reframe and never "floats". No face → hold the last framing.
--mode: biggest face (default) | left/right-most face (follow one person in a 2-up) | both (fit both if they fit, else biggest).
Output: [{"t0", "t1", "crop": [x, y, w, h]}] in SOURCE seconds/pixels. Check it with --sheet (one still per framing).
"""
import argparse, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.expanduser("~/.cache/vstudio/faces")


def faces_bin():
    if not os.path.exists(BIN):
        os.makedirs(os.path.dirname(BIN), exist_ok=True)
        subprocess.run(["swiftc", "-O", os.path.join(HERE, "faces.swift"), "-o", BIN], check=True)
    return BIN


def probe(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", path], capture_output=True, text=True).stdout
    j = json.loads(o)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--aspect", default="9:16"); ap.add_argument("--range", nargs=2, type=float)
    ap.add_argument("--sample", type=float, default=4); ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--mode", default="biggest", choices=["biggest", "left", "right", "both"])
    ap.add_argument("--deadzone", type=float, default=0.12); ap.add_argument("--hold", type=float, default=0.6)
    ap.add_argument("--headroom", type=float, default=0.38, help="face centre this far down the crop (vertical crops only)")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    SW, SH, dur = probe(a.src)
    t0, t1 = a.range or (0.0, dur)
    aw, ah = map(float, a.aspect.split(":"))
    ch = SH / a.zoom
    cw = ch * aw / ah
    if cw > SW:
        cw = SW; ch = cw * ah / aw
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", a.src,
                        "-vf", f"fps={a.sample},scale=640:-2", "-q:v", "4", f"{td}/frame_%05d.jpg"], check=True)
        F = json.loads(subprocess.run([faces_bin(), td], capture_output=True, text=True, check=True).stdout)
    samples = []
    for name in sorted(F):
        t = t0 + (int(name[6:11]) - 1) / a.sample
        fs = [f for f in F[name] if f[4] > 0.5 and f[2] > 0.03]
        if not fs:
            samples.append((t, None)); continue
        if a.mode == "left":
            f = min(fs, key=lambda f: f[0])
        elif a.mode == "right":
            f = max(fs, key=lambda f: f[0])
        else:
            f = max(fs, key=lambda f: f[2] * f[3])
            if a.mode == "both" and len(fs) > 1:
                x0 = min(g[0] for g in fs) * SW; x1 = max(g[0] + g[2] for g in fs) * SW
                if x1 - x0 < cw * 0.9:
                    samples.append((t, ((x0 + x1) / 2, (f[1] + f[3] / 2) * SH))); continue
        samples.append((t, ((f[0] + f[2] / 2) * SW, (f[1] + f[3] / 2) * SH)))

    def place(c):
        x = min(max(c[0] - cw / 2, 0), SW - cw)
        y = min(max(c[1] - ch * a.headroom, 0), SH - ch) if ch < SH else 0
        return [round(x), round(y), round(cw), round(ch)]

    first = next((c for _, c in samples if c), (SW / 2, SH / 2))
    cur, since, out, seg_t0 = first, None, [], t0
    for t, c in samples:
        if c is None:
            since = None; continue
        if abs(c[0] - cur[0]) > a.deadzone * cw or abs(c[1] - cur[1]) > a.deadzone * ch:
            since = since if since is not None else t
            if t - since >= a.hold:
                out.append({"t0": round(seg_t0, 3), "t1": round(since, 3), "crop": place(cur)})
                cur, seg_t0, since = c, since, None
        else:
            since = None
    out.append({"t0": round(seg_t0, 3), "t1": round(t1, 3), "crop": place(cur)})
    out = [o for o in out if o["t1"] - o["t0"] > 0.05]
    json.dump(out, open(a.out, "w"), indent=1)
    found = sum(1 for _, c in samples if c)
    print(f"wrote {a.out}: {len(out)} framings, faces in {found}/{len(samples)} samples, crop {cw:.0f}x{ch:.0f}")
    if a.sheet:
        with tempfile.TemporaryDirectory() as td:
            for i, o in enumerate(out[:24]):
                x, y, w, h = o["crop"]
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str((o["t0"] + o["t1"]) / 2), "-i", a.src, "-frames:v", "1",
                                "-vf", f"crop={w}:{h}:{x}:{y},scale=-2:480", f"{td}/s{i:02d}.jpg"], check=True)
            n = min(len(out), 24)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f"{td}/s%02d.jpg", "-vf",
                            f"tile={min(n, 8)}x{(n + 7) // 8}", "-frames:v", "1", a.sheet], check=True)
        print(f"sheet {a.sheet}")


if __name__ == "__main__":
    main()
