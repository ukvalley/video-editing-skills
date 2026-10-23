# ffmpeg cheatsheet (tested one-liners)

Conventions: `-y` overwrite, `-hide_banner -loglevel error` for clean logs, `-stats` for progress. Test on `-t 10` first.

## Inspect
```bash
ffprobe -v error -show_format -show_streams -of json in.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,nb_frames,codec_name -of csv=p=0 in.mp4
ffmpeg -i in.mp4 -af ebur128=peak=true -f null -          # loudness summary at end
ffmpeg -i in.mp4 -vf "select='gt(scene,0.35)',showinfo" -f null - 2>&1 | grep pts_time   # scene cuts
ffmpeg -i in.mp4 -af silencedetect=n=-35dB:d=0.5 -f null - 2>&1 | grep silence_
ffmpeg -i in.mp4 -vf blackdetect=d=0.1:pix_th=0.10 -f null -
```

## Trim / cut / concat
```bash
# accurate trim (re-encode)
ffmpeg -i in.mp4 -ss 00:00:05.250 -to 00:00:12.000 -c:v libx264 -crf 18 -c:a aac cut.mp4
# fast keyframe trim (lossless, approximate)
ffmpeg -ss 5 -i in.mp4 -t 7 -c copy rough.mp4
# concat identical-spec files losslessly
printf "file 'a.mp4'\nfile 'b.mp4'\n" > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
# concat with re-encode and conform (safe for mixed sources)
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p,setsar=1[v0];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p,setsar=1[v1];[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" out.mp4
# split into segments at times
ffmpeg -i in.mp4 -f segment -segment_times 10,25,40 -c copy -reset_timestamps 1 part%02d.mp4
```

## Resize / crop / rotate / stabilise
```bash
-vf "scale=1920:-2:flags=lanczos"                    # keep aspect, even height
-vf "crop=ih*9/16:ih"                                 # 16:9 → 9:16 centre
-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"   # fill vertical
-vf "transpose=1"                                      # rotate 90° CW (2 = CCW)
-vf "hflip" / "vflip"
-vf "deshake"                                          # quick stabilise
ffmpeg -i in.mp4 -vf vidstabdetect=shakiness=6:result=t.trf -f null - && ffmpeg -i in.mp4 -vf "vidstabtransform=input=t.trf:smoothing=30:zoom=4,unsharp=5:5:0.5" stab.mp4
```

## Audio
```bash
ffmpeg -i in.mp4 -vn -c:a pcm_s16le -ar 48000 audio.wav       # extract
ffmpeg -i in.mp4 -i music.mp3 -map 0:v -map 1:a -shortest out.mp4   # replace audio
ffmpeg -i in.mp4 -i vo.wav -filter_complex "[0:a][1:a]amix=inputs=2:normalize=0" ...   # mix
ffmpeg -i in.mp4 -af "volume=-6dB" ...
ffmpeg -i in.mp4 -af "afade=t=in:d=0.5,afade=t=out:st=28:d=1" ...
ffmpeg -i in.mp4 -af "loudnorm=I=-14:TP=-1:LRA=11" ...        # quick single-pass (use script for 2-pass)
ffmpeg -i in.mp4 -itsoffset 0.12 -i in.mp4 -map 0:v -map 1:a -c copy synced.mp4   # delay audio 120 ms
ffmpeg -i in.mp4 -af "pan=stereo|c0=c0|c1=c0" ...               # mono left → both
```

## Overlays and text
```bash
-i logo.png -filter_complex "[1:v]scale=120:-1[l];[0:v][l]overlay=W-w-40:40:format=auto"
-vf "drawtext=fontfile=F.ttf:text='Hello':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=h-200:box=1:boxcolor=black@0.5:boxborderw=20:enable='between(t,2,6)'"
-vf "subtitles=in.srt"  /  -vf "ass=in.ass"
-vf "drawbox=x=0:y=ih-6:w='iw*t/30':h=6:color=red@0.9:t=fill"    # progress bar for a 30 s clip
```

## Picture-in-picture / split screen
```bash
[1:v]scale=iw/3:-1[pip];[0:v][pip]overlay=W-w-30:H-h-30
[0:v]scale=960:1080:force_original_aspect_ratio=increase,crop=960:1080[l];[1:v]...[r];[l][r]hstack
```

## Image sequences, stills, GIF
```bash
ffmpeg -i in.mp4 -vf fps=1 frames/%04d.jpg
ffmpeg -loop 1 -i still.jpg -t 5 -vf "scale=1920:1080,zoompan=z='min(zoom+0.0008,1.15)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=25" -pix_fmt yuv420p kenburns.mp4
```

## Generated sources (useful for placeholders and tests)
```bash
ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=2 -f lavfi -i anullsrc=r=48000:cl=stereo -t 2 black.mp4
ffmpeg -f lavfi -i testsrc2=s=1920x1080:r=30:d=5 -f lavfi -i "sine=f=440:d=5" test.mp4
```

## Troubleshooting
- "Too many packets buffered" / drift on concat → conform fps and sample rate; add `-fps_mode cfr`.
- Green/black frames in player → `-pix_fmt yuv420p`.
- `xfade` error "first input link... timebase" → both inputs must have identical size/fps/format and `setsar=1`; apply `fps=` and `format=` before `xfade`.
- `-ss` before `-i` cuts on keyframe → put it after `-i` for accuracy.
- Audio shorter than video after `amix` → `duration=longest`, or `apad` the short one.
- Font not found → absolute `fontfile=` path. In `drawtext` text escape `:` as `\:`, `,` as `\,`, `%` as `\\%` (the graph parser eats one backslash) and replace `'` with `’` to avoid quoting hell — or use the EDL renderer, which escapes for you.
- `boxblur`/`gblur`/`colorbalance` reject `t` expressions → ramp them with several `enable='between(t,a,b)'` steps; `scale`, `crop`, `eq`, `hue`, `drawtext`, `drawbox`, `overlay` accept `t`.
- Timestamps weird after `trim` → always follow with `setpts=PTS-STARTPTS` / `asetpts=PTS-STARTPTS`.
