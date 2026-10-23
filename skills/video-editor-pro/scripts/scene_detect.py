#!/usr/bin/env python3
"""Find shot boundaries and optionally split the file into shots.

Usage:
  python3 scene_detect.py in.mp4 [--threshold 0.35] [--min-shot 0.5] [--out shots.json] [--split shots/]
                                  [--thumbs shots/thumbs]

Output: {"shots": [{"index":0,"start":0.0,"end":4.2,"duration":4.2}, ...]}
--split re-encodes each shot to its own file (frame-accurate). --thumbs saves one JPEG per shot (midpoint).
"""
import argparse
import json
import os
import re
import subprocess
import sys

from _common import media_info, require


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--threshold", type=float, default=0.35)
    ap.add_argument("--min-shot", type=float, default=0.5)
    ap.add_argument("--out")
    ap.add_argument("--split")
    ap.add_argument("--thumbs")
    a = ap.parse_args()
    require("ffmpeg")
    info = media_info(a.file)
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", a.file, "-vf",
           f"select='gt(scene,{a.threshold})',showinfo", "-an", "-f", "null", "-"]
    p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    cuts = [float(m) for m in re.findall(r"pts_time:([\d.]+)", p.stderr)]
    bounds = [0.0]
    for c in cuts:
        if c - bounds[-1] >= a.min_shot:
            bounds.append(c)
    if info["duration"] - bounds[-1] >= 0.05:
        bounds.append(info["duration"])
    shots = [{"index": i, "start": round(bounds[i], 3), "end": round(bounds[i + 1], 3),
              "duration": round(bounds[i + 1] - bounds[i], 3)} for i in range(len(bounds) - 1)]
    res = {"file": a.file, "shots": shots}
    if a.split:
        os.makedirs(a.split, exist_ok=True)
        for s in shots:
            out = os.path.join(a.split, f"shot_{s['index']:03d}.mp4")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.file,
                            "-ss", str(s["start"]), "-to", str(s["end"]), "-c:v", "libx264", "-crf", "16",
                            "-preset", "fast", "-c:a", "aac", "-b:a", "192k", out], check=True)
            s["file"] = out
    if a.thumbs:
        os.makedirs(a.thumbs, exist_ok=True)
        for s in shots:
            mid = (s["start"] + s["end"]) / 2
            out = os.path.join(a.thumbs, f"shot_{s['index']:03d}.jpg")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(mid), "-i", a.file,
                            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "3", out], check=True)
            s["thumb"] = out
    js = json.dumps(res, indent=1)
    if a.out:
        open(a.out, "w").write(js)
        print(f"{len(shots)} shots -> {a.out}", file=sys.stderr)
    else:
        print(js)


if __name__ == "__main__":
    main()
