#!/usr/bin/env python3
"""Build styled/animated .ass captions from word-level timestamps (Whisper output or any {"words":[{word,start,end}]}).

Usage:
  python3 captions_ass.py words.json out.ass [--style karaoke|clean|boxed] [--font Montserrat] [--size 64]
                         [--color &H00FFFFFF] [--highlight &H0000A5FF] [--words-per-line 4] [--playres 1080x1920]
                         [--position 0.72] [--uppercase] [--max-gap 0.6]

- karaoke: 3-5 word groups, the spoken word highlighted in --highlight with a 70 ms pop (reels/shorts style)
- clean:   same groups, plain white with outline, no per-word animation (tutorials, corporate)
- boxed:   clean text on a semi-opaque box (interviews, long-form)
- position: vertical anchor as a fraction of height (0.72 = lower-middle, good for 9:16; use 0.9 for 16:9)
ASS colours are &HAABBGGRR. Burn with: ffmpeg -i in.mp4 -vf "ass=out.ass" ...
"""
import argparse
import json


def ts(x):
    h = int(x // 3600)
    m = int(x % 3600 // 60)
    s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words_json")
    ap.add_argument("out")
    ap.add_argument("--style", default="karaoke", choices=["karaoke", "clean", "boxed"])
    ap.add_argument("--font", default="Montserrat")
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--color", default="&H00FFFFFF")
    ap.add_argument("--highlight", default="&H0000A5FF")
    ap.add_argument("--words-per-line", type=int, default=4)
    ap.add_argument("--playres", default="1080x1920")
    ap.add_argument("--position", type=float, default=None)
    ap.add_argument("--uppercase", action="store_true")
    ap.add_argument("--max-gap", type=float, default=0.6)
    a = ap.parse_args()
    W, H = [int(x) for x in a.playres.split("x")]
    words = json.load(open(a.words_json))["words"]
    pos = a.position if a.position is not None else (0.72 if H > W else 0.88)
    margin_v = int(H * (1 - pos))
    border = 3 if a.style != "boxed" else 0
    border_style = 1 if a.style != "boxed" else 3
    back = "&H80000000" if a.style != "boxed" else "&H99000000"
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{a.font},{a.size},{a.color},{a.highlight},&H00000000,{back},-1,0,0,0,100,100,0,0,{border_style},{max(2, a.size // 16) if border else 12},{max(1, a.size // 20) if border else 0},2,{int(W * 0.06)},{int(W * 0.06)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, group = [], []
    for i, w in enumerate(words):
        group.append(w)
        gap = (words[i + 1]["start"] - w["end"]) if i + 1 < len(words) else 9
        if len(group) >= a.words_per_line or gap > a.max_gap or w["word"].endswith((".", "?", "!", ",")) or w.get("br"):
            lines.append(group)
            group = []
    if group:
        lines.append(group)
    ev = []
    fmt = (lambda s: s.upper()) if (a.uppercase or a.style == "karaoke") else (lambda s: s)
    for li, g in enumerate(lines):
        s, e = g[0]["start"], max(g[-1]["end"], g[0]["start"] + 0.3)
        if li + 1 < len(lines):
            e = min(e, lines[li + 1][0]["start"])  # never overlap the next line
        if a.style == "karaoke":
            for k, w in enumerate(g):
                ws = w["start"]
                we = g[k + 1]["start"] if k + 1 < len(g) else e
                if we <= ws:
                    we = ws + 0.05
                txt = ""
                for j, x in enumerate(g):
                    word = fmt(x["word"])
                    if j == k:
                        txt += "{\\c" + a.highlight + "\\fscx112\\fscy112\\t(0,70,\\fscx100\\fscy100)}" + word + "{\\c" + a.color + "\\fscx100\\fscy100}"
                    else:
                        txt += word
                    txt += " "
                ev.append(f"Dialogue: 0,{ts(ws)},{ts(we)},Cap,,0,0,0,,{{\\an2\\fad({40 if k == 0 else 0},{40 if k == len(g) - 1 else 0})}}{txt.strip()}")
        else:
            txt = " ".join(fmt(x["word"]) for x in g)
            ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{{\\an2\\fad(60,60)}}{txt}")
    open(a.out, "w").write(hdr + "\n".join(ev) + "\n")
    print(f"{len(lines)} caption lines, {len(ev)} events -> {a.out}")


if __name__ == "__main__":
    main()
