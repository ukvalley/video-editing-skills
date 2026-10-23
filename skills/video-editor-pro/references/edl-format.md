# EDL format for `scripts/edl_render.py`

Describe the edit as JSON, render with:
```bash
python3 scripts/edl_render.py edit.json            # full render
python3 scripts/edl_render.py edit.json --preview  # fast 720p proxy (videotoolbox/ultrafast)
python3 scripts/edl_render.py edit.json --dry-run  # print the ffmpeg commands only
```
All times are seconds (floats). Timeline time = output time; clip time = time within the source file.

```jsonc
{
  "output": {
    "path": "out/final.mp4",
    "width": 1080, "height": 1920, "fps": 30,     // project spec; every clip is conformed to this
    "crf": 18,                                     // or "bitrate": "10M"
    "loudness": "youtube"                          // youtube|social|podcast|broadcast|none → -14/-14/-16/-23 LUFS
  },
  "work_dir": "work",                              // intermediates (default: work/)
  "font": "/Users/me/Library/Fonts/Montserrat-Bold.ttf",   // default font for text/lower-thirds
  "brand_color": "#FF6A00",

  "clips": [                                       // in timeline order
    {
      "src": "footage/a.mp4",
      "in": 2.0, "out": 5.5,                       // source in/out (out omitted = to end)
      "speed": 1.0,                                // number, or ramp keyframes [[clip_t, speed], ...] e.g. [[0,1],[1.5,0.25],[2.1,1]]
      "fit": "cover",                              // cover (crop to fill) | contain (pad) | stretch; default cover
      "crop_focus": "center",                      // center|left|right|top|bottom — where to keep when cover-cropping
      "zoom": [1.0, 1.06],                         // optional slow Ken-Burns punch-in from→to over the clip
      "filters": "eq=contrast=1.05",               // extra per-clip video filter chain (after conform)
      "mute": false, "volume_db": 0,               // clip's own audio
      "audio_offset": 0,                           // seconds; negative = J-cut (audio leads), positive = L-cut
      "transition": "whip_left",                   // transition INTO this clip from the previous one; omit = hard cut
      "transition_duration": 0.3,
      "freeze": {"at": 3.0, "duration": 1.0}       // optional freeze-frame inside the clip (clip time)
    }
  ],

  "music": {
    "file": "music/track.mp3", "start": 0.0,       // start = offset into the music file
    "gain_db": -10, "duck": true,                  // duck under voiceover + clip speech (sidechain)
    "duck_amount": 14,                             // dB of ducking depth (approx.)
    "fade_in": 0.0, "fade_out": 1.0
  },
  "voiceover": {"file": "vo.wav", "at": 0.0, "gain_db": 0, "clean": true},   // clean = dialogue chain
  "sfx": [                                          // transient of the file lands at "at"
    {"file": "sfx/whoosh.wav", "at": 3.35, "gain_db": -6, "pan": -0.5},
    {"file": "sfx/impact.wav", "at": 6.0,  "gain_db": -3}
  ],
  "auto_sfx": {"whoosh": "sfx/whoosh.wav", "impact": "sfx/impact.wav", "flash": "sfx/ping.wav"},
                                                   // if set, transitions get their matching SFX automatically

  "text": [
    {"text": "3 EDITING MISTAKES", "at": 0.2, "duration": 2.2,
     "size": 110, "color": "white", "position": "center",       // center|top|bottom|lower_third or {"x":"(w-text_w)/2","y":"h*0.3"}
     "anim": "slide_up",                                         // none|fade|slide_up|slide_left|pop
     "box": true, "font": "/optional/other.ttf", "shadow": true, "stagger": 0}
  ],
  "lower_thirds": [ {"name": "Your Name", "role": "Founder, Your Company", "at": 1.0, "duration": 4.0} ],
  "images": [ {"file": "logo.png", "at": 0, "duration": 0, "x": "W-w-40", "y": "40", "scale": 0.12, "opacity": 0.75, "anim": "fade"} ],
                                                   // duration 0 = whole timeline; scale = fraction of output width
  "captions": "captions.ass",                      // .ass or .srt, burned last
  "progress_bar": {"height": 8, "position": "bottom"},   // optional, uses brand_color

  "look": "teal_orange",                            // preset name (see color-and-look.md) or raw filter string, or "" for none
  "lut": {"file": "looks/film.cube", "strength": 0.6},
  "grain": 6,                                        // 0–16
  "vignette": 0.3,                                   // 0–1
  "letterbox": "2.39"                                // optional cinematic bars
}
```

## Transition names
`cut` (default), any `xfade` name (`fade`, `fadeblack`, `fadewhite`, `slideleft`, `smoothright`, `zoomin`, `hblur`, `circleopen`, `pixelize`, `dissolve`, ...), plus editor recipes: `whip_left`, `whip_right`, `whip_up`, `whip_down`, `zoom_punch`, `flash`, `flash_warm`, `glitch`, `film_burn`, `speed_ramp`, `blur_dissolve`, `match_dissolve` (2-frame).

## How the renderer works (so you can predict the result)
1. Each clip → conformed intermediate in `work/` (trim, speed/ramp, fit, zoom, filters, freeze, boundary effects for its transitions, clip audio with micro-fades).
2. Intermediates are joined in order: hard cuts via `concat`, transitions via `xfade`/`acrossfade` with the correct offsets. Durations are measured from the rendered intermediates, so offsets are exact.
3. Overlays applied on the joined video: look/LUT → images → lower-thirds → text → progress bar → captions → grain/vignette → letterbox.
4. Audio: timeline audio + cleaned voiceover + music (sidechain-ducked by VO/speech) + SFX → mix → `loudnorm` → limiter.
5. Encode to `output.path`. Run `qc.py` afterwards.

## Tips
- Compute clip durations from beats: `(out - in) / speed` should equal the gap between grid points. Keep 0.2 s extra in `out` for clips with a transition after them.
- To change one shot, edit the JSON and re-render; unchanged intermediates are reused (cache keyed on clip settings) so iterations are fast.
- For a montage with 40 clips, generate the JSON programmatically from `beats.json` + a shot list rather than writing by hand.
