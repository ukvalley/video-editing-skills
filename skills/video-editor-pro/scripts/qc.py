#!/usr/bin/env python3
"""Quality-check a deliverable against a platform spec.

Usage: python3 qc.py out.mp4 [--platform youtube|shorts|reels|tiktok|linkedin|x|feed|review|broadcast] [--json]

Checks: codec, pixel format, resolution/aspect, fps, duration limit, faststart, integrated loudness, true peak,
black frames, silence at head/tail, audio presence. Exit code 1 if any FAIL.
"""
import argparse
import json
import re
import subprocess
import sys

from _common import media_info, measure_loudness, require

SPECS = {
    "youtube":   {"aspect": "16:9", "min_w": 1920, "fps": [23.976, 24, 25, 29.97, 30, 50, 59.94, 60], "max_dur": 43200, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "shorts":    {"aspect": "9:16", "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 180, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "reels":     {"aspect": "9:16", "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 180, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "tiktok":    {"aspect": "9:16", "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 600, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "feed":      {"aspect": ["4:5", "1:1"], "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 60, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "linkedin":  {"aspect": ["16:9", "4:5", "1:1", "9:16"], "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 600, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "x":         {"aspect": ["16:9", "1:1", "9:16"], "min_w": 1080, "fps": [24, 25, 29.97, 30, 60], "max_dur": 140, "lufs": -14, "tp": -1, "lufs_tol": 1.5},
    "review":    {"aspect": None, "min_w": 1280, "fps": None, "max_dur": None, "lufs": -16, "tp": -1, "lufs_tol": 2.0},
    "broadcast": {"aspect": "16:9", "min_w": 1920, "fps": [25, 29.97], "max_dur": None, "lufs": -23, "tp": -1, "lufs_tol": 1.0},
}


def aspect_name(w, h):
    ar = w / h
    for name, v in (("16:9", 16 / 9), ("9:16", 9 / 16), ("1:1", 1.0), ("4:5", 0.8), ("4:3", 4 / 3), ("2.39:1", 2.39)):
        if abs(ar - v) < 0.02:
            return name
    return f"{ar:.3f}"


def black_frames(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", "blackdetect=d=0.08:pix_th=0.10", "-an", "-f", "null", "-"],
                       text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", p.stderr)]


def edge_silence(path, dur):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "silencedetect=n=-50dB:d=0.3", "-vn", "-f", "null", "-"],
                       text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    head = any(s < 0.05 for s in starts)
    tail = len(starts) > len(ends) or any(e > dur - 0.05 for e in ends)
    return head, tail


def faststart(path):
    with open(path, "rb") as fh:
        head = fh.read(2_000_000)
    mo = head.find(b"moov")
    md = head.find(b"mdat")
    return mo != -1 and (md == -1 or mo < md)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--platform", default="youtube", choices=sorted(SPECS))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    require("ffmpeg")
    spec = SPECS[a.platform]
    info = media_info(a.file)
    results = []

    def add(name, ok, detail, level="FAIL"):
        results.append({"check": name, "status": "PASS" if ok else level, "detail": detail})

    add("video stream", info["has_video"], info["vcodec"])
    add("audio stream", info["has_audio"], info["acodec"], "WARN")
    add("codec h264/hevc", info["vcodec"] in ("h264", "hevc", "prores"), info["vcodec"])
    add("pix_fmt yuv420p", info["pix_fmt"] == "yuv420p" or info["vcodec"] == "prores", info["pix_fmt"], "WARN")
    if info["has_video"]:
        asp = aspect_name(info["width"], info["height"])
        want = spec["aspect"]
        if want:
            wl = want if isinstance(want, list) else [want]
            add("aspect ratio", asp in wl, f"{info['width']}x{info['height']} = {asp}, want {wl}")
        add("resolution", max(info["width"], info["height"]) >= spec["min_w"], f"{info['width']}x{info['height']}", "WARN")
        if spec["fps"]:
            add("frame rate", any(abs(info["fps"] - f) < 0.02 for f in spec["fps"]), f"{info['fps']:.3f}", "WARN")
        if spec["max_dur"]:
            add("duration limit", info["duration"] <= spec["max_dur"], f"{info['duration']:.2f}s (max {spec['max_dur']}s)")
        add("faststart (web playback)", faststart(a.file), "moov before mdat" if faststart(a.file) else "run with -movflags +faststart", "WARN")
        bf = black_frames(a.file)
        add("black frames", len(bf) == 0, ", ".join(f"{s:.2f}-{e:.2f}" for s, e in bf) or "none", "WARN")
    if info["has_audio"]:
        add("sample rate 48k", info["sample_rate"] == 48000, info["sample_rate"], "WARN")
        ld = measure_loudness(a.file) or {}
        il = ld.get("integrated_lufs")
        tp = ld.get("true_peak_dbtp")
        if il is not None:
            add("integrated loudness", abs(il - spec["lufs"]) <= spec["lufs_tol"], f"{il:.1f} LUFS (target {spec['lufs']})")
        if tp is not None:
            add("true peak", tp <= spec["tp"] + 0.1, f"{tp:.1f} dBTP (max {spec['tp']})")
        h, t = edge_silence(a.file, info["duration"])
        add("no silence at head", not h, "silent opening" if h else "ok", "WARN")
        add("no silence at tail", not t, "silent ending" if t else "ok", "WARN")
    fails = [r for r in results if r["status"] == "FAIL"]
    if a.json:
        print(json.dumps({"file": a.file, "platform": a.platform, "results": results, "pass": not fails}, indent=1))
    else:
        print(f"QC {a.file} [{a.platform}]")
        for r in results:
            print(f"  {r['status']:4s}  {r['check']:28s} {r['detail']}")
        print("RESULT:", "FAIL" if fails else "PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
