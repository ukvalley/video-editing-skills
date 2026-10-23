# Sound design and mixing

Audience forgives soft picture; it never forgives bad audio. Work in this order: **clean → cut → balance → duck → sweeten (SFX) → master**.

## 1. Signal chain for dialogue / voiceover

```
highpass(80 Hz) → denoise (afftdn) → de-ess → EQ → compressor → gain to −18 LUFS-S → (later) master limiter
```
```bash
ffmpeg -i vo.wav -af "
highpass=f=80,
afftdn=nf=-25:nt=w,
deesser=i=0.4:m=0.5:f=0.5,
equalizer=f=250:t=q:w=1.5:g=-2,
equalizer=f=3000:t=q:w=1:g=2,
acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=4,
loudnorm=I=-18:TP=-2:LRA=9" vo_clean.wav
```
- `afftdn` noise floor: −20 (light) to −35 (heavy). Too strong = underwater voice. Use `nt=w` (white) for hiss, `nt=v` (vinyl) for rumble. For really bad audio suggest a dedicated tool (e.g. RNNoise `arnndn` with a model, or Adobe Enhance Speech); don't over-process.
- Cut 200–300 Hz for boxiness; add 2–4 kHz for presence; roll off >12 kHz if hissy.
- Compressor: 3:1, fast attack, 60–100 ms release, 4–6 dB gain reduction on loud words.
- Record-level target after chain: dialogue at −18 to −14 LUFS short-term, peaks < −6 dBFS before mastering.

## 2. Audio editing rules

- **Micro-fades on every edit**: 5–15 ms. Clicks come from cutting at non-zero crossings. `edl_render.py` adds these automatically; manually: `afade=t=in:d=0.01,afade=t=out:st=END-0.01:d=0.01`.
- **Room tone**: when removing a pause, don't leave digital silence — fill with 1–2 s of room tone looped at the original level. Capture it with `atrim` from a quiet moment in the source.
- **Breaths**: shorten, don't delete (cut 50–70% of each breath). Deleting all breaths sounds robotic.
- **J-cut / L-cut**: offset audio in/out by 0.3–1.0 s relative to picture. In the EDL: `"audio_offset": -0.5`.
- **Silence removal for talking-head**: `scripts/silence_cut.py --threshold -35 --min-silence 0.4 --padding 0.12` — padding keeps natural rhythm. Review the cut list; aggressive settings make speech frantic.

## 3. Music

- Choose tempo to the content: 90–110 BPM for calm/explainers, 120–140 for energy, 140+ for hype montages.
- Trim so the first strong downbeat lands at or before 0.5 s. Find beats with `scripts/beat_detect.py music.mp3` → JSON of beat times and estimated BPM.
- End music on a phrase boundary (every 4 or 8 bars). Compute bar length = 60/BPM × 4. Cut on a bar and fade 0.5–1.0 s, or use a music "stinger"/final hit if available.
- Loop extension: find a bar-aligned loop region and repeat with `aloop` / `concat`; crossfade 50–100 ms at the loop point.
- Edit music to length by cutting on bars, not by time-stretching. If you must stretch: `atempo=0.95..1.05` max (chain two for larger).

## 4. Ducking (music under speech)

Static volume drop is amateur. Use sidechain compression so music dips *with* speech and recovers after.

```bash
ffmpeg -i music.mp3 -i vo.wav -filter_complex "
[1:a]asplit=2[sc][vo];
[0:a][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400:makeup=1:level_sc=1[ducked];
[ducked]volume=-14dB[bed];
[bed][vo]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[a]" -map "[a]" mix.wav
```
- `threshold` 0.01–0.05 (lower = more sensitive), `ratio` 6–12, `attack` 10–30 ms, `release` 300–600 ms (longer = smoother).
- Bed level under speech ≈ −18 to −24 LUFS; when no speech, music can rise to −14 to −12.
- Also useful: `agate` on VO before sidechaining to stop breaths triggering the duck.
- For extra polish, add a `highpass=f=150` *only during ducking* via a parallel chain — reduces masking of the voice.

## 5. SFX map — what sound goes on what

| Visual event | Sound | Level vs music peak |
|---|---|---|
| Whip pan / slide | Whoosh (short, pitched to direction) | −6 dB |
| Zoom punch | Sub thump / soft impact | −4 dB |
| Hard cut on the beat in a montage | Usually nothing — the kick is the sound | — |
| Title appears | Soft whoosh + subtle "tick" or shimmer | −10 dB |
| Text pop (word by word) | Light click/pop per word | −14 dB |
| Build before a reveal | Riser (1–2 bars), cut dead on the reveal | −6 dB rising |
| Reveal / drop | Impact + reverse cymbal before it | −2 dB |
| Glitch | Digital stutter / bit-crush burst | −8 dB |
| Flash / light leak | Shutter / bright "ping" | −10 dB |
| Logo sting | Whoosh-in + deep hit + tail | −3 dB |
| Jump cut | Nothing, or extremely subtle "tick" | −20 dB |
| Slow-motion begins | Low-pass sweep on music (`lowpass` with `enable`), pitch-drop | — |
| Speed ramp up | Riser or pitch-up whoosh | −8 dB |

Alignment: place the *transient* of the SFX on the frame of the event; whooshes start 100–200 ms *before* the cut and peak on it. In the EDL: `"sfx": [{"file": "whoosh.wav", "at": 4.35, "gain_db": -6}]`.

Where to get SFX if the user has none: suggest free libraries (freesound.org, Pixabay, Mixkit, Zapsplat). Never ship silence where a sound is expected — if no file exists, synthesise placeholders:
```bash
# whoosh: filtered pink noise with exponential swell (filter cutoffs can't be time-expressions; shape with fades)
ffmpeg -f lavfi -i "anoisesrc=d=0.4:c=pink:a=0.6" -af "lowpass=f=2500,afade=t=in:d=0.12:curve=exp,afade=t=out:st=0.18:d=0.22" whoosh.wav
# sub impact
ffmpeg -f lavfi -i "sine=f=55:d=0.5" -af "afade=t=out:st=0.05:d=0.45,volume=0.9" impact.wav
# riser (2 s swell; for a pitch sweep render two or three bands and concat)
ffmpeg -f lavfi -i "anoisesrc=d=2:c=white:a=0.3" -af "lowpass=f=3000,afade=t=in:d=1.8:curve=exp" riser.wav
```

## 6. Mixing levels (relative, before master)

| Layer | Target |
|---|---|
| Dialogue / VO | −18 to −14 LUFS short-term, the anchor |
| Music under speech | −30 to −24 LUFS (12–18 dB under VO) |
| Music alone (montage) | −16 to −12 LUFS |
| Ambience / room tone | −40 to −32 LUFS |
| SFX | peaks 2–10 dB under music peak, per table |

Mix with `amix=normalize=0` (so levels you set are honoured) or `amerge`+`pan`. Always `aresample=48000` and `aformat=channel_layouts=stereo` before mixing.

## 7. Mastering

Two-pass `loudnorm` is the professional way (single-pass is less accurate on short clips). `scripts/normalize_audio.sh out.mp4 --target youtube` does: measure → apply `loudnorm` with measured values → `alimiter` at −1 dBTP → verify.

| Platform | Integrated | True peak | LRA |
|---|---|---|---|
| YouTube, Instagram, TikTok, LinkedIn | −14 LUFS | −1 dBTP | ≤ 11 |
| Spotify/podcast | −16 LUFS | −1 dBTP | ≤ 11 |
| Broadcast EU (EBU R128) | −23 LUFS | −1 dBTP | ≤ 15 |
| Broadcast US (ATSC A/85) | −24 LKFS | −2 dBTP | — |
| Cinema / client review | −27 to −24 | −2 | — |

Final chain: `loudnorm=I=-14:TP=-1:LRA=11:measured_I=..:measured_TP=..:measured_LRA=..:measured_thresh=..:linear=true,alimiter=limit=0.89:attack=5:release=50`.

## 8. Stereo and spatial touches

- VO stays dead centre. Music full stereo. SFX panned to motion (`pan` or `stereotools=mpan=`): whoosh-left for a left slide.
- Light reverb on VO only for cinematic pieces: `aecho=0.8:0.6:20:0.15` is a cheap room; prefer none for tutorials.
- Slow-motion sections: `lowpass=f=800` sweep in + `asetrate`/`atempo` pitch drop on the music for a "time stops" feel; return with a riser.

## 9. QC listening pass

1. Any clicks at edits? (listen on headphones)
2. Music ever fighting the voice?
3. Levels consistent between sections?
4. SFX on every transition that needed one, none where a hard cut was enough?
5. No digital silence anywhere (room tone/ambience present)?
6. Integrated loudness and true peak hit the target (`qc.py` reports them)?
