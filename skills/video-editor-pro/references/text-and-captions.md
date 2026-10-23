# Text, titles, captions and motion graphics

## 1. Fonts on macOS

Use a real font file path; don't rely on fontconfig names. Good system choices: `/System/Library/Fonts/Supplemental/Arial Bold.ttf` is *not* good — prefer:
- `/System/Library/Fonts/SFCompact.ttf` / `SFNS.ttf` (San Francisco, modern)
- `/System/Library/Fonts/Supplemental/Futura.ttc`, `Avenir Next.ttc`, `Helvetica Neue.ttc` (`:fontfile=...:` works with .ttc, uses first face)
- `/System/Library/Fonts/Supplemental/Impact.ttf` only for meme style
- User fonts: `~/Library/Fonts/`. Suggest Montserrat / Inter / Bebas Neue / Poppins (Google Fonts, free) for social.

List: `ls /System/Library/Fonts /System/Library/Fonts/Supplemental ~/Library/Fonts | grep -iE "ttf|otf|ttc"`.

## 2. Safe areas and sizing

| Platform | Keep text inside | Body text height | Title height |
|---|---|---|---|
| Reels / TikTok / Shorts (1080×1920) | x: 60–1020, y: 250–1500 (UI covers top 250 & bottom 420) | ≥ 60 px | 100–160 px |
| YouTube 16:9 (1920×1080) | 5% inset; avoid bottom-right (timestamp) | ≥ 44 px | 80–130 px |
| Feed square (1080×1080) | 5% inset | ≥ 50 px | 90–140 px |

Readability: high contrast, 2–4 px stroke or a 60% black box, 4–8 px shadow. Max 2 lines for captions, 6–8 words per line. Test on a phone-sized render.

## 3. Titles with `drawtext` + easing

All animation uses `p=clip((t-T0)/D,0,1)` eased. Example: title slides up from below and fades in over 0.5 s at t=1, holds 3 s, fades out 0.3 s.

```bash
drawtext=fontfile=/path/Montserrat-Bold.ttf:text='BUILD FASTER':fontsize=120:fontcolor=white:
 borderw=0:shadowcolor=black@0.5:shadowx=0:shadowy=6:
 x=(w-text_w)/2:
 y='h*0.75 - 60*(1-pow(1-clip((t-1)/0.5,0,1),3))':
 alpha='clip((t-1)/0.5,0,1)*clip((4.3-t)/0.3,0,1)':
 enable='between(t,1,4.3)'
```
- Letter-spacing isn't native; fake with `text='B U I L D'` or render text as PNG (see §6).
- Two-line titles: two `drawtext` calls, second delayed 0.1 s (stagger = professional).
- Scale animation: `drawtext` can't animate `fontsize` smoothly per frame in older ffmpeg; use `fontsize='110+10*p'` with `expansion=normal` (ffmpeg ≥ 6 supports expressions in fontsize) — if unsupported, render text to PNG and animate with `overlay`+`scale`.
- Background bar behind text: `box=1:boxcolor=black@0.6:boxborderw=24`. Animate the bar width with `drawbox` with `w='maxW*p'` for a wipe-reveal.

## 4. Lower-thirds

Pattern: accent bar slides in (0.3 s ease-out), name fades in 0.1 s after, role 0.2 s after; hold 4 s; reverse out.
```bash
drawbox=x='-8+ (120)*(1-pow(1-clip((t-1)/0.3,0,1),3))-120':y=ih-260:w=8:h=120:color=0xFF6A00@1:t=fill:enable='between(t,1,5.5)',
drawtext=fontfile=F:text='Your Name':fontsize=56:fontcolor=white:x='80+40*(1-(1-pow(1-clip((t-1.1)/0.3,0,1),3)))':y=ih-250:alpha='clip((t-1.1)/0.3,0,1)*clip((5.5-t)/0.3,0,1)',
drawtext=fontfile=F:text='Founder, Your Company':fontsize=36:fontcolor=white@0.85:x=80:y=ih-180:alpha='clip((t-1.3)/0.3,0,1)*clip((5.5-t)/0.3,0,1)'
```
`edl_render.py` has `"lower_third": {"name":..., "role":..., "at":..., "duration":...}` which builds this with the EDL's brand colour and font.

## 5. Captions / subtitles

### Workflow
1. `bash scripts/transcribe.sh in.mp4 --model medium --words` → `in.srt` + `in.words.json` (word-level timestamps).
2. Correct names/terms in the SRT (Whisper gets brand names wrong). Ask the user for a glossary if there are many.
3. Style and burn.

### Burn SRT with styling (fast, static captions)
```bash
ffmpeg -i in.mp4 -vf "subtitles=in.srt:force_style='FontName=Montserrat,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=60,Alignment=2'" out.mp4
```
ASS colours are `&HAABBGGRR` (alpha, blue, green, red). FontSize is in points relative to a 288-line PlayRes unless `PlayResY` is set; set it explicitly in ASS.

### Animated word-by-word captions ("karaoke"/Hormozi style)
Generate an `.ass` file from `in.words.json`: each caption line is a group of 3–5 words; the active word is highlighted with `\k` timing or by overlapping dialogue events with a different colour and a pop (`\fscx110\fscy110\t(0,80,\fscx100\fscy100)`). `scripts/transcribe.sh in.mp4 --ass-style karaoke` produces this directly; `scripts/captions_ass.py words.json out.ass --style karaoke|clean|boxed --font Montserrat --size 64 --highlight &H0000A5FF` rebuilds it from any word-timestamp JSON when you change the look.

Burn: `-vf "ass=in.ass"`. ASS supports: `\pos`, `\move`, `\fad(in,out)`, `\t(transform)`, `\bord`, `\shad`, `\3c` outline colour, `\an5` centre anchor. This is far more capable than `drawtext` and the right tool for any multi-cue text.

Caption rules for social: 1–2 lines, centre-bottom at y≈70–78% of frame, each cue 0.8–2.5 s, no cue shorter than 3 frames, punctuation kept light, emphasis word in brand colour.

### Styling by content type
- Tutorial / corporate: static, 2-line, white on 60% black box, bottom.
- Talking-head short: 3–5-word groups, big bold, centred slightly below mid, current word highlighted.
- Interview: lower-third style, speaker label if multiple.

## 6. Graphics, overlays and PNG/alpha assets

- Overlay a PNG/transparent MOV: `[0:v][1:v]overlay=x:y:enable=...`. Animate with easing in `x`/`y`, and fade via `[1:v]format=rgba,colorchannelmixer=aa='clip((t-1)/0.3,0,1)'`.
- Logo watermark: 4–6% of frame width, 70% opacity, 3% inset top-right or bottom-left.
- Progress bar for shorts: `drawbox=x=0:y=ih-8:w='iw*t/DUR':h=8:color=BRAND:t=fill`.
- Counter / numbers rolling: `drawtext=text='%{eif\:floor(t*25)\:d}'`.
- Timestamp / "day 3": `drawtext` with `box=1` in a corner.
- Arrow/circle highlight: `drawbox` or `drawellipse`-like via PNG; animate scale with `scale='iw*(0.8+0.2*p)'` + overlay.
- Screen recordings: zoom-in on a region with eased `crop`+`scale`, cursor highlight via overlaid PNG at tracked coordinates (ask user for coordinates/timestamps or detect from a click sound).

Rendering complex text to PNG when `drawtext` is limiting (letter-spacing, gradients): use Python Pillow (`pip3 install pillow`), then `overlay`. `scripts/edl_render.py` supports `"image"` layers for exactly this.

## 7. Motion rules for all graphics

- Ease everything; 0.25–0.5 s in, 0.2–0.3 s out. Out is faster than in.
- Stagger elements by 80–150 ms.
- Overshoot for playful brands only.
- Text appears *on* a beat or *on* the spoken word, never arbitrarily.
- Never leave a graphic up more than the time needed to read it twice (≈ words × 0.35 s + 1 s).
