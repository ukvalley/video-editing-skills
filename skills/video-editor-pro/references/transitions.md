# Transitions library

Default is the hard cut. Use a transition when it carries meaning: time jump, place change, energy spike, section break. Every transition gets a sound (see `sound-design.md` → SFX map). Keep handles: both clips need ≥ transition-duration of extra frames.

All examples assume clips are conformed (same size, fps, `yuv420p`, 48 kHz stereo). `edl_render.py` applies these by name; the raw ffmpeg forms are below for custom work.

## A. Built-in `xfade` (two inputs, `offset` = when in clip A the transition starts)

```bash
ffmpeg -i a.mp4 -i b.mp4 -filter_complex \
 "[0:v][1:v]xfade=transition=NAME:duration=0.5:offset=4.5[v]; \
  [0:a][1:a]acrossfade=d=0.5:c1=tri:c2=tri[a]" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac -b:a 192k out.mp4
```

Common `NAME` values and when they fit:

| Name | Feel | Use for |
|---|---|---|
| `fade` | classic dissolve | time passing, soft content |
| `fadeblack` / `fadewhite` | dip to black/white | chapter breaks; white = flash/bright moments |
| `dissolve` | noisy dissolve | gritty/analog looks |
| `wipeleft/right/up/down` | hard wipe | retro, presentations |
| `slideleft/right/up/down` | push | UI-style sequences, before/after |
| `smoothleft/right/up/down` | soft-edged wipe | gentle scene change |
| `circleopen/circleclose` | iris | playful, retro |
| `radial` | clock wipe | time passing (literal) |
| `zoomin` | zoom crossfade | reveals, energy |
| `pixelize` | pixel dissolve | tech/game content |
| `hblur` | horizontal blur | fast motion scene change |
| `squeezev/squeezeh` | squeeze | stylised |
| `fadegrays` | through grayscale | flashback |
| `hlslice/vuslice/...` | slice wipes | editorial/dynamic |
| `diagtl/diagtr/...` | diagonal | sports/promo |

Durations: 0.2–0.4 s for energetic content; 0.5–1.0 s for emotional dissolves; 1.5 s+ only for very slow pieces. Match `acrossfade` duration to the video.

## B. Editor-grade recipes (built from filters)

### 1. Whip pan (the Premiere/CapCut "swish")
Blur-and-slide out of A, blur-and-slide into B. Pair with a whoosh SFX.
```bash
# D = 0.3 transition, offA = clip A length - 0.3
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "
[0:v]split[a0][a1];
[a1]trim=start=OFFA,setpts=PTS-STARTPTS,
    boxblur=luma_radius='min(40,40*(t/0.3))':luma_power=2,
    crop=iw:ih:'(iw*0.6)*(t/0.3)':0[aout];
[1:v]split[b0][b1];
[b1]trim=end=0.3,setpts=PTS-STARTPTS,
    boxblur=luma_radius='max(0,40*(1-t/0.3))':luma_power=2[bin];
[a0]trim=end=OFFA,setpts=PTS-STARTPTS[ahead];
[b0]trim=start=0.3,setpts=PTS-STARTPTS[btail];
[aout][bin]xfade=transition=slideleft:duration=0.3:offset=0[mid];
[ahead][mid][btail]concat=n=3:v=1:a=0[v]" -map "[v]" out.mp4
```
Simpler, nearly identical look: `xfade=transition=slideleft` with `boxblur` applied to both clips' boundary regions — that's what `edl_render.py` does for `"transition": "whip_left"` (also `whip_right/up/down`).

### 2. Zoom punch / zoom transition
Fast scale-up on A's last frames and scale-down into B. Pair with a sub-bass impact.
```bash
# zoom out of A over last 0.25 s (scale 1→1.5), B zooms in from 1.5→1
[0:v]scale='iw*(1+0.5*clip((t-OFFA)/0.25,0,1))':-1:eval=frame,crop=W:H[za];
[1:v]scale='iw*(1.5-0.5*clip(t/0.25,0,1))':-1:eval=frame,crop=W:H[zb];
[za][zb]xfade=transition=fade:duration=0.12:offset=OFFA
```
`edl_render.py`: `"transition": "zoom_punch"`.

### 3. Luma / light-leak flash
Dip to white for 2–4 frames with a slight bloom. Great for "flash" cuts to the beat.
```bash
xfade=transition=fadewhite:duration=0.15:offset=OFFA
```
For a warm leak instead of pure white, overlay a light-leak clip (orange/pink gradient) with `blend=all_mode=screen` across the cut. `edl_render.py`: `"flash"` / `"flash_warm"`.

### 4. Glitch / datamosh-style
RGB split + slice displacement + noise for 4–8 frames at the cut.
```bash
[v]split=3[r][g][b];
[r]lutrgb=g=0:b=0,crop=iw:ih:'8*sin(t*90)':0[r2];
[b]lutrgb=r=0:g=0,crop=iw:ih:'-8*sin(t*90)':0[b2];
[g]lutrgb=r=0:b=0[g2];
[r2][g2]blend=all_mode=addition[rg];[rg][b2]blend=all_mode=addition,noise=alls=30:allf=t
```
Apply with `enable='between(t,OFFA-0.1,OFFA+0.1)'`. `edl_render.py`: `"glitch"`. Pair with a digital stutter SFX.

### 5. Film burn / dip through grain
`fadeblack` 0.3 s with `noise=alls=40:allf=t+u` enabled across the window and a slight `eq=brightness=0.1`. `edl_render.py`: `"film_burn"`.

### 6. Speed-ramp through the cut (the "smooth seamless" transition)
Speed A up 1×→4× into the cut, B starts 4×→1×, with a 4-frame motion-blur dissolve. The motion hides the cut. Needs `minterpolate` for the blur to look real — see `speed-and-time.md`. `edl_render.py`: `"speed_ramp"` (uses setpts curve + tblend).

### 7. Mask / shape wipe with soft edge
Use `geq` or an alpha PNG shape sequence as the wipe mask with `maskedmerge`:
```bash
[mask]format=gray,boxblur=20[m];[a][b][m]maskedmerge
```
Animate the mask by `scale`/`crop` on a static shape, or render the mask with `geq` (e.g. circle: `geq='if(lt((X-W/2)^2+(Y-H/2)^2,(T*R)^2),255,0)'`).

### 8. Match-cut dissolve (frame-blended)
`xfade=transition=fade:duration=0.08` — 2 frames. Reads as a hard cut but removes the "snap" when two shots nearly match. Good for jump cuts in talking-head.

### 9. Push with parallax
`slideleft` but the outgoing clip moves at 60% of the speed of the incoming one — gives depth. Build with two `overlay` layers with `x` expressions on `t`.

### 10. Blur dissolve
Both clips blur to 30 px at the midpoint: `gblur=sigma='30*sin(PI*(t-OFF)/D)'` enabled across the window, combined with `fade`.

## C. Intro / outro treatments

- **Cold open**: no transition, start on action, title appears 1–2 s in.
- **Logo sting**: animate scale 0.8→1 with ease-out over 0.4 s, hold 1.2 s, fade 0.3 s. Whoosh-in + soft hit.
- **End card**: last shot continues under a 20% darkened overlay, CTA text slides up with ease. Never black-screen the last 3 s.

## D. Rules

- A transition between two shots of the **same** scene is almost always wrong. Use a hard cut or jump-punch.
- Don't mix transition styles randomly; pick 1–2 for the whole piece.
- Transition *in time with the music*: start the transition so it completes on the beat, not starts on it.
- Every non-cut transition gets an SFX, mixed 6–10 dB under the music peak.
- Keep durations short. Modern pacing: 0.15–0.4 s.
