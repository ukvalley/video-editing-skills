#!/usr/bin/env python3
"""Remove silences from talking-head footage (jump-cut pass) with natural padding and optional punch-in.

Usage:
  python3 silence_cut.py in.mp4 out.mp4 [--threshold -35] [--min-silence 0.45] [--padding 0.12]
                         [--punch-in 0.04] [--keep-list keep.json] [--dry-run] [--crf 18]

- threshold: dBFS below which audio counts as silence (-30 strict, -40 loose)
- min-silence: only gaps longer than this are removed
- padding: seconds kept on each side of speech so it doesn't feel clipped
- punch-in: alternate every other kept segment with a slight scale (e.g. 0.04 = 4%) so jump cuts read as intentional. 0 = off
- keep-list: write the kept segments as JSON (review/edit, or feed into an EDL)

Micro-fades (8 ms) are applied at every audio join to avoid clicks.
"""
import argparse
import json
import re
import subprocess
import sys

from _common import media_info, require


def detect_silences(path, th, min_d):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
           f"silencedetect=n={th}dB:d={min_d}", "-vn", "-f", "null", "-"]
    p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--threshold", type=float, default=-35)
    ap.add_argument("--min-silence", type=float, default=0.45)
    ap.add_argument("--padding", type=float, default=0.12)
    ap.add_argument("--punch-in", type=float, default=0.0)
    ap.add_argument("--keep-list")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()
    require("ffmpeg")
    info = media_info(a.inp)
    dur = info["duration"]
    sil = detect_silences(a.inp, a.threshold, a.min_silence)
    keep = []
    cur = 0.0
    for s, e in sil:
        e = e if e is not None else dur
        ks, ke = cur, s + a.padding
        if ke - ks > 0.05:
            keep.append([max(0, ks), min(dur, ke)])
        cur = max(cur, e - a.padding)
    if dur - cur > 0.05:
        keep.append([cur, dur])
    # merge overlaps
    merged = []
    for k in keep:
        if merged and k[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], k[1])
        else:
            merged.append(k)
    keep = merged
    kept = sum(k[1] - k[0] for k in keep)
    print(f"source {dur:.2f}s -> kept {kept:.2f}s in {len(keep)} segments (removed {dur - kept:.2f}s)", file=sys.stderr)
    if a.keep_list:
        json.dump({"file": a.inp, "segments": [{"start": round(s, 3), "end": round(e, 3)} for s, e in keep]},
                  open(a.keep_list, "w"), indent=1)
    if a.dry_run or not keep:
        return
    W, H = info["width"], info["height"]
    parts_v, parts_a = [], []
    fc = []
    for i, (s, e) in enumerate(keep):
        vf = f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS"
        if a.punch_in and i % 2 == 1:
            z = 1 + a.punch_in
            vf += f",scale=iw*{z:.4f}:ih*{z:.4f},crop={W}:{H}"
        vf += f",setsar=1[v{i}]"
        af = (f"[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.008,afade=t=out:st={max(0, e - s - 0.008):.4f}:d=0.008[a{i}]")
        fc += [vf, af]
        parts_v.append(f"[v{i}]")
        parts_a.append(f"[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-i", a.inp,
           "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
