"""Original, copyright-free cinematic / trap hybrid hype track with a clear build and drop -> assets/music/<name>.wav + <name>.json
Usage: python3 make_hype_track.py [name=hype_120bpm]
120 BPM, D minor (Dm - Bb - F - C), 21 bars of 2.0 s = 42 s:
  bars 0-3  intro   : braam hits, felt-piano ostinato, heartbeat sub, swells
  bars 4-7  build   : kick + hats enter, arp, toms, snare roll, riser, half-beat of silence
  bars 8-13 DROP A  : impact, 808, trap hats with rolls, claps, saw stabs, lead hook
  bar  14   switch  : filtered breakdown, riser, tape-stop
  bars 15-18 DROP B : everything + lead an octave up + open hats
  bars 19-20 outro  : final braam + impact, reverb tail
The .json lists beat/bar times and the hit markers (drops, braams, tape-stop) so edits can lock to them.
Built to sit as the master track (no voice); peaks -1 dBFS.
"""
import json, os, sys, wave
import numpy as np

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name = sys.argv[1] if len(sys.argv) > 1 else "hype_120bpm"
BPM = 120.0; BEAT = 60 / BPM; BAR = 4 * BEAT; NBARS = 21
DUR = NBARS * BAR + 0.0
N = int(DUR * SR) + SR      # one extra second for tails, trimmed at the end
rng = np.random.default_rng(7)
SEC = {"intro": (0, 4), "build": (4, 8), "dropA": (8, 14), "switch": (14, 15), "dropB": (15, 19), "outro": (19, 21)}
CH = [[62, 65, 69], [58, 62, 65], [57, 60, 65], [55, 60, 64]]   # Dm Bb F C (voicings)
RT = [38, 34, 41, 36]                                             # roots D2 Bb1 F2 C2


def midi(n): return 440.0 * 2 ** ((n - 69) / 12)
def tt(d): return np.arange(int(d * SR)) / SR
def bar_t(b, beat=0.0): return b * BAR + beat * BEAT
def in_sec(b, *names): return any(SEC[s][0] <= b < SEC[s][1] for s in names)


def fftf(x, lo=None, hi=None, order=4):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if hi: g *= 1 / np.sqrt(1 + (f / hi) ** order)
    if lo: g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** order)
    return np.fft.irfft(X * g, len(x))


def conv(x, ir):
    n = len(x) + len(ir); m = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]


def make_ir(d, decay, lo=200, hi=7000, seed=1):
    r = np.random.default_rng(seed); t = tt(d)
    ir = r.standard_normal(len(t)) * np.exp(-t * decay)
    return fftf(ir, lo, hi) * 0.25


IR_L, IR_R = make_ir(2.2, 3.0, seed=1), make_ir(2.2, 3.0, seed=2)
IR_S = make_ir(0.9, 6.0, 300, 9000, seed=3)


def saw(f, t, ph=0.0):
    return 2 * ((f * t + ph) % 1.0) - 1


def add(buf, x, t0, g=1.0):
    i = int(round(t0 * SR))
    if i >= len(buf) or i + len(x) <= 0: return
    a = max(0, -i); b = min(len(x), len(buf) - i)
    buf[i + a:i + b] += x[a:b] * g


# ---------------------------------------------------------------- instruments (mono unless noted)
def kick(punch=1.0):
    t = tt(0.45); f = 45 + 110 * np.exp(-t * 28) + 40 * np.exp(-t * 200)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6.5)
    click = fftf(rng.standard_normal(len(t)) * np.exp(-t * 300), lo=2000) * 0.25
    return np.tanh((body + click) * 1.6 * punch) * 0.9


def clap():
    t = tt(0.35); x = np.zeros(len(t))
    for k, d in enumerate([0, 0.011, 0.022, 0.031]):
        i = int(d * SR); n = len(t) - i
        x[i:] += rng.standard_normal(n) * np.exp(-np.arange(n) / SR * (60 if k < 3 else 18))
    x = fftf(x, 900, 9000); tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    return (x * 0.55 + tone) * 0.8


def snare():
    t = tt(0.3); n = fftf(rng.standard_normal(len(t)), 1500, 10000) * np.exp(-t * 22)
    body = np.sin(2 * np.pi * np.cumsum(220 + 60 * np.exp(-t * 40)) / SR) * np.exp(-t * 25)
    return (n * 0.7 + body * 0.6) * 0.7


def hat(open_=False):
    t = tt(0.4 if open_ else 0.06); x = fftf(rng.standard_normal(len(t)), 7000, None)
    return x * np.exp(-t * (9 if open_ else 70)) * (0.32 if open_ else 0.28)


def tom(f0):
    t = tt(0.5); f = f0 * (1 + 0.6 * np.exp(-t * 18))
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * 1.4) * 0.6


def piano(n, d=0.9, vel=1.0):
    t = tt(d); f = midi(n); x = np.zeros(len(t))
    for h, a in [(1, 1.0), (2, 0.45), (3, 0.22), (4, 0.12), (5, 0.06)]:
        x += a * np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h)) * np.exp(-t * (2.2 + 1.5 * h))
    att = np.minimum(1, t / 0.004)
    return fftf(x * att, hi=2600) * 0.32 * vel


def pluck(n, d=0.35):
    t = tt(d); f = midi(n)
    x = saw(f, t) + saw(f * 1.006, t, 0.3) + 0.5 * np.sign(np.sin(2 * np.pi * f * 0.5 * t))
    cut = 600 + 5000 * np.exp(-t * 14)
    # time-varying lowpass approximated by blending a bright and a dark copy
    bright = fftf(x, hi=6000); dark = fftf(x, hi=700); k = (cut - 600) / 5000
    return (bright * k + dark * (1 - k)) * np.exp(-t * 6) * np.minimum(1, t / 0.003) * 0.22


def lead(n, d):
    t = tt(d + 0.15); f = midi(n) * (1 + 0.003 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.3))
    ph = np.cumsum(f) / SR
    x = (2 * (ph % 1) - 1) + (2 * ((ph * 1.007 + 0.2) % 1) - 1) + 0.6 * np.sign(np.sin(2 * np.pi * ph * 0.5))
    env = np.minimum(1, t / 0.01) * np.where(t < d, 1.0, np.exp(-(t - d) * 18)) * (0.75 + 0.25 * np.exp(-t * 4))
    return fftf(np.tanh(x * 0.8), lo=180, hi=5200) * env * 0.16


def stab(ch, d=0.22):
    t = tt(d + 0.1); x = np.zeros(len(t))
    for n in ch + [ch[0] + 12]:
        for dt in (-0.012, 0.0, 0.009):
            x += saw(midi(n + 12) * (1 + dt), t, rng.random())
    env = np.minimum(1, t / 0.002) * np.exp(-t * 11)
    return fftf(x, lo=250, hi=4800) * env * 0.07


def sub808(n, d, glide_from=None):
    t = tt(d + 0.05); f0 = midi(n)
    f = np.full(len(t), f0) if glide_from is None else f0 + (midi(glide_from) - f0) * np.exp(-t * 18)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.minimum(1, t / 0.004) * np.where(t < d, np.exp(-t * 0.9), np.exp(-d * 0.9) * np.exp(-(t - d) * 40))
    return np.tanh(x * 2.2) * env * 0.55


def braam(n=26, d=3.5, bright=1.0):
    t = tt(d); x = np.zeros(len(t))
    for m in (n, n + 7, n + 12, n + 19):
        for dt in (-0.006, 0.0, 0.005):
            x += saw(midi(m) * (1 + dt), t, rng.random())
    sweep_dark = fftf(x, hi=220); sweep_bright = fftf(x, hi=1800 * bright)
    k = np.clip(np.minimum(t / 0.25, 1) * np.exp(-t * 0.9), 0, 1)
    y = sweep_dark * (1 - k) + sweep_bright * k
    env = np.minimum(1, t / 0.03) * np.exp(-t * 0.85)
    return np.tanh(y * 0.35 * 2.5) * env * 0.5


def impact():
    t = tt(2.5); sub = np.sin(2 * np.pi * np.cumsum(30 + 70 * np.exp(-t * 9)) / SR) * np.exp(-t * 2.2)
    crack = fftf(rng.standard_normal(len(t)), 300, 8000) * np.exp(-t * 7)
    return np.tanh(sub * 1.8 + crack * 0.6) * 0.75


def riser(d):
    t = tt(d); p = t / d
    noise = rng.standard_normal(len(t)); out = np.zeros(len(t)); seg = int(0.05 * SR)
    for i in range(0, len(t), seg):          # stepped band-pass sweep 300 Hz -> 9 kHz
        c = 300 * (30 ** p[min(i, len(p) - 1)])
        out[i:i + seg] = fftf(noise[i:i + seg] if len(noise[i:i + seg]) > 16 else np.zeros(len(noise[i:i + seg])), c * 0.7, c * 1.4)
    tone = saw(110 * (2 ** (p * 3)), t) * 0.25
    return (fftf(out, 200) * 0.6 + fftf(tone, hi=3000)) * (p ** 2.2) * 0.5


def reverse_cym(d=1.0):
    t = tt(d); x = fftf(rng.standard_normal(len(t)), 4000) * np.exp(-t * 3.5)
    return x[::-1] * 0.35


def heartbeat():
    t = tt(0.35); x = np.sin(2 * np.pi * 48 * t) * np.exp(-t * 14)
    return np.tanh(x * 2) * 0.6


# ---------------------------------------------------------------- arrangement
DR = np.zeros(N); BASS = np.zeros(N); MUS_L = np.zeros(N); MUS_R = np.zeros(N); FX = np.zeros(N); LEAD = np.zeros(N)
kick_times = []
HOOK = [(0, 74, 2), (3, 77, 1), (4, 76, 2), (6, 74, 2), (8, 81, 3), (11, 79, 1), (12, 77, 2), (14, 76, 2),
        (16, 74, 2), (19, 77, 1), (20, 79, 2), (22, 77, 2), (24, 72, 3), (27, 74, 1), (28, 76, 4)]
S16 = BEAT / 4

for b in range(NBARS):
    ci = b % 4; ch = CH[ci]; t0 = bar_t(b)
    # pads: supersaw chord through the whole track (quiet in intro, filtered in switch)
    if b < 20:
        t = tt(BAR + 0.4); env = np.minimum(1, t / 0.35) * np.minimum(1, np.maximum(0, BAR + 0.4 - t) / 0.4)
        pl = np.zeros(len(t)); pr = np.zeros(len(t))
        for n in ch:
            for k, dt in enumerate((-0.01, -0.004, 0.0, 0.005, 0.011)):
                v = saw(midi(n) * (1 + dt), t, rng.random())
                (pl if k % 2 else pr)[:] += v; (pr if k % 2 else pl)[:] += v * 0.5
        g = 0.035 if in_sec(b, "intro") else (0.05 if in_sec(b, "build") else 0.06)
        hi = 1500 if not in_sec(b, "switch") else 500
        add(MUS_L, fftf(pl, 150, hi) * env * g, t0); add(MUS_R, fftf(pr, 150, hi) * env * g, t0)
    # felt-piano ostinato (intro + build + switch), 8ths of chord tones
    if in_sec(b, "intro", "build", "switch"):
        pat = [0, 1, 2, 1, 0, 2, 1, 2]
        for k in range(8):
            n = ch[pat[k]] + (0 if k % 4 else -12 if k == 0 else 0)
            add(MUS_L, piano(n + 12, 1.0, 1.0 if k % 2 == 0 else 0.7), t0 + k * BEAT / 2, 0.9 if k % 2 else 0.6)
            add(MUS_R, piano(n + 12, 1.0, 1.0 if k % 2 == 0 else 0.7), t0 + k * BEAT / 2, 0.6 if k % 2 else 0.9)
    # intro: braams + heartbeat
    if in_sec(b, "intro"):
        if b in (0, 2): add(FX, braam(26, 3.6, 0.8 if b == 0 else 1.0), t0, 0.9)
        for q in (0, 0.45, 2, 2.45):
            add(BASS, heartbeat(), t0 + q * BEAT, 0.8 if q in (0, 2) else 0.5)
        if b == 3: add(FX, reverse_cym(1.5), t0 + 4 * BEAT - 1.5, 0.8)
    # build: kick on 1 & 3 then four-on-floor, hats 8ths, pluck arp, toms + roll last bar
    if in_sec(b, "build"):
        kq = (0, 2) if b < 6 else (0, 1, 2, 3)
        last = b == SEC["build"][1] - 1
        for q in kq:
            if last and q == 3: continue
            add(DR, kick(0.9), t0 + q * BEAT); kick_times.append(t0 + q * BEAT)
        for e in range(8):
            add(DR, hat(), t0 + e * BEAT / 2, 0.8 if e % 2 else 0.5)
        for k in range(16):
            n = ch[k % 3] + 12 + (12 if k % 4 == 3 else 0)
            add(MUS_L, pluck(n), t0 + k * S16, 0.6 + 0.4 * ((b - 4) / 3)); add(MUS_R, pluck(n), t0 + k * S16 + 0.012, 0.6)
        if b == 6:
            for q, f in ((3, 110), (3.5, 90)): add(DR, tom(f), t0 + q * BEAT, 0.8)
        if last:   # snare roll accelerating, half-beat gap before the drop
            ts = []; x = 0.0
            while x < 3.5 * BEAT:
                ts.append(x); x += BEAT / 2 if x < BEAT else (BEAT / 4 if x < 2.5 * BEAT else BEAT / 8)
            for i, x in enumerate(ts): add(DR, snare(), t0 + x, 0.35 + 0.65 * i / len(ts))
            add(FX, riser(BAR - BEAT / 2), t0, 0.9)
            add(FX, reverse_cym(1.2), t0 + BAR - 1.2 - BEAT / 2, 0.7)
    # drops
    if in_sec(b, "dropA", "dropB"):
        B2 = in_sec(b, "dropB"); first = b in (SEC["dropA"][0], SEC["dropB"][0])
        if first:
            add(FX, impact(), t0, 1.0); add(FX, braam(26, 2.5, 1.3), t0, 0.6)
        # kick: 1, a-of-2 (3/4 beat after beat2), 3, and-of-4 in odd bars
        kpat = [0, 1.75, 2.0] + ([3.5] if b % 2 else [])
        for q in kpat:
            add(DR, kick(1.1), t0 + q * BEAT); kick_times.append(t0 + q * BEAT)
        for q in (1, 3):
            add(DR, clap(), t0 + q * BEAT, 0.9); add(DR, snare(), t0 + q * BEAT, 0.35)
        # trap hats: 16ths, roll (32nd triplets) on the last beat of every 2nd bar
        for k in range(16):
            if b % 2 and k >= 12:
                for r in range(6):
                    add(DR, hat(), t0 + 3 * BEAT + r * BEAT / 6, 0.35 + 0.08 * r)
                break
            add(DR, hat(), t0 + k * S16, 0.75 if k % 4 == 2 else (0.5 if k % 2 == 0 else 0.35))
        if B2:
            for q in (0.5, 2.5): add(DR, hat(True), t0 + q * BEAT, 0.6)
        # 808 following roots, glide into each bar
        add(BASS, sub808(RT[ci] + 12 if RT[ci] < 36 else RT[ci], 1.7 * BEAT, glide_from=RT[ci] + 7 if b % 2 == 0 else None), t0, 1.0)
        add(BASS, sub808(RT[ci] + 12 if RT[ci] < 36 else RT[ci], 1.1 * BEAT), t0 + 1.75 * BEAT, 0.85)
        add(BASS, sub808(RT[ci] + 12 if RT[ci] < 36 else RT[ci], 1.6 * BEAT), t0 + 2.0 * BEAT, 0.9)
        # stabs on the off-beats
        for q in (0.5, 1.5, 2.75):
            s = stab(ch); add(MUS_L, s, t0 + q * BEAT, 0.9); add(MUS_R, s, t0 + q * BEAT + 0.008, 0.9)
        # lead hook over 2-bar phrase
        base = (b - (SEC["dropB"][0] if B2 else SEC["dropA"][0])) % 2
        for st, n, ln in HOOK:
            if (st >= 16) == bool(base):
                add(LEAD, lead(n + (12 if B2 else 0), ln * S16), t0 + (st - 16 * base) * S16, 1.0 if B2 else 0.85)
                if B2: add(LEAD, lead(n, ln * S16), t0 + (st - 16 * base) * S16, 0.45)
    # switch: drums out, riser, tape stop at the end (handled after mix)
    if in_sec(b, "switch"):
        add(FX, riser(BAR - BEAT / 4), t0, 1.0)
        for q in (0, 2): add(BASS, sub808(RT[ci], 0.9 * BEAT), t0 + q * BEAT, 0.6)
        for k in range(8): add(DR, snare(), t0 + 2 * BEAT + k * BEAT / 4, 0.25 + 0.08 * k)
    # outro
    if in_sec(b, "outro") and b == SEC["outro"][0]:
        add(FX, impact(), t0, 1.0); add(FX, braam(26, 4.0, 1.2), t0, 0.95)
        add(MUS_L, piano(62, 3.0), t0 + 0.5, 0.8); add(MUS_R, piano(69, 3.0), t0 + 0.5, 0.8)

# ---------------------------------------------------------------- mix
# sidechain pump on pads/stabs/bass from kicks in the drops
pump = np.ones(N)
for k in kick_times:
    i = int(k * SR); n = min(int(0.28 * SR), N - i)
    if n > 0: pump[i:i + n] = np.minimum(pump[i:i + n], 0.35 + 0.65 * (np.arange(n) / n) ** 0.6)
MUS_L *= pump; MUS_R *= pump
BASS = fftf(BASS, hi=900) * np.sqrt(pump)
lead_rev_l = conv(LEAD, IR_L) * 0.35; lead_rev_r = conv(LEAD, IR_R) * 0.35
dl = int(BEAT * 0.75 * SR)
lead_dly = np.concatenate([np.zeros(dl), LEAD[:-dl]]) * 0.25
mus_rev_l = conv(MUS_L, IR_L) * 0.4; mus_rev_r = conv(MUS_R, IR_R) * 0.4
dr_rev = conv(fftf(DR, 400), IR_S) * 0.25
fx_rev_l = conv(FX, IR_L) * 0.5; fx_rev_r = conv(FX, IR_R) * 0.5
L = MUS_L + mus_rev_l + LEAD + lead_rev_l + lead_dly + DR + dr_rev + BASS + FX * 0.9 + fx_rev_l
R = MUS_R + mus_rev_r + LEAD * 0.95 + lead_rev_r + DR * 0.98 + dr_rev + BASS + FX * 0.9 + fx_rev_r
# tape-stop on the last beat of the switch bar: pitch/time slows to zero
ts0 = bar_t(SEC["switch"][0], 3.0); ts1 = bar_t(SEC["switch"][1])
i0, i1 = int(ts0 * SR), int(ts1 * SR)
for ch_ in (L, R):
    seg = ch_[i0:i1].copy(); n = len(seg); pos = np.cumsum(np.linspace(1.0, 0.0, n)); pos = pos / pos[-1] * (n * 0.5)
    ch_[i0:i1] = np.interp(pos, np.arange(n), seg) * np.linspace(1, 0.2, n)
# section dynamics: quiet cinematic intro -> rising build -> loudest drops (contrast is what makes a drop hit)
tg = np.arange(N) / SR
curve = np.interp(tg, [0, bar_t(4) - 0.01, bar_t(4), bar_t(8) - BEAT / 2, bar_t(8) - 0.01, bar_t(8), bar_t(14), bar_t(14) + 0.3,
                       bar_t(15) - 0.01, bar_t(15), bar_t(19), DUR + 1],
                  [0.30, 0.34, 0.42, 0.62, 0.62, 1.0, 1.0, 0.55, 0.6, 1.06, 1.0, 1.0])
L *= curve; R *= curve
# master: gentle glue (soft clip), fade the tail, peak -1 dBFS
st = np.stack([L, R], 1)[: int(DUR * SR)]
tail = np.arange(len(st)) / SR; st *= np.minimum(1, (DUR - tail) / 2.5)[:, None] ** 1.5
st = st / np.max(np.abs(st)) * 1.6; st = np.tanh(st) / np.tanh(1.6) * 0.89
os.makedirs(f"{ROOT}/assets/music", exist_ok=True)
w = wave.open(f"{ROOT}/assets/music/{name}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()
markers = {"bpm": BPM, "beat": BEAT, "bar": BAR, "first_beat": 0.0, "duration": DUR,
           "sections": {k: [bar_t(a), bar_t(b)] for k, (a, b) in SEC.items()},
           "hits": {"braam_0": 0.0, "braam_1": bar_t(2), "pre_drop_gap": bar_t(8) - BEAT / 2, "dropA": bar_t(8),
                    "tape_stop": ts0, "dropB": bar_t(15), "outro_hit": bar_t(19)}}
json.dump(markers, open(f"{ROOT}/assets/music/{name}.json", "w"), indent=1)
print(f"music -> assets/music/{name}.wav ({DUR:.1f}s, {BPM:.0f} bpm); markers -> {name}.json")
