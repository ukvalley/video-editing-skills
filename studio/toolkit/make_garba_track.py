"""Original, copyright-free cinematic garba / dandiya track -> assets/music/<name>.wav + <name>.json
Usage: python3 make_garba_track.py [name=garba_cinematic_128bpm]
128 BPM, 12/8 garba feel (each beat = 3 triplet-eighths, a bar = two 6/8 garba cycles), D Khamaj (Mixolydian).
17 bars of 1.875 s = 31.9 s (+ tail):
  bars 0-3   intro    : tanpura drone, temple bells, ghungroo shimmer, bansuri alaap, slow swell
  bars 4-5   build    : dhol enters soft -> chalti roll, dandiya clicks, riser, half-beat gap
  bars 6-13  DROP     : full garba groove (dhol dagga/tilli, dandiya taps, manjira, bass), shehnai hook, harmonium
  bar  14    break    : groove drops out -> dandiya clicks + drone + bansuri (emotional moment)
  bars 15-16 finale   : full groove with hook an octave up, last-beat hit, ring-out
The .json lists beat/bar times and hit markers so the edit can lock to them. Peaks -1 dBFS.
"""
import json, os, sys, wave
import numpy as np

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name = sys.argv[1] if len(sys.argv) > 1 else "garba_cinematic_128bpm"
BPM = 128.0; BEAT = 60 / BPM; E8 = BEAT / 3; BAR = 4 * BEAT; NBARS = 17
DUR = NBARS * BAR + 2.5
N = int(DUR * SR)
rng = np.random.default_rng(11)
SEC = {"intro": (0, 4), "build": (4, 6), "drop": (6, 14), "break": (14, 15), "finale": (15, 17)}


def midi(n): return 440.0 * 2 ** ((n - 69) / 12)
def tt(d): return np.arange(int(d * SR)) / SR
def bt(b, e=0.0): return b * BAR + e * E8          # bar b, triplet-eighth e (0..11)
def sec(b, *names): return any(SEC[s][0] <= b < SEC[s][1] for s in names)


def fftf(x, lo=None, hi=None, order=4):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if hi: g *= 1 / np.sqrt(1 + (f / hi) ** order)
    if lo: g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** order)
    return np.fft.irfft(X * g, len(x))


def peak(x, fc, q=4.0, gain=1.0):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 1 + gain * np.exp(-((f - fc) / (fc / q)) ** 2)
    return np.fft.irfft(X * g, len(x))


def conv(x, ir):
    n = len(x) + len(ir); m = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)]


def make_ir(d, decay, lo=200, hi=7000, seed=1):
    r = np.random.default_rng(seed); t = tt(d)
    return fftf(r.standard_normal(len(t)) * np.exp(-t * decay), lo, hi) * 0.25


IR_L, IR_R = make_ir(2.6, 2.6, seed=1), make_ir(2.6, 2.6, seed=2)


def add(buf, x, t0, g=1.0):
    i = int(round(t0 * SR))
    if i >= len(buf) or i + len(x) <= 0: return
    a = max(0, -i); b = min(len(x), len(buf) - i)
    buf[i + a:i + b] += x[a:b] * g


# ---------------------------------------------------------------- instruments
def dhol_bass(v=1.0):          # dagga (low side): pitched membrane with downward bend + slap
    t = tt(0.6); f = 62 + 70 * np.exp(-t * 22)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5.5)
    over = np.sin(2 * np.pi * np.cumsum(f * 2.3) / SR) * np.exp(-t * 14) * 0.35
    slap = fftf(rng.standard_normal(len(t)) * np.exp(-t * 180), 400, 3500) * 0.35
    return np.tanh((body + over + slap) * 1.8 * v) * 0.85


def dhol_tilli(v=1.0, ring=False):   # tilli (stick side): bright, tight crack with a ringing head
    t = tt(0.25); f0 = 330 if ring else 410
    tone = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.15 * np.exp(-t * 60))) / SR) * np.exp(-t * (18 if ring else 32))
    crack = fftf(rng.standard_normal(len(t)), 1800, 9000) * np.exp(-t * 70)
    return (tone * 0.55 + crack * 0.6) * 0.55 * v


def dandiya(v=1.0, pan=0.0):    # two wooden sticks: short resonant woodblock click (stereo)
    t = tt(0.12); x = np.zeros(len(t))
    for f, d in ((1850, 95), (2650, 120), (4100, 160)):
        x += np.sin(2 * np.pi * f * (1 + rng.uniform(-0.02, 0.02)) * t) * np.exp(-t * d)
    x += fftf(rng.standard_normal(len(t)), 2000, 8000) * np.exp(-t * 400) * 0.6
    x *= 0.33 * v
    return x * (1 - pan) / 1.4, x * (1 + pan) / 1.4


def manjira(v=1.0, open_=False):   # small cymbals: metallic partials
    t = tt(0.9 if open_ else 0.18); x = np.zeros(len(t))
    for f in (3150, 4420, 5870, 7330):
        x += np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t * (4 if open_ else 26))
    x += fftf(rng.standard_normal(len(t)), 6000) * np.exp(-t * (8 if open_ else 50)) * 0.8
    return x * (0.035 if open_ else 0.06) * v


def bell(n, d=3.0):            # temple bell: inharmonic partials
    t = tt(d); f = midi(n); x = np.zeros(len(t))
    for r, a, dc in ((1, 1, 0.9), (2.0, 0.5, 1.4), (2.76, 0.4, 1.8), (5.4, 0.25, 3), (8.93, 0.12, 5)):
        x += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * dc)
    return x * np.minimum(1, t / 0.002) * 0.06


def ghungroo(d=0.25):          # ankle bells shimmer
    t = tt(d); x = np.zeros(len(t))
    for k in range(8):
        o = int(rng.uniform(0, 0.06) * SR); tk = t[:len(t) - o]
        f = rng.uniform(4500, 8000)
        x[o:] += np.sin(2 * np.pi * f * tk) * np.exp(-tk * 30)
    return x * 0.02


def tanpura(n, d):             # bright jawari drone (rich harmonics with slow shimmer)
    t = tt(d); f = midi(n); x = np.zeros(len(t))
    for h in range(1, 14):
        x += (1 / h ** 0.9) * np.sin(2 * np.pi * f * h * t + rng.random() * 6) * (0.7 + 0.3 * np.sin(2 * np.pi * (0.2 + 0.07 * h) * t))
    env = np.minimum(1, t / 0.08) * np.exp(-t * 0.5)
    return fftf(x, 60, 5000) * env * 0.03


def shehnai(n, d, bend_from=None, vib=1.0):   # nasal double-reed: odd-heavy saw through formants, meend + vibrato
    t = tt(d + 0.12)
    f = np.full(len(t), midi(n))
    if bend_from is not None: f = midi(n) + (midi(bend_from) - midi(n)) * np.exp(-t * 22)
    f = f * (1 + 0.006 * vib * np.sin(2 * np.pi * 5.8 * t) * np.clip((t - 0.12) / 0.25, 0, 1))
    ph = np.cumsum(f) / SR
    x = 2 * (ph % 1) - 1 + 0.5 * np.sign(np.sin(2 * np.pi * ph))
    x = peak(peak(fftf(np.tanh(x * 1.3), 300, 6000), 1250, 3, 2.5), 2600, 4, 1.4)
    env = np.minimum(1, t / 0.025) * np.where(t < d, 1.0, np.exp(-(t - d) * 25)) * (0.85 + 0.15 * np.exp(-t * 6))
    return x * env * 0.075


def bansuri(n, d, bend_from=None):           # breathy bamboo flute
    t = tt(d + 0.25)
    f = np.full(len(t), midi(n))
    if bend_from is not None: f = midi(n) + (midi(bend_from) - midi(n)) * np.exp(-t * 12)
    f = f * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.2) / 0.4, 0, 1))
    ph = np.cumsum(f) / SR
    x = np.sin(2 * np.pi * ph) + 0.18 * np.sin(4 * np.pi * ph) + 0.06 * np.sin(6 * np.pi * ph)
    br = fftf(rng.standard_normal(len(t)), midi(n) * 0.8, midi(n) * 3) * 0.12
    env = np.minimum(1, t / 0.09) * np.where(t < d, 1.0, np.exp(-(t - d) * 9))
    return (x + br) * env * 0.11


def harmonium(notes, d):        # reed organ: pulse-ish with slight beating, stereo
    t = tt(d + 0.15); l = np.zeros(len(t)); r = np.zeros(len(t))
    for n in notes:
        for k, dt in enumerate((-0.0025, 0.0, 0.003)):
            ph = midi(n) * (1 + dt) * t + rng.random()
            v = np.where((ph % 1) < 0.32, 1.0, -0.47)
            (l if k != 1 else r)[:] += v; (r if k != 1 else l)[:] += v * 0.6
    env = np.minimum(1, t / 0.06) * np.where(t < d, 1.0, np.exp(-(t - d) * 14))
    return fftf(l, 150, 2600) * env * 0.022, fftf(r, 150, 2600) * env * 0.022


def bass(n, d):
    t = tt(d + 0.05); x = np.sin(2 * np.pi * midi(n) * t) + 0.3 * np.sin(4 * np.pi * midi(n) * t)
    env = np.minimum(1, t / 0.005) * np.where(t < d, np.exp(-t * 2.5), np.exp(-d * 2.5) * np.exp(-(t - d) * 40))
    return np.tanh(x * 1.6) * env * 0.33


def impact():
    t = tt(2.8); sub = np.sin(2 * np.pi * np.cumsum(32 + 75 * np.exp(-t * 9)) / SR) * np.exp(-t * 2.0)
    crack = fftf(rng.standard_normal(len(t)), 300, 8000) * np.exp(-t * 7)
    return np.tanh(sub * 1.8 + crack * 0.6) * 0.7


def riser(d):
    t = tt(d); p = t / d; noise = rng.standard_normal(len(t)); out = np.zeros(len(t)); seg = int(0.05 * SR)
    for i in range(0, len(t), seg):
        c = 300 * (30 ** p[min(i, len(p) - 1)]); s = noise[i:i + seg]
        out[i:i + seg] = fftf(s, c * 0.7, c * 1.4) if len(s) > 16 else 0
    return fftf(out, 200) * (p ** 2.2) * 0.45


def swell(d):                   # reversed cymbal into a downbeat
    t = tt(d); return (fftf(rng.standard_normal(len(t)), 3500) * np.exp(-t * 3.0))[::-1] * 0.3


# ---------------------------------------------------------------- arrangement
DR_L = np.zeros(N); DR_R = np.zeros(N); MUS_L = np.zeros(N); MUS_R = np.zeros(N); LEAD = np.zeros(N); FX = np.zeros(N); LOW = np.zeros(N)
# hook (D Khamaj): (eighth, midi, length in eighths) per bar of a 4-bar phrase
HOOK = [[(0, 69, 2), (2, 71, 1), (3, 69, 1), (4, 67, 1), (5, 66, 1), (6, 67, 2), (8, 69, 1), (9, 66, 2), (11, 64, 1)],
        [(0, 62, 2), (2, 64, 1), (3, 66, 1), (4, 67, 1), (5, 69, 1), (6, 71, 1), (7, 69, 1), (8, 67, 1), (9, 66, 2), (11, 64, 1)],
        [(0, 69, 3), (3, 74, 2), (5, 72, 1), (6, 71, 2), (8, 69, 1), (9, 67, 2), (11, 66, 1)],
        [(0, 67, 1), (1, 66, 1), (2, 64, 1), (3, 66, 2), (5, 67, 1), (6, 64, 3), (9, 62, 3)]]
ROOTS = [38, 38, 36, 43]                       # D D C G (bass)
CHORDS = [[62, 69], [62, 69], [60, 67], [59, 67, 62]]

for b in range(NBARS):
    t0 = bt(b); ph = (b - 6) % 4
    # tanpura drone throughout (Pa-Sa-Sa-Sa pluck cycle), quieter under the full groove
    if b < 16:
        g = 1.0 if sec(b, "intro", "break") else 0.6
        for k, n in enumerate((57, 62, 62, 50)):
            add(MUS_L if k % 2 else MUS_R, tanpura(n, 3.0), t0 + k * BEAT, g)
            add(MUS_R if k % 2 else MUS_L, tanpura(n, 3.0), t0 + k * BEAT, g * 0.5)

    if sec(b, "intro"):
        if b in (0, 2): add(FX, bell(74, 4.0), t0, 1.2); add(FX, bell(81, 3.0), t0 + 2 * BEAT, 0.6)
        for k in range(4): add(FX, ghungroo(), t0 + k * BEAT + rng.uniform(0, 0.08), 0.5 + 0.2 * b)
        # bansuri alaap (free phrase across bars 0-3)
    if sec(b, "build"):
        # dhol enters: bar 4 sparse, bar 5 chalti roll accelerating into the drop
        if b == 4:
            for e, v in ((0, 0.7), (3, 0.5), (6, 0.8), (9, 0.55)): add(LOW, dhol_bass(v), bt(b, e))
            for e in (2, 5, 8, 11): add(DR_L, dhol_tilli(0.5), bt(b, e)); add(DR_R, dhol_tilli(0.5), bt(b, e))
            for e in (0, 3, 6, 9):
                l, r = dandiya(0.7, -0.3); add(DR_L, l, bt(b, e)); add(DR_R, r, bt(b, e))
        else:
            for e in range(11):            # leave the last eighth empty: a breath before the drop
                v = 0.5 + 0.5 * e / 10
                add(LOW, dhol_bass(v), bt(b, e)) if e % 3 == 0 else None
                add(DR_L, dhol_tilli(v), bt(b, e)); add(DR_R, dhol_tilli(v * 0.8), bt(b, e))
                if e >= 6: add(DR_L, dhol_tilli(v * 0.6, True), bt(b, e + 0.5)); add(DR_R, dhol_tilli(v * 0.6, True), bt(b, e + 0.5))
            hl, hr = harmonium([62, 69, 74], BAR - E8); add(MUS_L, hl, t0, 0.7); add(MUS_R, hr, t0, 0.7)
        add(FX, ghungroo(0.3), t0 + BEAT, 0.8)

    if sec(b, "drop", "finale"):
        # garba groove: per 6/8 cycle -> DHA . na DHA . na  (dagga on 0 & 3, tilli fills)
        for half in (0, 6):
            add(LOW, dhol_bass(1.0), bt(b, half)); add(LOW, dhol_bass(0.75), bt(b, half + 3))
            for e, v, ring in ((1, 0.45, False), (2, 0.85, True), (4, 0.5, False), (5, 0.9, True)):
                add(DR_L, dhol_tilli(v, ring), bt(b, half + e)); add(DR_R, dhol_tilli(v * 0.85, ring), bt(b, half + e))
            # dandiya: tak (on 0) .. tak-tak (on 2,3) like the dancers' strikes
            for e, v, p in ((0, 1.0, -0.4), (2, 0.6, 0.4), (3, 0.95, 0.4)):
                l, r = dandiya(v, p); add(DR_L, l, bt(b, half + e)); add(DR_R, r, bt(b, half + e))
            for e in range(6):
                add(DR_L if e % 2 else DR_R, manjira(0.9 if e in (0, 3) else 0.5), bt(b, half + e))
        add(DR_L, manjira(1.0, True), t0); add(DR_R, manjira(1.0, True), t0)
        # bass + harmonium
        add(LOW, bass(ROOTS[ph], 3 * E8), bt(b, 0)); add(LOW, bass(ROOTS[ph], 2 * E8), bt(b, 3), 0.8)
        add(LOW, bass(ROOTS[ph] + 7, 3 * E8), bt(b, 6), 0.9); add(LOW, bass(ROOTS[ph], 2 * E8), bt(b, 9), 0.8)
        for e in (0, 6):
            hl, hr = harmonium(CHORDS[ph], 5.5 * E8); add(MUS_L, hl, bt(b, e)); add(MUS_R, hr, bt(b, e))
        # shehnai hook (bars 8-13 + finale; bars 6-7 groove-only so the drop breathes)
        if b >= 8 or sec(b, "finale"):
            up = 12 if sec(b, "finale") else 0
            prev = None
            for e, n, ln in HOOK[ph]:
                add(LEAD, shehnai(n + up, ln * E8 * 0.95, bend_from=(prev + up) if prev and abs(prev - n) <= 3 and ln >= 2 else None), bt(b, e))
                prev = n

    if sec(b, "break"):
        for e in (0, 3, 6, 9):
            l, r = dandiya(0.8, -0.3 if e % 6 else 0.3); add(DR_L, l, bt(b, e)); add(DR_R, r, bt(b, e))
        add(FX, bell(74, 3.0), t0, 0.8)
        hl, hr = harmonium([62, 69, 74], BAR); add(MUS_L, hl, t0, 0.6); add(MUS_R, hr, t0, 0.6)

# bansuri lines: intro alaap and the break
ALAAP = [(0.3, 74, 1.4, 76), (1.9, 72, 0.6, None), (2.5, 71, 0.5, None), (3.0, 69, 1.6, 71),
         (4.9, 71, 0.5, None), (5.4, 72, 0.5, None), (5.9, 74, 1.1, 72), (7.2, 69, 0.55, None)]
for s, n, d, bf in ALAAP: add(LEAD, bansuri(n, d, bf), s)
for s, n, d, bf in [(0.0, 81, 0.7, 83), (0.75, 79, 0.35, None), (1.1, 78, 0.7, None)]: add(LEAD, bansuri(n, d, bf), bt(14) + s, 0.9)

# transitions & hits
add(FX, riser(BAR * 2 - E8), bt(4), 0.9)
add(FX, swell(1.2), bt(6) - 1.2, 1.0)
add(LOW, impact(), bt(6), 1.0); add(FX, bell(86, 2.0), bt(6), 0.8)
add(FX, swell(0.9), bt(15) - 0.9, 0.9); add(LOW, impact(), bt(15), 0.8)
add(FX, swell(0.6), bt(14) - 0.6, 0.6)
END = bt(17)
add(LOW, impact(), END, 1.0); add(FX, bell(74, 3.0), END, 1.2); add(DR_L, manjira(1.3, True), END); add(DR_R, manjira(1.3, True), END)
for k in range(3):    # final 3 dandiya strikes leading into the last hit
    l, r = dandiya(1.1, 0.0); add(DR_L, l, END - (3 - k) * E8); add(DR_R, r, END - (3 - k) * E8)

# ---------------------------------------------------------------- mix
def glue(x, amt=1.0): return np.tanh(x * amt) / max(np.tanh(amt), 1e-6)


rev_send_l = MUS_L * 0.5 + LEAD * 0.55 + FX * 0.6 + DR_L * 0.10
rev_send_r = MUS_R * 0.5 + LEAD * 0.55 + FX * 0.6 + DR_R * 0.10
RL = conv(rev_send_l, IR_L); RR = conv(rev_send_r, IR_R)
L = LOW * 0.95 + DR_L + MUS_L + LEAD * 0.95 + FX * 0.8 + RL * 0.38
R = LOW * 0.95 + DR_R + MUS_R + LEAD * 0.95 + FX * 0.8 + RR * 0.38
# sidechain-ish duck of music bed on dhol bass hits (pumps the groove)
st = np.stack([L, R])
# arrangement dynamics: soft intro, building, full drop, a dip for the break
tg = np.arange(N) / SR
env = np.interp(tg, [0, bt(4), bt(5), bt(6) - 0.01, bt(6), bt(14), bt(14) + 0.05, bt(15) - 0.3, bt(15), DUR],
                     [0.5, 0.55, 0.7, 0.85, 1.0, 1.0, 0.62, 0.7, 1.0, 1.0])
st = st * env
st = glue(st / np.max(np.abs(st)) * 1.05, 0.9)
fade = np.ones(N); fl = int(2.2 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 2
st *= fade
st = st / np.max(np.abs(st)) * 10 ** (-1 / 20)
out = f"{ROOT}/assets/music/{name}.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st.T * 32767).astype(np.int16).tobytes())
meta = {"bpm": BPM, "beat": BEAT, "eighth": E8, "bar": BAR, "first_beat": 0.0, "bars": NBARS, "duration": DUR,
        "sections": {k: [bt(a), bt(b)] for k, (a, b) in SEC.items()},
        "hits": {"drop": bt(6), "break": bt(14), "finale": bt(15), "end_hit": END},
        "note": "12/8 garba feel: beat = 3 triplet-eighths. Cut on beats; dandiya taps fall on eighths 0, 2, 3 of each 6/8 cycle."}
json.dump(meta, open(out.replace(".wav", ".json"), "w"), indent=2)
print(f"{out}  {DUR:.1f}s  drop @ {bt(6):.3f}s  end hit @ {END:.3f}s")
