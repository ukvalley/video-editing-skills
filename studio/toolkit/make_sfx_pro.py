"""Advanced SFX pack -> assets/sfx/ (adds to the basic pack from make_sfx.py).
Layered synthesis with stereo width and convolution reverb tails, so hits feel 'produced', not beepy.
Replace any file with a real sample of the same name to upgrade it everywhere.
"""
import os, wave
import numpy as np

SR = 48000
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/sfx")
rng = np.random.default_rng(11)


def t(d):
    return np.arange(int(SR * d)) / SR


def norm(x, peak=0.89):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def save(name, st):
    if st.ndim == 1:
        st = np.stack([st, st], 1)
    st = norm(st)
    w = wave.open(f"{OUT}/{name}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()


def svf_sweep(x, f, q=2.0, mode="bp"):
    """state-variable filter with per-sample cutoff array f"""
    out = np.zeros_like(x); lp = bp = 0.0
    F = 2 * np.sin(np.pi * np.clip(f, 20, SR / 2.5) / SR)
    for i in range(len(x)):
        hp = x[i] - lp - bp / q; bp += F[i] * hp; lp += F[i] * bp
        out[i] = bp if mode == "bp" else (lp if mode == "lp" else hp)
    return out


def reverb(x, decay=1.2, mix=0.3, predelay=0.012, bright=6000):
    """stereo convolution reverb with decorrelated exponentially-decaying noise IRs"""
    n = int(SR * decay); tt = np.arange(n) / SR
    outs = []
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-tt * 6.9 / decay)
        ir = svf_sweep(ir, np.full(n, bright), 0.7, "lp")
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir]); ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        wet = np.convolve(x, ir)[: len(x) + n]
        dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
        outs.append(dry * (1 - mix) + wet * mix * 2.2)
    return np.stack(outs, 1)


def pan_sweep(x, a=-0.8, b=0.8):
    p = np.linspace(a, b, len(x))
    return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], 1) * 1.4


def tone(f, d, k):
    tt = t(d); return np.sin(2 * np.pi * np.cumsum(np.broadcast_to(f, tt.shape)) / SR) * np.exp(-tt * k)


# whoosh_long: doppler-ish sweep, two noise layers, L->R, airy tail
d = 0.95; tt = t(d)
f = 250 + 4200 * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 2
x = svf_sweep(rng.standard_normal(len(tt)), f, 2.2) + 0.5 * svf_sweep(rng.standard_normal(len(tt)), f * 1.8, 4)
x *= np.sin(np.pi * tt / d) ** 3
save("whoosh_long", np.pad(pan_sweep(x), ((0, int(0.6 * SR)), (0, 0))) * 0.8 + reverb(x, 0.6, 0.25) * 0.4)  # dry panned sweep + airy tail

# whoosh_fast: tight 0.28 s swipe
d = 0.28; tt = t(d); f = np.geomspace(600, 7000, len(tt))
x = svf_sweep(rng.standard_normal(len(tt)), f, 1.6) * np.sin(np.pi * tt / d) ** 2
save("whoosh_fast", pan_sweep(x, -0.5, 0.6))

# sub_drop: 808 pitch drop + soft saturation, for section openers
d = 1.4; tt = t(d); f = 35 + 75 * np.exp(-tt * 5)
x = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.2)); x[:200] *= np.linspace(0, 1, 200)
save("sub_drop", x)

# boom_hit: cinematic hit = sub + noise burst + metallic ring, big room
d = 2.0; tt = t(d)
sub = np.sin(2 * np.pi * np.cumsum(45 + 60 * np.exp(-tt * 12)) / SR) * np.exp(-tt * 3)
burst = svf_sweep(rng.standard_normal(len(tt)), np.full(len(tt), 1800.0), 0.8) * np.exp(-tt * 18)
ring = sum(a * np.sin(2 * np.pi * fr * tt) * np.exp(-tt * k) for fr, a, k in [(220, .3, 4), (331, .2, 5), (497, .15, 6), (811, .1, 8)])
x = sub * 1.0 + burst * 0.8 + ring * 0.5
save("boom_hit", reverb(x, 2.2, 0.35, bright=4000))

# reverse_swell: reversed reverb'd hit, peaks at the end (place so it ends on the cut)
y = reverb(burst[: int(0.4 * SR)] + 0.4 * ring[: int(0.4 * SR)], 1.6, 0.9, bright=5000)
y = y[::-1]; y *= np.linspace(0, 1, len(y))[:, None] ** 1.5; y[-120:] *= np.linspace(1, 0, 120)[:, None]
save("reverse_swell", y)

# shutter: camera shutter (two mechanical clicks) for zoom punches / freeze frames
d = 0.16; x = np.zeros(int(SR * d))
for st, g in [(0.0, 1.0), (0.045, 0.7)]:
    i = int(st * SR); n = int(0.03 * SR); tt2 = np.arange(n) / SR
    c = svf_sweep(rng.standard_normal(n), np.full(n, 3500.0), 1.2) * np.exp(-tt2 * 160) * g
    x[i:i + n] += c
save("shutter", reverb(x, 0.25, 0.12))

# glitch: digital stutter (repeated slices, bit-crush, pitch jumps)
d = 0.45; base = np.sign(np.sin(2 * np.pi * 180 * t(0.06))) * 0.5 + rng.standard_normal(int(0.06 * SR)) * 0.5
segs = []
for k in range(7):
    s = base.copy(); s = np.round(s * (2 + k % 3)) / (2 + k % 3)
    rate = [1, 2, 0.5, 1.5, 3, 1, 0.75][k]
    idx = (np.arange(int(len(s) / rate)) * rate).astype(int); s = s[idx[idx < len(s)]]
    segs.append(s * (0.9 if k % 2 == 0 else 0.5)); segs.append(np.zeros(int(SR * 0.008)))
x = np.concatenate(segs)[: int(SR * d)]
st = np.stack([x, np.roll(x, 90)], 1)
save("glitch", st)

# coins: cascading metallic pings (money lost)
d = 1.3; x = np.zeros(int(SR * d))
for k in range(9):
    s0 = 0.05 + k * 0.09 + rng.uniform(-0.02, 0.02); n = int(0.5 * SR); tt2 = np.arange(n) / SR
    f0 = rng.uniform(2800, 4600)
    c = sum(a * np.sin(2 * np.pi * f0 * m * tt2) for m, a in [(1, 1), (1.52, .5), (2.41, .3)]) * np.exp(-tt2 * rng.uniform(9, 16)) * (1 - k * 0.07)
    i = int(s0 * SR); x[i:i + n] += c[: len(x) - i]
save("coins", reverb(x, 0.8, 0.25))

# notification: two-tone up chime for checks / positives
x = np.concatenate([tone(1046.5, 0.12, 14) * 0.8, tone(1568, 0.6, 7)])
x += 0.3 * np.concatenate([tone(2093, 0.12, 20), tone(3136, 0.6, 10)])
save("notification", reverb(x, 0.9, 0.25))

# success: major arpeggio (C E G C) shimmer
x = np.zeros(int(SR * 1.3))
for k, fr in enumerate([523.25, 659.25, 783.99, 1046.5]):
    s = tone(fr, 0.9, 5) + 0.35 * tone(fr * 2, 0.9, 8); i = int(k * 0.07 * SR); x[i:i + len(s)] += s[: len(x) - i]
save("success", reverb(x, 1.4, 0.3))

# ui_click: soft UI tap
x = tone(1800, 0.05, 120) * 0.7 + svf_sweep(rng.standard_normal(int(0.05 * SR)), np.full(int(0.05 * SR), 5000.0), 1) * np.exp(-t(0.05) * 300)
save("ui_click", x)

# typing: 10 keyboard clicks
d = 1.0; x = np.zeros(int(SR * d))
for k in range(10):
    i = int((0.04 + k * 0.085 + rng.uniform(-0.015, 0.015)) * SR); n = int(0.03 * SR)
    c = svf_sweep(rng.standard_normal(n), np.full(n, rng.uniform(2500, 4000)), 1.5) * np.exp(-np.arange(n) / SR * 220)
    x[i:i + n] += c * rng.uniform(0.6, 1)
save("typing", reverb(x, 0.3, 0.1))

# tension_drone: 4 s low drone with slow beating, for problem sections
d = 4.0; tt = t(d)
x = sum(np.sin(2 * np.pi * f * tt) for f in [55, 55.6, 82.4, 110.3]) * 0.25
x = svf_sweep(x + 0.05 * rng.standard_normal(len(tt)), 300 + 200 * np.sin(2 * np.pi * 0.25 * tt), 1.0, "lp")
x *= np.minimum(1, tt / 0.8) * np.minimum(1, (d - tt) / 0.8)
save("tension_drone", reverb(x, 1.5, 0.3, bright=2000))

# swipe_up: short rising air for text entering
d = 0.35; tt = t(d); x = svf_sweep(rng.standard_normal(len(tt)), np.geomspace(800, 9000, len(tt)), 1.8) * (tt / d) ** 1.5 * np.exp(-np.maximum(0, tt - 0.28) * 60)
save("swipe_up", x)

print("advanced SFX written to", OUT)
