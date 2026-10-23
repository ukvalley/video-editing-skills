# Speed, time remapping and beat sync

## 1. Constant speed

```bash
# 2x faster (video + audio)
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" out.mp4
# 0.5x slow-mo, naive (duplicates frames — fine for 60fps source → 30fps output)
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=2.0*PTS[v];[0:a]atempo=0.5[a]" ...
```
- `atempo` range is 0.5–2.0 per instance; chain for more (`atempo=2.0,atempo=2.0` = 4×). Above ~3× speech is unintelligible; drop audio or keep only music.
- For slow-mo, prefer dropping the original audio and using music + SFX; slowed dialogue sounds broken.

## 2. True slow-motion (optical flow interpolation)

Native 60/120 fps footage: just retime with `setpts` and output at 30 fps — real frames, perfect result. 30 fps footage slowed 2×+ needs synthetic frames:
```bash
ffmpeg -i in.mp4 -filter:v "setpts=4.0*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" slow.mp4
```
- `minterpolate` is slow (minutes per minute). Apply only to the segment you need (`trim` first).
- Works well on smooth, well-lit motion; artefacts on fast/complex motion (hands, water). If artefacts, fall back to frame blending: `tblend=all_mode=average` or `framerate=fps=60`.
- For a smooth-motion "cinematic 24p look" on 30p: `minterpolate=fps=24` or just `fps=24` with a `-g` of 48.

## 3. Speed ramps (variable speed)

A ramp is a `setpts` expression that changes the rate over time. Use a smooth curve (ease-in/out), never a step.

Concept: output PTS = integral of (1/speed). Simplest robust approach: split the clip into segments, apply constant speeds per segment with short crossfades (what `edl_render.py` does for `"speed": [[0,1.0],[2.0,4.0],[2.5,1.0]]` — pairs of `[clip_time, speed]`), or use an expression:

```bash
# Ramp from 1x to 4x between t=2 and t=3 (clip time), then 4x. N = frame number, TB = timebase
# Speed s(t) = 1 + 3*smoothstep((t-2)/1). Output time = ∫ 1/s(t) dt — approximate with a lookup via 'if' chain for 3-4 keyframes.
```
Expressions with integrals are painful; use the segment approach for anything with more than 2 keyframes, with `minterpolate` on slow segments and `tblend` on fast ones for motion blur.

**Ramp recipes**
- **Hit-ramp** (common in reels): 1× → 0.25× for 0.6 s on the beat → back to 1×. Music `lowpass` sweep during the slow part.
- **Speed-ramp transition**: last 0.4 s of A ramps 1×→5×, first 0.4 s of B ramps 5×→1×, `tblend=average` over the fast parts. Whoosh across.
- **Time-lapse with hold**: 20× through the boring part, ease to 1× for the moment that matters.

Motion blur for fast segments makes ramps read as intentional:
```bash
tblend=all_mode=average,tblend=all_mode=average     # 2 passes ≈ 180° shutter feel at high speed
```

## 4. Time-lapse / hyperlapse

```bash
ffmpeg -i in.mp4 -vf "setpts=PTS/20,tblend=all_mode=average,framestep=1" -an tl.mp4
# From photos:
ffmpeg -framerate 24 -pattern_type glob -i 'img/*.jpg' -vf "scale=3840:-2,deflicker" tl.mp4
```
Stabilise hyperlapses: two-pass `vidstabdetect` → `vidstabtransform=smoothing=30:zoom=5` (needs libvidstab; `brew install ffmpeg` has it) or `deshake`.

## 5. Freeze frame

```bash
# freeze at t=5 for 2 seconds
ffmpeg -i in.mp4 -filter_complex "
[0:v]trim=end=5,setpts=PTS-STARTPTS[a];
[0:v]trim=start=5:end=5.04,setpts=PTS-STARTPTS,loop=loop=60:size=1:start=0,setpts=N/FRAME_RATE/TB[f];
[0:v]trim=start=5,setpts=PTS-STARTPTS[b];
[a][f][b]concat=n=3:v=1:a=0[v]" -map "[v]" out.mp4
```
Pair with a camera-shutter SFX and a punch-in to 105%. Audio: pause music with a tape-stop (`asetrate` ramp) or continue it.

## 6. Reverse

```bash
ffmpeg -i in.mp4 -vf reverse -af areverse out.mp4   # loads whole clip in RAM — trim first
```
Bounce loop (forward then reverse) for reels: concat clip + reversed clip.

## 7. Beat sync workflow

1. `python3 scripts/beat_detect.py music.mp3 --out beats.json` → `{ "bpm": 124.0, "beats": [0.48, 0.97, ...], "downbeats": [0.48, 2.42, ...] }` (downbeats estimated every 4 beats from the strongest onset).
2. Decide the cut grid: every beat (hype), every 2 (energetic), every bar/4 (steady). Mix them: bars in the verse, beats in the chorus.
3. For each grid point, choose a clip and set its duration = gap to the next grid point. In the EDL use `"duration_from": "beats"` or compute explicitly.
4. Place *impacts* (zoom punches, flashes) on downbeats only.
5. Verify visually: `scripts/contact_sheet.sh out.mp4 --every-beat beats.json` draws a sheet with one frame per beat — each frame should be a new shot if you cut on every beat.

Tempo-matching a clip's *motion* to the music (e.g., a walk cycle to BPM): measure the motion's period from the footage (frames between repeats via contact sheet), then `setpts` = motion_period / beat_period.

## 8. Frame-rate conversion (conform)

- 29.97 → 25 or 24: `-r 24` drops frames (judder on pans); `minterpolate=fps=24` is smooth but slow; `fps=24` with `-fps_mode cfr` is the pragmatic default.
- Variable frame rate (phones): always `-fps_mode cfr -r 30` on ingest, or A/V drift appears across long edits.
- Mixed fps in one edit: pick the majority fps as the project fps; conform the rest with `fps=`.

## 9. Easing expressions (for use inside `setpts`, `scale`, `overlay`, `drawtext`)

With `p = clip((t-T0)/D, 0, 1)`:
- ease-in-out (smoothstep): `p*p*(3-2*p)`
- ease-out cubic: `1-pow(1-p,3)`
- ease-in cubic: `p*p*p`
- overshoot (bounce): `1+2.7*pow(p-1,3)+1.7*pow(p-1,2)`

ffmpeg syntax, e.g. scale for a punch-in 1.0→1.08 over 0.4 s starting at 2 s:
`scale='iw*(1+0.08*(1-pow(1-clip((t-2)/0.4,0,1),3)))':-1:eval=frame,crop=1920:1080`
