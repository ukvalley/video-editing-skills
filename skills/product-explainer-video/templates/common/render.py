"""Render the video: graphics frames (parallel) + VO/music/SFX mix -> work/.

    python3 edit/render.py --scale 0.5                  # preview 960x540 (show this before any full render)
    python3 edit/render.py --scale 1                    # full 1920x1080
    python3 edit/render.py --stills 3,12.5,40           # PNG stills at those times -> work/stills/
    python3 edit/render.py --scale 0.5 --only video|audio
    python3 edit/render.py --lang hi                    # vo_lines_hi.json / work/vo_hi/, outputs suffixed _hi
    python3 edit/render.py --scale 1 --fps 25           # TV: native 25p (frames are time-based), outputs suffixed _25p
    python3 edit/render.py --layout 916                 # 9:16 from edit/scenes_916.py, outputs suffixed _916
Music and its mix come from edit/config.json: music, music_db, music_fade [in, out], duck [threshold, ratio, attack, release].
Explainers loop the bed; ads (scenes define MUSIC_OFF) start it at an offset so its drop lands on the logo slam.
Outputs: work/video_<W><suf>.mp4, work/sfx<suf>.wav, work/mix_<W><suf>.mov (video + unmastered mix; deliver.sh masters it).
"""
import argparse, json, os, subprocess, sys, wave
from multiprocessing import Pool
import numpy as np

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("STUDIO_ROOT") or os.path.dirname(os.path.dirname(P))
CFG = json.load(open(f"{P}/edit/config.json"))
ap = argparse.ArgumentParser()
ap.add_argument("--scale", type=float, default=0.5); ap.add_argument("--stills"); ap.add_argument("--only")
ap.add_argument("--jobs", type=int, default=8); ap.add_argument("--lang", default="en"); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--layout", default="169"); ap.add_argument("--music", default=CFG.get("music"))
A = ap.parse_args()
FPS = A.fps
os.environ["TV_LANG"] = A.lang
LSUF = "" if A.lang == "en" else f"_{A.lang}"
SUF = LSUF + ("" if A.fps == 30 else f"_{A.fps}p") + ("" if A.layout == "169" else f"_{A.layout}")
os.environ["TV_LAYOUT"] = "scenes" if A.layout == "169" else f"scenes_{A.layout}"
FF = ["ffmpeg", "-nostdin", "-y", "-v", "error"]


def _init(scale):
    sys.path.insert(0, f"{P}/edit"); sys.path.insert(0, f"{ROOT}/toolkit")
    global SCN, X
    import importlib
    SCN = importlib.import_module(os.environ.get("TV_LAYOUT", "scenes"))
    import explainer as X
    X.init(scale, *getattr(SCN, "CANVAS", (1920, 1080)))


def render_chunk(args):
    i0, i1, out, scale = args
    _init(scale)
    w, h = X.RW, X.RH
    enc = subprocess.Popen(FF + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
                                 "-c:v", "libx264", "-preset", "veryfast" if scale < 1 else "slow", "-crf", "20" if scale < 1 else "14",
                                 "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(i0, i1):
        enc.stdin.write(SCN.frame(i / FPS).convert("RGB").tobytes())
    enc.stdin.close(); enc.wait()


def collect_sfx():
    """run every scene once per 1/10 s to register its SFX (cheap at tiny scale)"""
    _init(0.25)
    t = 0.0
    while t < SCN.DUR:
        getattr(SCN, "sfx_frame", SCN.frame)(t); t += 0.1
    return dict(SCN.SFX)


def build_sfx(sched, dur):
    SR = 48000; buf = np.zeros((int(dur * SR) + SR, 2)); cache = {}
    for (name, t), db in sorted(sched.items(), key=lambda kv: kv[0][1]):
        if t < 0: continue
        if name not in cache:
            a = subprocess.run(FF + ["-i", f"{ROOT}/assets/sfx/{name}.wav", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
            cache[name] = np.frombuffer(a, np.float32).reshape(-1, 2)
        x = cache[name] * 10 ** (db / 20); i = int(t * SR); n = min(len(x), len(buf) - i)
        if n > 0: buf[i:i + n] += x[:n]
    buf = buf[:int(dur * SR)]
    pk = np.max(np.abs(buf)); buf = np.tanh(buf / max(1.0, pk) * 1.0) if pk > 1 else buf
    w = wave.open(f"{P}/work/sfx{SUF}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
    return len(sched)


def mix(video, out, dur):
    """voice chain (studio standard), music bed ducked under voice, SFX; mastered by deliver.sh / normalize_audio.sh afterwards"""
    off = getattr(SCN, "MUSIC_OFF", None)
    ad = off is not None
    mdb = CFG.get("music_db", -13 if ad else -17); fi, fo = CFG.get("music_fade", [0.3, 0.8] if ad else [1.5, 3.5])
    th, ra, at, rl = CFG.get("duck", [0.05, 4, 15, 250] if ad else [0.04, 5, 20, 350])
    fc = (f"[1:a]aresample=48000,highpass=f=90,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3000:t=q:w=1:g=3,"
          f"acompressor=threshold=-24dB:ratio=3:attack=5:release=120:makeup=4,alimiter=limit=0.9,aformat=channel_layouts=stereo,asplit=2[v][vk];"
          f"[2:a]aresample=48000,volume={mdb}dB,afade=t=in:d={fi},afade=t=out:st={dur - fo:.2f}:d={fo}[m];"
          f"[m][vk]sidechaincompress=threshold={th}:ratio={ra}:attack={at}:release={rl}[md];"
          f"[3:a]aresample=48000,volume=0dB[s];"
          f"[v][md][s]amix=inputs=3:normalize=0:duration=first,atrim=0:{dur:.3f}[a]")
    music_in = ["-ss", f"{off:.3f}"] if ad else ["-stream_loop", "-1"]
    subprocess.run(FF + ["-i", video, "-i", f"{P}/work/vo{LSUF}/vo.wav"] + music_in + ["-i", f"{ROOT}/{A.music}", "-i", f"{P}/work/sfx{SUF}.wav",
                         "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "pcm_s16le", "-t", f"{dur:.3f}", out], check=True)


if __name__ == "__main__":
    os.makedirs(f"{P}/work/stills", exist_ok=True)
    if A.stills:
        _init(A.scale)
        for s in A.stills.split(","):
            SCN.frame(float(s)).convert("RGB").save(f"{P}/work/stills/t{float(s):07.2f}{SUF}.png")
        print("stills ->", f"{P}/work/stills"); sys.exit()
    _init(A.scale)
    dur = SCN.DUR; n = int(round(dur * FPS)); W = X.RW
    video = f"{P}/work/video_{W}{SUF}.mp4"
    if A.only != "audio":
        os.makedirs(f"{P}/work/chunks", exist_ok=True)
        k = max(1, A.jobs * 3); edges = [round(n * j / k) for j in range(k + 1)]
        jobs = [(edges[j], edges[j + 1], f"{P}/work/chunks/c{W}{SUF}_{j:03d}.mp4", A.scale) for j in range(k)]
        with Pool(A.jobs) as pool:
            for _ in pool.imap_unordered(render_chunk, jobs): print(".", end="", flush=True)
        print()
        lst = f"{P}/work/chunks/list_{W}{SUF}.txt"
        open(lst, "w").write("".join(f"file '{j[2]}'\n" for j in jobs))
        subprocess.run(FF + ["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video], check=True)
    if A.only != "video":
        print("sfx events:", build_sfx(collect_sfx(), dur))
        mix(video, f"{P}/work/mix_{W}{SUF}.mov", dur)
    print(f"done: {dur:.2f}s, {n} frames, {W}px -> work/mix_{W}{SUF}.mov")
