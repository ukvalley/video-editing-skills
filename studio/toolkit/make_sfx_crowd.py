"""Crowd ambience SFX -> assets/sfx/ : applause.wav (3 s swell), applause_short.wav (1.2 s), crowd_murmur.wav (6 s room tone).
Applause = hundreds of individual synthesized hand-claps (band-passed noise bursts with random pitch/level/pan) at a
density envelope, plus a little room reverb. Replace with real recordings of the same name to upgrade everywhere.
"""
import os, wave
import numpy as np

SR = 48000
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/sfx")
rng = np.random.default_rng(21)


def fftf(x, lo=None, hi=None):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if hi: g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if lo: g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X * g, len(x))


def save(name, st, peak=0.8):
    st = st / (np.max(np.abs(st)) + 1e-9) * peak
    w = wave.open(f"{OUT}/{name}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close(); print("sfx ->", name)


# a small bank of clap transients (different hand shapes = different band centres)
BANK = []
for k in range(24):
    n = int(SR * 0.05); t = np.arange(n) / SR
    x = rng.standard_normal(n) * np.exp(-t * rng.uniform(90, 160))
    c = rng.uniform(900, 2600)
    BANK.append(fftf(x, c * 0.5, c * 2.2))


def applause(dur, density_peak=70, attack=0.4, release=1.2):
    n = int(SR * dur); L = np.zeros(n); R = np.zeros(n); t = np.arange(n) / SR
    dens = density_peak * np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, dur - t) / release)
    # each clapper claps at ~4-6 Hz; emulate the aggregate with a Poisson process
    for i in range(0, n, int(SR * 0.005)):
        k = rng.poisson(dens[i] * 0.005)
        for _ in range(k):
            c = BANK[rng.integers(len(BANK))]; j = i + rng.integers(int(SR * 0.005)); m = min(len(c), n - j)
            if m <= 0: continue
            g = rng.uniform(0.2, 1.0); p = rng.uniform(0, 1)
            L[j:j + m] += c[:m] * g * (1 - p); R[j:j + m] += c[:m] * g * p
    ir = rng.standard_normal(int(SR * 0.6)) * np.exp(-np.arange(int(SR * 0.6)) / SR * 9)
    L = L + np.convolve(L, ir * 0.02)[:n]; R = R + np.convolve(R, ir[::-1] * 0.02)[:n]
    return np.stack([L, R], 1)


def murmur(dur):
    n = int(SR * dur); t = np.arange(n) / SR; out = np.zeros((n, 2))
    for ch in range(2):
        x = np.zeros(n)
        for v in range(14):  # 14 'voices': noise through moving formant bands, syllable-rate amplitude
            f1 = rng.uniform(350, 800); f2 = rng.uniform(1100, 2200)
            src = rng.standard_normal(n)
            y = fftf(src, f1 * 0.7, f1 * 1.3) + 0.5 * fftf(src, f2 * 0.8, f2 * 1.2)
            syl = (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(3, 5.5) * t + rng.uniform(0, 6))) ** 2
            phrase = (np.sin(2 * np.pi * rng.uniform(0.15, 0.4) * t + rng.uniform(0, 6)) > -0.2).astype(float)
            x += y * syl * fftf(phrase, hi=8)
        out[:, ch] = fftf(x, 150, 3500)
    fade = np.minimum(1, t / 0.5) * np.minimum(1, (dur - t) / 0.5)
    return out * fade[:, None]


save("applause", applause(3.0))
save("applause_short", applause(1.2, 55, 0.15, 0.7))
save("crowd_murmur", murmur(6.0), 0.6)
