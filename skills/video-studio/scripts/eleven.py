#!/usr/bin/env python3
"""ElevenLabs helper for the ~/video-editing studio (stdlib only: pip is blocked, `requests` isn't installed).

    python3 eleven.py credits
    python3 eleven.py tts  "text" out.mp3 [--voice ID] [--model eleven_multilingual_v2] [--speed 1.05] [--words out.json]
    python3 eleven.py stt  in.(wav|mp4|...) out.json [--lang hin] [--speakers 2] [--yes]
    python3 eleven.py isolate in.(wav|mp4|...) out.wav [--chunk 300] [--yes]

- Key: ELEVENLABS_API_KEY from the env or ~/video-editing/.env.
- tts: writes the audio plus (with --words) word timings {"words":[{word,start,end}]} built from the character alignment.
  Cached by (text, voice, model, settings) in ~/.cache/eleven_tts, so re-runs of unchanged lines cost nothing.
- stt: Scribe (scribe_v1), verbatim, word timestamps, diarization, audio events. Unlike whisper-cpp it KEEPS fillers and
  stutters (अअअ, ता-ताकत, umm), which is exactly what a filler-cut pass needs. Output: Scribe JSON + "words" list
  [{word,start,end,speaker,type}] (type word|audio_event; spacing dropped). ~18 credits/min (Starter = 40k/month).
- isolate: voice isolation (removes echo/room/noise). ~600 credits/min, so it ALWAYS asks unless --yes. Splits into chunks
  (default 300 s with 1 s overlap), re-aligns each returned chunk to the source by cross-correlation (the mp3 comes back
  with a small offset) and crossfades the overlaps, so the result stays sample-locked to the video.
"""
import argparse, base64, hashlib, json, os, subprocess, sys, tempfile, uuid, urllib.request, urllib.error
STUDIO = os.environ.get("VIDEO_STUDIO", os.path.expanduser("~/video-editing"))
import numpy as np

API = "https://api.elevenlabs.io"
DEFAULT_VOICE = "siw1N9V8LmYeEWKyWBxv"  # Ruhaan (studio default); Prem 05QRrdNgiglhuYOaTQvw, Saavi H8bdWZHK2OgZwTN7ponr, Viraj bajNon13EdhNMndG3z05
SR = 48000


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        env = os.path.join(STUDIO, ".env")
        if os.path.exists(env):
            for line in open(env):
                if line.startswith("ELEVENLABS_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        sys.exit("ELEVENLABS_API_KEY not set (env or ~/video-editing/.env)")
    return k


def call(method, path, body=None, headers=None, raw=False):
    h = {"xi-api-key": key()}
    h.update(headers or {})
    req = urllib.request.Request(API + path, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:600]
        if e.code in (401, 402):
            msg += "\n(401/402 on a library voice usually means the account is on the Free tier, or credits ran out)"
        sys.exit(f"ElevenLabs {e.code}: {msg}")
    return data if raw else json.loads(data)


def multipart(fields, files):
    b = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (fname, data, ctype) in files.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
        out += data + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), {"Content-Type": f"multipart/form-data; boundary={b}"}


def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout)


def credits():
    s = call("GET", "/v1/user/subscription")
    used, lim = s.get("character_count", 0), s.get("character_limit", 0)
    print(f"tier {s.get('tier')}: {used:,} / {lim:,} credits used, {lim - used:,} left")
    return lim - used


def confirm(cost, yes):
    left = credits()
    print(f"this job: ~{cost:,.0f} credits")
    if cost > left:
        sys.exit("not enough credits left")
    if not yes:
        sys.exit("re-run with --yes to spend them (ask the user first)")


# ---------- TTS ----------
def tts(a):
    settings = {"stability": a.stability, "similarity_boost": a.similarity, "style": a.style, "speed": a.speed}
    body = {"text": a.text, "model_id": a.model, "voice_settings": settings}
    h = hashlib.sha1(json.dumps([body, a.voice, a.format], sort_keys=True).encode()).hexdigest()[:16]
    cache = os.path.expanduser(f"~/.cache/eleven_tts/{h}.json")
    cached = os.path.exists(cache)
    if cached:
        r = json.load(open(cache))
    else:
        r = call("POST", f"/v1/text-to-speech/{a.voice}/with-timestamps?output_format={a.format}",
                 json.dumps(body).encode(), {"Content-Type": "application/json"})
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump(r, open(cache, "w"))
    open(a.out, "wb").write(base64.b64decode(r["audio_base64"]))
    if a.words:
        al = r.get("alignment") or r["normalized_alignment"]
        words, cur = [], None
        for ch, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
            if ch.isspace():
                cur = None
                continue
            if cur is None:
                cur = {"word": "", "start": s, "end": e}
                words.append(cur)
            cur["word"] += ch
            cur["end"] = e
        json.dump({"text": a.text, "words": words}, open(a.words, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {a.out}" + (f" + {a.words}" if a.words else "") + (" (cached)" if cached else ""))


# ---------- STT ----------
def stt(a):
    mins = duration(a.inp) / 60
    confirm(mins * 18, a.yes or mins < 5)
    with tempfile.TemporaryDirectory() as td:
        mp3 = os.path.join(td, "a.mp3")
        ff("-i", a.inp, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", mp3)
        fields = {"model_id": "scribe_v1", "timestamps_granularity": "word", "diarize": "true", "tag_audio_events": "true"}
        if a.lang:
            fields["language_code"] = a.lang
        if a.speakers:
            fields["num_speakers"] = str(a.speakers)
        body, h = multipart(fields, {"file": ("a.mp3", open(mp3, "rb").read(), "audio/mpeg")})
        r = call("POST", "/v1/speech-to-text", body, h)
    r["words"] = [{"word": w["text"], "start": w["start"], "end": w["end"], "speaker": w.get("speaker_id"), "type": w["type"]}
                  for w in r.get("words", []) if w.get("type") != "spacing"]
    json.dump(r, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {a.out}: {len(r['words'])} words, language {r.get('language_code')}")


# ---------- isolation ----------
def load(path):
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.float32).copy()


def lag(ref, sig, max_lag=0.5):
    """Samples to shift `sig` left so it lines up with `ref` (FFT cross-correlation on the first 20 s)."""
    n = min(len(ref), len(sig), SR * 20)
    a, b = ref[:n] - ref[:n].mean(), sig[:n] - sig[:n].mean()
    m = 1 << (2 * n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(b, m) * np.conj(np.fft.rfft(a, m)), m)
    L = int(SR * max_lag)
    c = np.concatenate([c[-L:], c[:L + 1]])
    return int(np.argmax(c)) - L


def isolate(a):
    total = duration(a.inp)
    confirm(total / 60 * 600, a.yes)
    src = load(a.inp)
    chunk, ov = int(a.chunk * SR), SR
    out = np.zeros(len(src), np.float32)
    weight = np.zeros(len(src), np.float32)
    starts = list(range(0, len(src), chunk))
    with tempfile.TemporaryDirectory() as td:
        for i, s in enumerate(starts):
            e = min(len(src), s + chunk + ov)
            wav = os.path.join(td, f"c{i}.wav")
            seg = src[s:e]
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", wav],
                           input=seg.tobytes(), check=True)
            body, h = multipart({}, {"audio": (f"c{i}.wav", open(wav, "rb").read(), "audio/wav")})
            res = os.path.join(td, f"r{i}.mp3")
            open(res, "wb").write(call("POST", "/v1/audio-isolation", body, h, raw=True))
            iso = load(res)
            d = lag(seg, iso)
            iso = iso[d:] if d >= 0 else np.concatenate([np.zeros(-d, np.float32), iso])
            iso = np.pad(iso, (0, max(0, len(seg) - len(iso))))[:len(seg)]
            w = np.ones(len(seg), np.float32)
            if i > 0:
                w[:ov] = np.linspace(0, 1, ov)
            if e < len(src):
                w[-ov:] = np.linspace(1, 0, ov)
            out[s:e] += iso * w
            weight[s:e] += w
            print(f"chunk {i + 1}/{len(starts)}: offset {d / SR * 1000:+.1f} ms", flush=True)
    out /= np.maximum(weight, 1e-6)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s24le", a.out], input=out.tobytes(), check=True)
    print(f"wrote {a.out} ({total:.1f} s, aligned to source)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("credits")
    t = sp.add_parser("tts")
    t.add_argument("text"); t.add_argument("out")
    t.add_argument("--voice", default=DEFAULT_VOICE); t.add_argument("--model", default="eleven_multilingual_v2")
    t.add_argument("--speed", type=float, default=1.0); t.add_argument("--stability", type=float, default=0.5)
    t.add_argument("--similarity", type=float, default=0.75); t.add_argument("--style", type=float, default=0.0)
    t.add_argument("--format", default="mp3_44100_128", help="Starter plan: mp3_44100_128 (192k needs Creator)")
    t.add_argument("--words")
    s = sp.add_parser("stt")
    s.add_argument("inp"); s.add_argument("out"); s.add_argument("--lang", default="hin")
    s.add_argument("--speakers", type=int); s.add_argument("--yes", action="store_true")
    i = sp.add_parser("isolate")
    i.add_argument("inp"); i.add_argument("out"); i.add_argument("--chunk", type=float, default=300)
    i.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    {"credits": lambda a: credits(), "tts": tts, "stt": stt, "isolate": isolate}[a.cmd](a)


if __name__ == "__main__":
    main()
