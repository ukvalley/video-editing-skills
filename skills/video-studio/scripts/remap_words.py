#!/usr/bin/env python3
"""Map source-time word timings onto the timeline of a keep_render.py cut (drops words that were cut out).

    python3 remap_words.py edit/keeps.json work/scribe.json work/words_out.json [--offset 0]

Output {"words": [{word, start, end, speaker}]} in OUTPUT seconds — feed it to video-editor-pro/scripts/captions_ass.py,
or anchor graphics/SFX to spoken words. --offset shifts everything (e.g. an intro card before the cut starts).
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from transcript_view import load_words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keeps"); ap.add_argument("words"); ap.add_argument("out")
    ap.add_argument("--offset", type=float, default=0.0)
    a = ap.parse_args()
    segs = json.load(open(a.keeps))["segments"]
    W = [w for w in load_words(a.words) if w["type"] == "word"]
    out, t = [], a.offset
    for s in segs:
        for w in W:
            mid = (w["start"] + w["end"]) / 2
            if s["in"] <= mid < s["out"] and not s.get("src"):
                out.append({"word": w["word"], "start": round(t + max(0, w["start"] - s["in"]), 3),
                            "end": round(t + min(s["out"], w["end"]) - s["in"], 3), "speaker": w["speaker"]})
        t += s["out"] - s["in"]
    json.dump({"words": out}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {a.out}: {len(out)} words over {t:.1f}s")


if __name__ == "__main__":
    main()
