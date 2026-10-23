# Color correction, grading and finishing

Order: **conform → primary correction → shot matching → secondary → creative look → texture → sharpen**. Correct first, grade second. Judge on a contact sheet of all shots side by side, not one shot at a time.

## 1. Primary correction (per shot)

```bash
# Exposure / contrast / saturation / gamma
eq=brightness=0.02:contrast=1.08:saturation=1.1:gamma=1.0
# White balance (warm shot → cooler): shift blue up, red down slightly
colorbalance=rs=-0.03:bs=0.05           # shadows
colortemperature=temperature=5600:mix=1 # ffmpeg ≥ 5 — direct Kelvin
# Lift/gamma/gain style
colorlevels=rimin=0.02:gimin=0.02:bimin=0.02:rimax=0.98:gimax=0.98:bimax=0.98
# Curves (luma S-curve)
curves=master='0/0 0.25/0.22 0.5/0.5 0.75/0.78 1/1'
```
Targets: skin tones ~ 65–80 IRE-ish midtones, blacks not crushed (check `signalstats` → YMIN ≥ 16 on video range), whites not clipped (YMAX ≤ 235). Use `waveform` / `vectorscope` filters to render scopes if unsure:
```bash
ffmpeg -ss 5 -i in.mp4 -frames:v 1 -vf "split[a][b];[b]waveform=mode=column:intensity=0.2[w];[a][w]vstack" scope.png
```

## 2. Log footage (iPhone ProRes Log, Sony S-Log, etc.)

Apply the camera's technical LUT *first* (`lut3d=file=cam_to_rec709.cube`), then correct. If no LUT: `eq=contrast=1.4:saturation=1.5:gamma=0.85` as a rough normalisation, then adjust by eye.

## 3. Shot matching

- Pick a hero shot. Match every other shot's exposure (midtone), then white balance, then saturation to it.
- Compare with a side-by-side: `[a][b]hstack` of one frame each.
- Phone footage from different phones: match saturation (Samsung oversaturates, iPhone slightly warm). `hue=s=0.9` on the oversaturated one.
- Mixed lighting (daylight + tungsten): neutralise each first, then grade.

## 4. Creative looks (apply the same look to the whole piece)

```bash
# Teal & orange (modern cinematic)
colorbalance=rs=-0.06:gs=0.02:bs=0.12:rh=0.10:gh=0.03:bh=-0.10,eq=saturation=1.05
# Clean commercial / corporate: lifted contrast, neutral
curves=master='0/0 0.5/0.52 1/1',eq=saturation=1.05:contrast=1.05
# Moody / desaturated shadows
eq=saturation=0.8,curves=master='0/0.03 0.3/0.25 1/0.97',colorbalance=bs=0.08
# Warm nostalgic / film
colortemperature=temperature=4800,eq=contrast=0.95:saturation=0.9,curves=r='0/0.02 1/0.98':b='0/0.05 1/0.93'
# Bleach bypass
eq=saturation=0.4:contrast=1.3
# High-key bright social
eq=brightness=0.04:contrast=1.02:saturation=1.15,curves=master='0/0.02 0.5/0.56 1/1'
# Black & white with red filter feel
colorchannelmixer=.4:.4:.2:0:.4:.4:.2:0:.4:.4:.2,eq=contrast=1.15
# Cyberpunk / neon
colorbalance=rs=-0.10:bs=0.20:rh=0.10:gh=-0.10:bh=0.10,eq=saturation=1.3,vibrance=intensity=0.3
```
LUTs: `.cube` via `lut3d=file=look.cube:interp=tetrahedral`. Apply at reduced strength by blending: `split[a][b];[b]lut3d=look.cube[l];[a][l]blend=all_mode=normal:all_opacity=0.6`.

Skin protection: use `vibrance=intensity=0.25` (boosts weak colours, protects skin) instead of global saturation.

## 5. Secondary (selective)

- Sky: `selectivecolor=cyans=-0.1:blues=0.1:0.05:-0.1` or hue-keyed `colorkey`/`chromakey` mask → `maskedmerge`.
- Skin warmth: `selectivecolor=reds=0:0.05:0.05:0:yellows=0:0:0.05:0`.
- Vignette: `vignette=PI/5` (subtle) or `vignette=PI/4:mode=backward`.

## 6. Texture and finish

```bash
noise=alls=8:allf=t+u          # fine film grain (6–12). Add last, before sharpen
unsharp=5:5:0.6:5:5:0.0        # delivery sharpen; never above 1.0 amount
gblur=sigma=0.5                 # anti-aliasing for over-sharp phone footage before grading
```
Letterbox/cinematic bars: `pad=iw:iw*9/16*1.185:0:(oh-ih)/2` on 16:9 → 2.39:1 inside the frame, or `drawbox` black bars. Only for pieces that *mean* cinematic.

## 7. Repair

- Stabilise: `deshake=rx=32:ry=32` (quick) or vidstab two-pass (better). Zoom 3–5% to hide borders.
- Flicker (lights at 50 Hz): `deflicker=size=5`.
- Overexposed: pull `eq=brightness=-0.06:gamma=0.9`; you cannot recover clipped highlights — accept it or crop.
- Rolling-shutter wobble: nothing good in ffmpeg; use `deshake` or recommend a dedicated tool.
- Interlaced source: `yadif=mode=1` (or `bwdif`) *before* anything else.
- Banding after grading: add `noise=alls=4` or dither via `format=yuv420p10le` intermediate.

## 8. Aspect ratio conversions (with intent)

- 16:9 → 9:16 vertical: `crop=ih*9/16:ih` centred, or animated `crop` tracking the subject (`x='min(max(0,SUBJECT_X-ow/2),iw-ow)'`); or blurred-bg pillar: `split[bg][fg];[bg]scale=1080:1920,boxblur=20[bgb];[fg]scale=1080:-2[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2`.
- 9:16 → 16:9: blurred bg sideways, same idea.
- 4:3 → 16:9: crop 25% top/bottom — only if the composition allows; else pillar.
- Always `scale=...:flags=lanczos` for downscales, `bicubic`/`spline` for upscales; `-sws_flags lanczos+accurate_rnd`.

## 9. Colour management for delivery

- Social and web: BT.709, `-pix_fmt yuv420p`, tag it: `-color_primaries bt709 -color_trc bt709 -colorspace bt709`.
- HDR source (iPhone HLG/Dolby Vision) → SDR: `zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p` (needs zimg in ffmpeg, which Homebrew includes). Without tonemapping, HDR footage looks washed out on SDR platforms.
- Never deliver `yuv444p`/`yuv422p` to social — many players show green/black.
