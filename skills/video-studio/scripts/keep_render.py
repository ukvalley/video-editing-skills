#!/usr/bin/env python3
"""Render a list of KEEP segments from one or more sources into one clean, re-framed video.
Used for podcast filler cuts, long-form → shorts clips, and any "cut list" edit too big for an EDL.

    python3 keep_render.py keeps.json out.mov [--size 1920x1080] [--fps 25] [--crops crops.json] [--preview] [--work work/keeps]

keeps.json: {"src": "raw/ep.mp4", "audio": "work/iso.wav"?, "segments": [
    {"in": 12.30, "out": 18.92},                                   # plain keep
    {"in": 19.05, "out": 25.40, "crop": [960, 0, 960, 1080]},      # x,y,w,h in SOURCE pixels (close-up from a 2-up)
    {"in": 25.40, "out": 31.00, "crop": [...], "zoom": 1.08},      # punch-in about the crop centre
    {"in": 40.0,  "out": 44.0,  "src": "raw/camB.mp4"}             # other angle (same timecode base)
]}
  "audio": optional replacement audio for the whole source timeline (e.g. ElevenLabs-isolated voice), sample-locked to src.
--crops: a face_track.py timeline [{t0,t1,crop:[x,y,w,h]}]; segments without their own crop are split where it changes.

Every segment gets 8 ms audio fades (no clicks at micro-cuts). Intermediates are H.264 CRF 14 + PCM in .mov,
joined with the concat demuxer; output is .mov (H.264 + PCM) — master/normalise it afterwards.
Run heavy jobs as: taskpolicy -b nice -n 19 python3 keep_render.py ...   (the laptop hangs otherwise)
"""
import argparse, json, os, subprocess, sys

FADE = 0.008


def ff(args, quiet=True):
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-y"] + (["-loglevel", "error"] if quiet else []) + args
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit("ffmpeg failed: " + " ".join(cmd))


def probe_size(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    w, h = o.splitlines()[0].split(",")[:2]  # DJI/iPhone files repeat the stream inside a stream group
    return int(w), int(h)


def split_by_crops(segs, crops):
    out = []
    for s in segs:
        if "crop" in s or not crops:
            out.append(s)
            continue
        t = s["in"]
        while t < s["out"] - 1e-3:
            c = next((c for c in crops if c["t0"] <= t < c["t1"]), None)
            end = min(s["out"], c["t1"]) if c else s["out"]
            if c is None:
                nxt = [c["t0"] for c in crops if c["t0"] > t]
                end = min(s["out"], nxt[0]) if nxt else s["out"]
            seg = dict(s, **{"in": t, "out": end})
            if c:
                seg["crop"] = c["crop"]
            if end - t > 0.04:
                out.append(seg)
            t = end
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keeps"); ap.add_argument("out")
    ap.add_argument("--size", default="1920x1080"); ap.add_argument("--fps", type=float, default=25)
    ap.add_argument("--crops"); ap.add_argument("--preview", action="store_true", help="half size, videotoolbox, fast")
    ap.add_argument("--work", default="work/keeps")
    a = ap.parse_args()
    K = json.load(open(a.keeps))
    W, H = map(int, a.size.lower().split("x"))
    if a.preview:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    segs = split_by_crops(K["segments"], json.load(open(a.crops)) if a.crops else None)
    os.makedirs(a.work, exist_ok=True)
    venc = (["-c:v", "h264_videotoolbox", "-b:v", "6M"] if a.preview else ["-c:v", "libx264", "-crf", "14", "-preset", "medium"])
    sizes, parts = {}, []
    for i, s in enumerate(segs):
        src = s.get("src", K["src"])
        sizes.setdefault(src, probe_size(src))
        sw, sh = sizes[src]
        n = max(1, round((s["out"] - s["in"]) * a.fps))   # whole frames: every piece is exactly n/fps long
        d = n / a.fps
        x, y, cw, ch = s.get("crop", [0, 0, sw, sh])
        z = s.get("zoom", 1.0)
        if z != 1.0:
            nw, nh = cw / z, ch / z
            x, y, cw, ch = x + (cw - nw) / 2, y + (ch - nh) / 2, nw, nh
        # fill the output aspect inside the crop box (cover), centred on it
        ar = W / H
        if cw / ch > ar:
            nw = ch * ar; x += (cw - nw) / 2; cw = nw
        else:
            nh = cw / ar; y += (ch - nh) / 2; ch = nh
        x, y = max(0, min(sw - cw, x)), max(0, min(sh - ch, y))
        # fps FIRST: converting 29.97/59.94 sources after the trim added 1-3 frames per piece and the picture drifted
        # 27 s behind the audio over a 14-min podcast. Video is cut to exactly n frames, audio padded/trimmed to n/fps.
        vf = (f"fps={a.fps},crop={int(cw)//2*2}:{int(ch)//2*2}:{int(x)}:{int(y)},scale={W}:{H}:flags=lanczos,"
              f"format=yuv420p,setsar=1")
        af = (f"aresample=48000,apad,atrim=0:{d:.6f},afade=t=in:d={FADE},"
              f"afade=t=out:st={max(0, d - FADE):.6f}:d={FADE}")
        part = os.path.join(a.work, f"k{i:04d}.mov")
        inputs = ["-ss", f"{s['in']:.4f}", "-t", f"{d + 0.2:.4f}", "-i", src]
        amap = "0:a:0"
        if K.get("audio") and "src" not in s:
            inputs += ["-ss", f"{s['in']:.4f}", "-t", f"{d + 0.2:.4f}", "-i", K["audio"]]
            amap = "1:a:0"
        ff(inputs + ["-map", "0:v:0", "-map", amap, "-vf", vf, "-af", af, *venc, "-frames:v", str(n),
                     "-c:a", "pcm_s24le", "-ac", "2", part])
        parts.append(part)
        print(f"\r{i + 1}/{len(segs)} segments", end="", flush=True)
    lst = os.path.join(a.work, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", a.out])
    total = sum(max(1, round((s["out"] - s["in"]) * a.fps)) / a.fps for s in segs)
    # count real video packets (the container's duration field drifts ~12 ms per piece with hardware encodes)
    q = lambda *x: subprocess.run(["ffprobe", "-v", "error", *x, "-of", "csv=p=0", a.out], capture_output=True, text=True).stdout.strip()
    vd = int(q("-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets") or 0) / a.fps
    ad = float(q("-select_streams", "a:0", "-show_entries", "stream=duration") or 0)
    print(f"\nwrote {a.out}: {len(segs)} segments, {total:.2f} s (video {vd:.2f} / audio {ad:.2f})")
    if abs(vd - ad) > 1.5 / a.fps:
        sys.exit(f"A/V length mismatch {vd - ad:+.3f} s — do not use this render")


if __name__ == "__main__":
    main()
