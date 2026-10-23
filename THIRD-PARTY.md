# Third-party software and assets

Nothing below is bundled in this repository; `setup.sh` installs or downloads it from the original source.

| Component | Used for | License | Source |
|---|---|---|---|
| FFmpeg (`ffmpeg-full` Homebrew formula) | all rendering | LGPL/GPL | https://ffmpeg.org |
| whisper.cpp + ggml models | free local transcription | MIT | https://github.com/ggml-org/whisper.cpp |
| NumPy, Pillow | analysis, graphics | BSD / HPND | Homebrew |
| Montserrat, Anton, Caveat, Noto Sans Devanagari | titles, captions | SIL Open Font License 1.1 | https://github.com/google/fonts |
| ElevenLabs API (optional) | voice-over, Scribe transcripts, voice isolation | commercial API (your own key) | https://elevenlabs.io |
| Apple Vision framework | face detection for reframing | macOS system framework | — |
| video-shotcraft (optional, separate install) | Remotion product promos | Apache-2.0 | https://github.com/Vincentwei1021/video-shotcraft |

The SFX and music in `assets/` are generated locally by `toolkit/make_sfx*.py`, `make_music.py` and `make_hype_track.py`
(original synthesis, royalty-free under this repo's license).
