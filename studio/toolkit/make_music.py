"""Generate a royalty-free corporate underscore -> assets/music/<name>.wav
Usage: python3 make_music.py [seconds=70] [bpm=100] [name=underscore_100bpm]
Layers: warm detuned pad, plucked arpeggio, sub bass, soft kick/clap/hats (drums enter at bar 3).
Built to sit 15-20 dB under dialogue and be sidechain-ducked.
"""
import os, sys, wave
import numpy as np

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 70
bpm = float(sys.argv[2]) if len(sys.argv) > 2 else 100
name = sys.argv[3] if len(sys.argv) > 3 else "underscore_100bpm"
rng = np.random.default_rng(5)
beat = 60 / bpm; bar = 4 * beat
N = int(secs * SR); T = np.arange(N) / SR


def midi(n): return 440 * 2 ** ((n - 69) / 12)


def fft_filter(x, lo=None, hi=None):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if hi: g *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if lo: g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X * g, len(x))


def saw(f, tt):
    ph = (f * tt) % 1.0
    return 2 * ph - 1


# chord progression (Am - F - C - G), voicings in MIDI
prog = [[57, 60, 64, 69], [53, 57, 60, 65], [55, 60, 64, 67], [55, 59, 62, 67]]
roots = [45, 41, 48, 43]
padL = np.zeros(N); padR = np.zeros(N); arp = np.zeros(N); bass = np.zeros(N); drums = np.zeros(N)
nbars = int(np.ceil(secs / bar))
for b in range(nbars):
    ch = prog[b % 4]; s0 = int(b * bar * SR); s1 = min(N, int((b + 1) * bar * SR) + int(0.3 * SR))
    if s0 >= N: break
    tt = np.arange(s1 - s0) / SR
    env = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (bar + 0.3 - tt)) / 0.5)
    for n in ch:
        f = midi(n)
        padL[s0:s1] += (saw(f * 0.997, tt) + saw(f * 1.004, tt + 0.13)) * env * 0.12
        padR[s0:s1] += (saw(f * 1.003, tt + 0.07) + saw(f * 0.995, tt + 0.21)) * env * 0.12
    # sub bass: root on beats 1 and 3
    for q in (0, 2):
        i = s0 + int(q * beat * SR); n = int(beat * 1.8 * SR); n = min(n, N - i)
        if n <= 0: continue
        t2 = np.arange(n) / SR
        bass[i:i + n] += np.sin(2 * np.pi * midi(roots[b % 4]) * t2) * np.minimum(1, t2 / 0.01) * np.exp(-t2 * 1.6) * 0.5
    # arpeggio 8ths: chord tones up an octave
    pattern = [0, 1, 2, 3, 2, 1, 2, 3]
    for k in range(8):
        i = s0 + int(k * beat / 2 * SR); n = min(int(0.45 * SR), N - i)
        if n <= 0: continue
        t2 = np.arange(n) / SR; f = midi(ch[pattern[k]] + 12)
        arp[i:i + n] += (np.sin(2 * np.pi * f * t2) + 0.3 * np.sin(4 * np.pi * f * t2)) * np.exp(-t2 * 9) * (0.22 if k % 2 == 0 else 0.15)
    if b >= 2:  # drums
        for q in range(4):
            i = s0 + int(q * beat * SR)
            if i >= N: continue
            if q in (0, 2):
                n = min(int(0.35 * SR), N - i); t2 = np.arange(n) / SR
                drums[i:i + n] += np.sin(2 * np.pi * np.cumsum(50 + 90 * np.exp(-t2 * 30)) / SR) * np.exp(-t2 * 9) * 0.55
            else:
                n = min(int(0.18 * SR), N - i); t2 = np.arange(n) / SR
                drums[i:i + n] += rng.standard_normal(n) * np.exp(-t2 * 28) * 0.18
        for e in range(8):
            i = s0 + int(e * beat / 2 * SR); n = min(int(0.04 * SR), N - i)
            if n > 0: drums[i:i + n] += rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 120) * (0.06 if e % 2 else 0.035)
padL = fft_filter(padL, lo=120, hi=1400); padR = fft_filter(padR, lo=120, hi=1400)
arp = fft_filter(arp, lo=300, hi=6000); bass = fft_filter(bass, hi=200)
hats = fft_filter(drums, lo=5000); kick = fft_filter(drums, hi=5000)
# simple stereo delay on the arp
dl = int(beat * 0.75 * SR); arpL = arp + 0.35 * np.concatenate([np.zeros(dl), arp[:-dl]]); arpR = arp + 0.35 * np.concatenate([np.zeros(dl // 2), arp[:-(dl // 2)]])
L = padL + arpL * 0.9 + bass + kick + hats * 0.8
R = padR + arpR * 0.9 + bass + kick + hats * 1.0
fade = np.minimum(1, T / 1.5) * np.minimum(1, (secs - T) / 2.0)
st = np.stack([L * fade, R * fade], 1); st = np.tanh(st / np.max(np.abs(st)) * 1.2) * 0.85
os.makedirs(f"{ROOT}/assets/music", exist_ok=True)
w = wave.open(f"{ROOT}/assets/music/{name}.wav", "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()
print(f"music -> assets/music/{name}.wav ({secs:.0f}s, {bpm:.0f} bpm, bar={bar:.3f}s)")
