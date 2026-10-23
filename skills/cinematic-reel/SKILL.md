---
name: cinematic-reel
description: Edit raw camera footage into a cinematic, beat-synced vertical reel (Instagram Reels / YouTube Shorts) using FFmpeg — e.g. car delivery, event, product or travel reels. Use when the user asks for a cinematic reel, car delivery reel, beat-sync edit or B-roll montage from their clips.
---

# Cinematic Reel Editor

Turn a folder of raw clips + a music track into a 15–45 s, 9:16, beat-synced cinematic reel. All editing is done with FFmpeg from the command line. The plan lives in an editable edit list (`edl.json`) so any change can be re-rendered without starting over.

## 0. Hard rules
- NEVER modify or delete anything in `raw/`. Write all outputs to `work/` and `out/`.
- Music must be supplied by the user (licensed / royalty-free). If `music/` is empty, ask for a track — do not download copyrighted music.
- Show the user the shot plan (step 4) and get a go-ahead before the final render.
- Prefer hard cuts on beats. Use transitions sparingly (max 2–3 per reel).

## 1. Check prerequisites
```bash
ffmpeg -version && ffprobe -version
python3 -c "import librosa, numpy" || pip install librosa numpy soundfile
```
If FFmpeg is missing, tell the user to install it (Windows: `winget install ffmpeg`, Mac: `brew install ffmpeg`, Linux: `sudo apt install ffmpeg`) and stop.

## 2. Folder layout
```
project/
  raw/      # camera clips (read-only)
  music/    # one music track
  luts/     # optional .cube LUT for color grade
  work/     # thumbnails, segments, edl.json, beats.json
  out/      # final renders (reel_v1.mp4, reel_v2.mp4 ...)
```

## 3. Inventory and look at the footage
For every clip, record duration, resolution, fps and orientation:
```bash
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate,codec_type -of json raw/CLIP.mp4
```
Make a contact sheet per clip (one frame every 2 s) and VIEW it with the Read tool so you know what is in each shot:
```bash
ffmpeg -y -i raw/CLIP.mp4 -vf "fps=1/2,scale=320:-1,tile=4x3" -frames:v 1 work/thumbs/CLIP.jpg
```
Tag each usable moment: shot type (wide / medium / close-up / detail), subject, motion, quality (sharp, stable, well lit), and whether it is slow-mo capable (source ≥ 50 fps).

## 4. Build the story (shot plan)
Structure every reel as:
1. **Hook (0–2 s)** — the most striking shot. No logo or text intro.
2. **Build-up** — details and anticipation (close-ups, slow motion).
3. **Hero moment** — on the biggest beat / music drop.
4. **Emotion / payoff** — reactions, people, celebration.
5. **Outro (last 2–3 s)** — clean wide shot, optional text or logo, music fade.

Car delivery template (adapt to footage): exterior wide → logo close-up → wheel/headlight details → family walking in (slow-mo) → cover reveal (on the drop) → key handover → reactions/smiles → interior + steering → cake / garland / pooja → first drive away (wide, outro).

Rules: vary shot sizes (never two wides in a row), keep each shot 0.5–2.5 s, use slow motion only for emotional or reveal shots, cut on motion where possible.

## 5. Beat detection
```python
# work/beats.py
import librosa, json, sys
y, sr = librosa.load(sys.argv[1])
tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
beats = librosa.frames_to_time(frames, sr=sr).tolist()
onset = librosa.onset.onset_strength(y=y, sr=sr)
json.dump({"tempo": float(tempo), "beats": beats}, open("work/beats.json", "w"), indent=1)
print(f"tempo {float(tempo):.1f} BPM, {len(beats)} beats")
```
Cut on beats (every beat for fast sections, every 2nd or 4th beat for slow ones). Find the drop (largest energy jump) and put the hero shot there.

## 6. Write the edit list `work/edl.json`
```json
{
  "output": {"w": 1080, "h": 1920, "fps": 30},
  "music": {"file": "music/track.mp3", "start": 12.0, "fade_out": 1.5},
  "grade": {"lut": "luts/teal_orange.cube", "vignette": true},
  "shots": [
    {"id": 1, "src": "raw/C0001.mp4", "in": 4.20, "dur": 1.40, "speed": 1.0, "crop_x": "center", "note": "hook – car wide"},
    {"id": 2, "src": "raw/C0007.mp4", "in": 10.0, "dur": 1.00, "speed": 0.5, "crop_x": "center", "note": "wheel slow-mo"}
  ],
  "transitions": [{"after_shot": 4, "type": "fade", "dur": 0.3}],
  "text": [{"text": "Welcome Home", "start": 18.0, "end": 21.0}]
}
```
`dur` is the length on the timeline. With `speed` 0.5 the source range used is `dur × speed` seconds. Show the user this plan as a simple table (shot, time, description) before rendering.

## 7. Render each shot as a uniform segment
Every segment must have identical resolution, fps, pixel format and no audio, so they join cleanly:
```bash
# landscape source → 9:16 crop, speed, grade
ffmpeg -y -ss IN -t SRC_DUR -i raw/CLIP.mp4 -an -vf "\
setpts=PTS/SPEED,\
scale=-2:1920,crop=1080:1920,\
fps=30,\
lut3d=luts/teal_orange.cube,\
eq=contrast=1.06:saturation=1.10,\
vignette=PI/5,\
format=yuv420p" \
-c:v libx264 -crf 16 -preset medium work/seg_01.mp4
```
- `SRC_DUR = dur × speed`. For slow motion use a high-fps source; avoid `minterpolate` unless asked (slow and artifacts).
- Vertical source: use `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920`.
- No LUT available: use `eq=contrast=1.08:saturation=1.15:gamma=0.98` plus `curves=preset=increase_contrast` for a cinematic look.
- Optional cinematic bars are NOT used in 9:16 reels.

## 8. Join segments
No transitions — concat demuxer:
```bash
printf "file 'seg_%02d.mp4'\n" 1 2 3 ... > work/list.txt
ffmpeg -y -f concat -safe 0 -i work/list.txt -c copy work/video.mp4
```
With a transition between two segments use `xfade` (offset = length of first clip − transition duration):
```bash
ffmpeg -y -i work/seg_04.mp4 -i work/seg_05.mp4 -filter_complex \
"[0][1]xfade=transition=fade:duration=0.3:offset=1.2,format=yuv420p" work/seg_04_05.mp4
```
Each transition shortens the timeline by its duration — re-check beat alignment.

## 9. Music, text, final export
```bash
ffmpeg -y -i work/video.mp4 -ss MUSIC_START -i music/track.mp3 -filter_complex "\
[1:a]afade=t=in:d=0.3,afade=t=out:st=FADE_START:d=1.5,loudnorm=I=-14:TP=-1:LRA=11[a];\
[0:v]drawtext=fontfile=FONT.ttf:text='Welcome Home':fontsize=72:fontcolor=white:\
x=(w-text_w)/2:y=h*0.72:enable='between(t,18,21)':alpha='if(lt(t,18.4),(t-18)/0.4,1)'[v]" \
-map "[v]" -map "[a]" -shortest \
-c:v libx264 -crf 18 -preset slow -profile:v high -pix_fmt yuv420p -r 30 \
-c:a aac -b:a 192k -movflags +faststart out/reel_v1.mp4
```
Find a font file on the machine for `drawtext` (or ask). Keep text minimal, inside the safe area (avoid the top 15% and bottom 25%, where Instagram UI sits).

## 10. Quality check (always)
- `ffprobe out/reel_vN.mp4` → 1080×1920, 30 fps, H.264, AAC, duration as planned.
- Contact sheet of the final reel (`fps=2,scale=270:-1,tile=6x5`) and view it: no black frames, no wrong crops (heads cut off), consistent color.
- Check loudness and that the hero shot lands on the drop.
- Report to the user: duration, shot count, file path, and anything you were unsure about.

## 11. Revisions
Never start over. Edit `work/edl.json` (swap a shot, change `in`/`dur`, speed, text, grade), re-render only the changed segments, re-join and export as the next version (`reel_v2.mp4`). Keep old versions so the user can compare.
