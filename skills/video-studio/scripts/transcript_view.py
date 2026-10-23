#!/usr/bin/env python3
"""Readable, timestamped transcript from word timings (Scribe, Whisper or eleven.py tts) — for picking clips, chapters,
hooks and B-roll moments by reading instead of scrubbing.

    python3 transcript_view.py work/scribe.json [--out work/transcript.md] [--range 0 600] [--gap 0.8] [--max-words 28]

Lines look like `[12:03.4–12:09.9] S0: sentence …`; a new line starts at sentence punctuation, a pause > --gap,
a speaker change or --max-words.
"""
import argparse, json, re


def load_words(path):
    j = json.load(open(path))
    ws = j["words"] if isinstance(j, dict) else j
    out = []
    for w in ws:
        if w.get("type", "word") not in ("word", "audio_event"):
            continue
        text = w.get("word", w.get("text", "")).strip()
        if text:
            out.append({"word": text, "start": float(w["start"]), "end": float(w["end"]),
                        "speaker": w.get("speaker", w.get("speaker_id")), "type": w.get("type", "word")})
    return out


def ts(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words"); ap.add_argument("--out"); ap.add_argument("--range", nargs=2, type=float)
    ap.add_argument("--gap", type=float, default=0.8); ap.add_argument("--max-words", type=int, default=28)
    a = ap.parse_args()
    W = load_words(a.words)
    if a.range:
        W = [w for w in W if a.range[0] <= w["start"] < a.range[1]]
    lines, cur = [], []
    for i, w in enumerate(W):
        cur.append(w)
        nxt = W[i + 1] if i + 1 < len(W) else None
        if (nxt is None or re.search(r"[.?!।]$", w["word"]) or nxt["start"] - w["end"] > a.gap
                or nxt["speaker"] != w["speaker"] or len(cur) >= a.max_words):
            spk = cur[0]["speaker"]
            spk = f"S{str(spk).split('_')[-1]}: " if spk is not None else ""
            text = " ".join(f"({x['word'].strip('()')})" if x["type"] == "audio_event" else x["word"] for x in cur)
            lines.append(f"[{ts(cur[0]['start'])}–{ts(cur[-1]['end'])}] {spk}{text}")
            cur = []
    txt = "\n".join(lines) + "\n"
    if a.out:
        open(a.out, "w").write(txt)
        print(f"wrote {a.out}: {len(lines)} lines")
    else:
        print(txt, end="")


if __name__ == "__main__":
    main()
