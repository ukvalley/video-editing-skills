"""Voiceover from edit/vo_lines.json -> work/vo/vo.wav + work/vo/timeline.json (scene spans + word times).

    python3 edit/make_vo.py say      # scratch VO with macOS `say` (word times estimated from character length)
    python3 edit/make_vo.py eleven   # ElevenLabs (needs ELEVENLABS_API_KEY in ~/video-editing/.env); exact word times
    python3 edit/make_vo.py eleven hi   # Hinglish: edit/vo_lines_hi.json -> work/vo_hi/   (any <lang>: vo_lines_<lang>.json)

vo_lines keys: voice {eleven_id, eleven_model, say_voice, say_rate, speed?, settings?}, gap, total? (fixed-length spot,
e.g. 30.0: the end card is padded to exactly that length and the script fails if the VO runs over), pronounce?
({"Acme": "Ack me"}: applied to lines without their own "say"), scenes [{id, pre, post, gap?, lines}].
A line is a string or {text, say?, head?}: text = on-screen words / animation anchors, say = what the voice reads.
ElevenLabs output is mp3_44100_128 (works on the Starter plan; 192k needs Creator). Lines are cached in work/vo/<backend>/,
so re-running after a script edit only pays for the changed lines.

On-screen words (text / head) are timed by matching them to the spoken words (exact where the same word is spoken,
interpolated between matches otherwise), so Devanagari "say" text can drive Roman on-screen text.

Each line is rendered separately (cached by text+backend), trimmed, and laid out with scene pre/post pads and a gap
between lines, so the timeline is fully determined by this file and the line audio.
"""
import base64, hashlib, json, os, re, subprocess, sys, wave
import numpy as np

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("STUDIO_ROOT") or os.path.dirname(os.path.dirname(P))
SR = 48000
backend = sys.argv[1] if len(sys.argv) > 1 else "say"
LANG = sys.argv[2] if len(sys.argv) > 2 else "en"
SUF = "" if LANG == "en" else f"_{LANG}"
cfg = json.load(open(f"{P}/edit/vo_lines{SUF}.json"))
V = cfg["voice"]
OUT = f"{P}/work/vo{SUF}"; CACHE = f"{P}/work/vo/{backend}"; os.makedirs(CACHE, exist_ok=True); os.makedirs(OUT, exist_ok=True)


def load_env():
    for ln in open(f"{ROOT}/.env"):
        if "=" in ln:
            k, v = ln.strip().split("=", 1); os.environ.setdefault(k, v)


def read_wav(path):
    a = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(a, np.float32).copy()


def trim(x, thr=0.01):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx): return x, 0.0
    s = max(0, idx[0] - int(0.02 * SR)); e = min(len(x), idx[-1] + int(0.06 * SR))
    return x[s:e], s / SR


def est_words(text, dur):
    """word times spread over the line by character weight (scratch VO only)"""
    ws = text.split(); wts = [len(w) + 2 for w in ws]; tot = sum(wts); t = 0.0; out = []
    for w, k in zip(ws, wts):
        d = dur * k / tot; out.append({"w": w, "s": round(t, 3), "e": round(t + d * 0.9, 3)}); t += d
    return out


def line_say(text, say):
    key = hashlib.md5(f"{V['say_voice']}{V['say_rate']}{say}".encode()).hexdigest()[:10]
    aiff = f"{CACHE}/{key}.aiff"
    if not os.path.exists(aiff):
        subprocess.run(["say", "-v", V["say_voice"], "-r", str(V["say_rate"]), "-o", aiff, say], check=True)
    x, _ = trim(read_wav(aiff))
    return x, est_words(say, len(x) / SR)


def line_eleven(text, say):
    vs = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3, "use_speaker_boost": True, **V.get("settings", {}), "speed": V.get("speed", 1.0)}
    key = hashlib.md5(f"{V['eleven_id']}{V['eleven_model']}{json.dumps(vs, sort_keys=True)}{say}".encode()).hexdigest()[:10]
    js = f"{CACHE}/{key}.json"
    if not os.path.exists(js):
        load_env()
        body = json.dumps({"text": say, "model_id": V["eleven_model"],
                           "voice_settings": vs})
        r = subprocess.run(["curl", "-s", "-f", f"https://api.elevenlabs.io/v1/text-to-speech/{V['eleven_id']}/with-timestamps?output_format=mp3_44100_128",
                            "-H", f"xi-api-key: {os.environ['ELEVENLABS_API_KEY']}", "-H", "Content-Type: application/json", "-d", body],
                           capture_output=True, text=True)
        if r.returncode: raise SystemExit(f"ElevenLabs failed for: {say}\n{r.stdout[:400]}")
        open(js, "w").write(r.stdout)
    d = json.load(open(js)); mp3 = js.replace(".json", ".mp3")
    if not os.path.exists(mp3): open(mp3, "wb").write(base64.b64decode(d["audio_base64"]))
    x, off = trim(read_wav(mp3))
    al = d["alignment"]; ch, cs, ce = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    spoken = []; cur = None
    for c, s, e in zip(ch, cs, ce):
        if c.isspace():
            cur = None; continue
        if cur is None: cur = {"w": "", "s": s - off, "e": e - off}; spoken.append(cur)
        cur["w"] += c; cur["e"] = e - off
    return x, [{"w": w["w"], "s": round(max(0, w["s"]), 3), "e": round(w["e"], 3)} for w in spoken]


def norm(w): return re.sub(r"[^a-z0-9%]", "", w.lower())


def align(words, ref, t0, t1):
    """time each of `words` from `ref` (timed words): exact on normalized match, else interpolated"""
    out = [None] * len(words); j = 0
    for i, w in enumerate(words):
        n = norm(w)
        if not n: continue
        for k in range(j, min(len(ref), j + 8)):
            if norm(ref[k]["w"]) == n:
                out[i] = (ref[k]["s"], ref[k]["e"]); j = k + 1; break
    known = [(i, v) for i, v in enumerate(out) if v]
    for i in range(len(words)):
        if out[i]: continue
        prev = max([kv for kv in known if kv[0] < i], default=(-1, (t0, t0)))
        nxt = min([kv for kv in known if kv[0] > i], default=(len(words), (t1, t1)))
        a, b = prev[1][1], nxt[1][0]; f = (i - prev[0]) / (nxt[0] - prev[0])
        st = a + (b - a) * f; out[i] = (st, st + max(0.05, (b - a) / (nxt[0] - prev[0]) * 0.9))
    return [{"w": w, "s": round(v[0], 3), "e": round(v[1], 3)} for w, v in zip(words, out)]


def pron(s):
    for a, b in cfg.get("pronounce", {}).items(): s = s.replace(a, b)
    return s


gen = line_say if backend == "say" else line_eleven
t = 0.0; chunks = []; scenes = []
for sc in cfg["scenes"]:
    s0 = t; t += sc.get("pre", 0.3); lines = []
    for i, ln in enumerate(sc["lines"]):
        ln = ln if isinstance(ln, dict) else {"text": ln}
        if i: t += sc.get("gap", cfg["gap"])
        x, spoken = gen(ln["text"], ln.get("say", pron(ln["text"])))
        fade = np.minimum(1, np.arange(len(x)) / (0.005 * SR)) * np.minimum(1, (len(x) - np.arange(len(x))) / (0.01 * SR))
        chunks.append((t, x * fade))
        spoken = [{"w": w["w"], "s": round(t + w["s"], 3), "e": round(t + w["e"], 3)} for w in spoken]
        e = t + len(x) / SR
        words = align(ln["text"].split(), spoken, t, e)
        rec = {"text": ln["text"], "s": round(t, 3), "e": round(e, 3), "words": words, "spoken": spoken}
        if "head" in ln:
            flat = align([w for h, _ in ln["head"] for w in h.split()], words, t, e)  # one pass, so repeated words map in order
            rec["head"] = []
            for h, hi in ln["head"]:
                n = len(h.split()); rec["head"].append([flat[:n], hi]); flat = flat[n:]
        lines.append(rec)
        t += len(x) / SR
    t += sc.get("post", 0.4)
    if sc is cfg["scenes"][-1] and cfg.get("total"):  # fixed-length spot: pad the end card to the exact slot length
        if t > cfg["total"]: raise SystemExit(f"VO runs {t:.2f}s, over the {cfg['total']}s slot - trim the script or raise speed")
        t = cfg["total"]
    scenes.append({"id": sc["id"], "s": round(s0, 3), "e": round(t, 3), "lines": lines})

buf = np.zeros(int(t * SR) + SR)
for st, x in chunks:
    i = int(st * SR); buf[i:i + len(x)] += x
buf = buf[:int(t * SR)]
pk = np.max(np.abs(buf)); buf = buf / pk * 0.89 if pk > 0 else buf
w = wave.open(f"{OUT}/vo.wav", "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((buf * 32767).astype(np.int16).tobytes()); w.close()
json.dump({"backend": backend, "duration": round(t, 3), "scenes": scenes}, open(f"{OUT}/timeline.json", "w"), indent=1)
print(f"VO ({backend}, {LANG}) -> {OUT}/vo.wav  {t:.1f}s")
for sc in scenes: print(f"  {sc['id']:<11} {sc['s']:6.2f} - {sc['e']:6.2f}  ({sc['e'] - sc['s']:.1f}s)")
