# SFX library (shared by every project)

| File | Use | Typical level (before +6 dB boost) |
|---|---|---|
| whoosh.wav | whip transitions, full-screen graphics in/out | -11 dB |
| swish.wav | text / cards sliding in | -14 dB |
| pop.wav | titles, labels, chips appearing | -13 dB |
| tick.wav | checklist ticks, counters | -16 to -22 dB |
| ding.wav | success moments ("khareeda", stat badges) | -14 dB |
| impact.wav | zoom-punch, hook opening, big reveals | -9 to -12 dB |
| riser.wav | 1.6 s build into a reveal | -20 dB |
| buzz.wav | wrong / crossed-out | -17 dB |

These are synthesised placeholders (`python3 toolkit/make_sfx.py` regenerates them).
To upgrade: drop a real sample with the **same file name** here (Mixkit, Pixabay, freesound — 48 kHz WAV preferred). Add new sounds with new names; they become available to every project.
