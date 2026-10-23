#!/usr/bin/env python3
"""Analyse media files: streams, loudness, scene cuts, silences. Prints JSON.

Usage:
  python3 probe.py file1.mp4 [file2.mov ...] [--scenes] [--silence] [--loudness] [--all] [--scene-th 0.35]
                              [--silence-db -35] [--min-silence 0.5] [--out report.json]

Defaults to --all. Use the output to conform sources (fps/size mismatch), pick cut points and judge audio.
"""
import argparse
import json
import re
import subprocess
import sys

from _common import media_info, measure_loudness, require


def scene_cuts(path, th=0.35):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf",
           f"select='gt(scene,{th})',showinfo", "-an", "-f", "null", "-"]
    p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    times = [float(m) for m in re.findall(r"pts_time:([\d.]+)", p.stderr)]
    return [round(t, 3) for t in times]


def silences(path, db=-35, min_d=0.5):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
           f"silencedetect=n={db}dB:d={min_d}", "-vn", "-f", "null", "-"]
    p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        out.append({"start": round(s, 3), "end": round(e, 3) if e else None,
                    "duration": round(e - s, 3) if e else None})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scenes", action="store_true")
    ap.add_argument("--silence", action="store_true")
    ap.add_argument("--loudness", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scene-th", type=float, default=0.35)
    ap.add_argument("--silence-db", type=float, default=-35)
    ap.add_argument("--min-silence", type=float, default=0.5)
    ap.add_argument("--out")
    a = ap.parse_args()
    require("ffmpeg")
    if not (a.scenes or a.silence or a.loudness):
        a.all = True
    report = []
    for f in a.files:
        try:
            info = media_info(f)
        except Exception as e:  # noqa
            report.append({"path": f, "error": str(e)})
            continue
        if info["has_video"] and (a.all or a.scenes):
            info["scene_cuts"] = scene_cuts(f, a.scene_th)
        if info["has_audio"] and (a.all or a.silence):
            info["silences"] = silences(f, a.silence_db, a.min_silence)
        if info["has_audio"] and (a.all or a.loudness):
            info["loudness"] = measure_loudness(f)
        # quick verdicts an editor cares about
        notes = []
        if info["fps"] and abs(info["fps"] - round(info["fps"])) > 0.01 and abs(info["fps"] - 29.97) > 0.01 and abs(info["fps"] - 23.976) > 0.01 and abs(info["fps"] - 59.94) > 0.01:
            notes.append(f"unusual/variable fps {info['fps']:.3f} — conform with fps= and -fps_mode cfr")
        if info["sample_rate"] and info["sample_rate"] != 48000:
            notes.append(f"audio {info['sample_rate']} Hz — resample to 48000")
        if info["pix_fmt"] and info["pix_fmt"] not in ("yuv420p",):
            notes.append(f"pix_fmt {info['pix_fmt']} — convert to yuv420p for delivery")
        if info.get("loudness") and info["loudness"].get("integrated_lufs") is not None:
            il = info["loudness"]["integrated_lufs"]
            if il < -30:
                notes.append("very quiet audio — check gain / mic")
            if info["loudness"].get("true_peak_dbtp", -99) > -0.5:
                notes.append("audio peaks near 0 dBTP — likely clipping")
        if info["width"] and info["height"]:
            ar = info["width"] / info["height"]
            info["aspect"] = "16:9" if abs(ar - 16 / 9) < 0.02 else "9:16" if abs(ar - 9 / 16) < 0.02 else "1:1" if abs(ar - 1) < 0.02 else "4:5" if abs(ar - 0.8) < 0.02 else f"{ar:.3f}"
        info["notes"] = notes
        report.append(info)
    js = json.dumps(report if len(report) > 1 else report[0], indent=2)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(js)
        print(f"wrote {a.out}", file=sys.stderr)
    print(js)


if __name__ == "__main__":
    main()
