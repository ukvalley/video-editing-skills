#!/usr/bin/env python3
"""Detect beats, BPM and downbeats in a music file (ffmpeg decode + numpy onset analysis).

Usage:
  python3 beat_detect.py music.mp3 [--out beats.json] [--start 0] [--end 60] [--min-bpm 70] [--max-bpm 180]
                                   [--grid beats|bars|half] [--quantize]

Output JSON: {"bpm": 124.0, "first_beat": 0.48, "beats": [...], "downbeats": [...], "onsets": [...], "duration": 183.2}

--quantize snaps the beat list to a perfect grid from the estimated BPM (use for electronic music);
without it, beats follow the detected onsets (better for live/acoustic music).
"""
import argparse
import json
import subprocess
import sys

try:
    import numpy as np
except ImportError:
    sys.exit("numpy required: pip3 install numpy")

from _common import require, media_info

SR = 22050
HOP = 256  # ~11.6 ms


def decode_mono(path, start=0.0, end=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path]
    if start:
        cmd += ["-ss", str(start)]
    if end:
        cmd += ["-to", str(end)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_envelope(y):
    """Spectral flux onset strength, log-compressed, per hop."""
    n_fft = 1024
    win = np.hanning(n_fft).astype(np.float32)
    n_frames = max(1, (len(y) - n_fft) // HOP)
    idx = np.arange(n_fft)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = y[idx] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    # log compression; combine a full-band flux with a separately-normalised low band (kick/snare)
    # so the beat follows the drums rather than hi-hats/cymbals
    freqs = np.fft.rfftfreq(n_fft, 1 / SR)
    logmag = np.log1p(mag * 10)
    d = np.maximum(np.diff(logmag, axis=0, prepend=logmag[:1]), 0)
    low = (freqs >= 40) & (freqs <= 300)
    f_full = d.sum(axis=1)
    f_low = d[:, low].sum(axis=1)
    f_full /= (f_full.max() + 1e-9)
    f_low /= (f_low.max() + 1e-9)
    flux = f_full + 1.5 * f_low
    # local mean subtraction (adaptive) and normalise
    k = 16
    ker = np.ones(k) / k
    local = np.convolve(flux, ker, mode="same")
    env = np.maximum(flux - local, 0)
    if env.max() > 0:
        env /= env.max()
    return env


def estimate_bpm(env, min_bpm, max_bpm):
    fps = SR / HOP
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    ac /= (ac[0] + 1e-9)
    min_lag = int(fps * 60 / max_bpm)
    max_lag = int(fps * 60 / min_bpm)
    seg = ac[min_lag:max_lag]
    # prefer lags near 120 bpm mildly (log-gaussian prior) to resolve octave errors
    lags = np.arange(min_lag, max_lag)
    bpms = 60 * fps / lags
    prior = np.exp(-0.5 * ((np.log2(bpms / 120.0)) / 0.9) ** 2)
    score = seg * prior
    best = lags[int(np.argmax(score))]
    bpm = 60 * fps / best
    # refine with parabolic interpolation
    i = int(np.argmax(score))
    if 0 < i < len(score) - 1:
        a, b, c = score[i - 1], score[i], score[i + 1]
        denom = (a - 2 * b + c)
        if denom != 0:
            shift = 0.5 * (a - c) / denom
            bpm = 60 * fps / (best + shift)
    return float(bpm)


def pick_peaks(env, period_frames):
    """Greedy peak picking with a minimum distance ~0.6 beat period."""
    min_dist = max(2, int(period_frames * 0.6))
    thr = max(0.08, float(np.percentile(env, 70)) * 0.5)
    peaks = []
    i = 0
    n = len(env)
    while i < n:
        if env[i] > thr and env[i] == env[max(0, i - 3):i + 4].max():
            peaks.append(i)
            i += min_dist
        else:
            i += 1
    return np.array(peaks)


def track_beats(env, bpm, quantize=False):
    fps = SR / HOP
    period = fps * 60 / bpm
    onsets = pick_peaks(env, period)
    if len(onsets) == 0:
        return np.array([]), np.array([])
    # find phase: the offset (0..period) that maximises onset energy on the grid
    best_phase, best_score = 0.0, -1
    for ph in np.linspace(0, period, 32, endpoint=False):
        grid = np.arange(ph, len(env), period)
        gi = np.clip(grid.astype(int), 0, len(env) - 1)
        s = env[gi].sum()
        if s > best_score:
            best_score, best_phase = s, ph
    grid = np.arange(best_phase, len(env), period)
    if quantize:
        beats = grid
    else:
        # snap each grid point to nearest strong onset within 20% of a period, else keep grid
        beats = []
        for g in grid:
            win = onsets[np.abs(onsets - g) < 0.2 * period]
            if len(win):
                beats.append(win[np.argmin(np.abs(win - g))])
            else:
                beats.append(g)
        beats = np.array(beats, dtype=float)
    # downbeats: among 4 possible phases, pick the one with the highest mean onset energy
    gi = np.clip(beats.astype(int), 0, len(env) - 1)
    energies = env[gi]
    best_k, best_e = 0, -1
    for k in range(4):
        e = energies[k::4].mean() if len(energies[k::4]) else 0
        if e > best_e:
            best_e, best_k = e, k
    downbeats = beats[best_k::4]
    return beats / fps, downbeats / fps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--min-bpm", type=float, default=70)
    ap.add_argument("--max-bpm", type=float, default=180)
    ap.add_argument("--quantize", action="store_true")
    a = ap.parse_args()
    require("ffmpeg")
    y = decode_mono(a.file, a.start, a.end)
    if len(y) < SR:
        sys.exit("audio too short")
    env = onset_envelope(y)
    bpm = estimate_bpm(env, a.min_bpm, a.max_bpm)
    beats, downbeats = track_beats(env, bpm, a.quantize)
    fps = SR / HOP
    onsets = pick_peaks(env, fps * 60 / bpm) / fps
    # analysis window centre compensation (frame i spans HOP*i .. HOP*i+1024)
    comp = 512 / SR
    beats, downbeats, onsets = beats + comp, downbeats + comp, onsets + comp
    dur = media_info(a.file)["duration"]
    res = {
        "file": a.file, "bpm": round(bpm, 2), "beat_period": round(60 / bpm, 4),
        "bar_period": round(240 / bpm, 4), "duration": round(dur, 3),
        "first_beat": round(float(beats[0]) + a.start, 3) if len(beats) else None,
        "beats": [round(float(b) + a.start, 3) for b in beats],
        "downbeats": [round(float(b) + a.start, 3) for b in downbeats],
        "onsets": [round(float(o) + a.start, 3) for o in onsets],
    }
    js = json.dumps(res)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(json.dumps(res, indent=1))
        print(f"bpm={res['bpm']} beats={len(res['beats'])} downbeats={len(res['downbeats'])} -> {a.out}", file=sys.stderr)
    else:
        print(js)


if __name__ == "__main__":
    main()
