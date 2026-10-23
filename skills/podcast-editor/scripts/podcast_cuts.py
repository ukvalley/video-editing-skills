#!/usr/bin/env python3
"""Scribe words → podcast cut list: fillers, stutters, repeated phrases, long pauses, plus auto multicam framing.

    python3 podcast_cuts.py work/scribe.json edit/keeps.json --src raw/ep.mp4 [--audio work/iso.wav]
        [--range 0 3600] [--max-gap 0.7] [--keep-gap 0.32] [--crops edit/speaker_crops.json] [--min-shot 2.5]
        [--punch 1.12] [--wide-every 0] [--no-repeats] [--report edit/cuts_report.md]

What gets cut (all reviewable in --report before anything renders):
- fillers: अ/अअ/आ/उम/हम्म/umm/uh/hmm/er/ah (+ --extra-fillers "matlab,basically" if the user wants)
- stutters: ता-ताकत style hyphen stutters (keeps the full word) and immediate repeats "ek ek ek" (keeps the last)
- false starts: an immediately repeated 2-5 word phrase → keeps the LAST take (disable with --no-repeats)
- host backchannels (हमम, haan, ok) only when they sit in a pause — never when they overlap the guest
- pauses longer than --max-gap are tightened to --keep-gap (podcasts breathe: don't go below ~0.3 s)
Framing (--crops '{"speaker_0": [x,y,w,h], "speaker_1": [...], "wide": [...]}' in source px):
- each kept stretch gets its speaker's close-up; shots shorter than --min-shot stay on the previous framing
- a micro-cut inside one speaker's shot toggles a --punch zoom so the jump cut reads as a camera change
- --wide-every N: return to "wide" every N seconds for a beat (if a wide exists and has no baked-in name tags)
"""
import argparse, json, re

FILLERS = {"अ", "अअ", "अअअ", "आ", "आआ", "उम", "उम्म", "हम्म", "हमम", "हम्मम", "umm", "um", "uh", "uhh", "hmm",
           "hmmm", "mm", "mmm", "er", "erm", "ah", "aa", "aaa"}
BACKCHANNEL = {"हां", "हाँ", "हा", "हम्म", "हमम", "ओके", "okay", "ok", "haan", "han", "achha", "अच्छा", "right", "yeah", "yes"}


def norm(w):
    return re.sub(r"[^\wऀ-ॿ-]", "", w.lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scribe"); ap.add_argument("out")
    ap.add_argument("--src", required=True); ap.add_argument("--audio")
    ap.add_argument("--range", nargs=2, type=float)
    ap.add_argument("--max-gap", type=float, default=0.7); ap.add_argument("--keep-gap", type=float, default=0.32)
    ap.add_argument("--min-cut", type=float, default=0.12)
    ap.add_argument("--extra-fillers", default="")
    ap.add_argument("--no-repeats", action="store_true")
    ap.add_argument("--crops"); ap.add_argument("--min-shot", type=float, default=2.5)
    ap.add_argument("--punch", type=float, default=1.12); ap.add_argument("--wide-every", type=float, default=0)
    ap.add_argument("--report")
    a = ap.parse_args()
    fillers = FILLERS | {norm(x) for x in a.extra_fillers.split(",") if x.strip()}
    W = [w for w in json.load(open(a.scribe))["words"] if w.get("type", "word") == "word"]
    if a.range:
        W = [w for w in W if w["start"] >= a.range[0] and w["end"] <= a.range[1]]
    drop, why = set(), {}

    def mark(i, r):
        if i not in drop:
            drop.add(i); why[i] = r

    for i, w in enumerate(W):
        n = norm(w["word"])
        if n in fillers:
            mark(i, "filler")
        elif "-" in n:
            p = n.split("-")
            if p[0] and p[-1].startswith(p[0]):
                w["word"] = p[-1]  # ता-ताकत → keep, caption it as ताकत
        if i + 1 < len(W) and n and n == norm(W[i + 1]["word"]) and W[i + 1]["start"] - w["end"] < 0.6:
            mark(i, "stutter")
    # host backchannels in a pause of the other speaker
    for i, w in enumerate(W):
        if norm(w["word"]) in BACKCHANNEL and 0 < i < len(W) - 1:
            p, q = W[i - 1], W[i + 1]
            if p.get("speaker") == q.get("speaker") != w.get("speaker") and w["start"] >= p["end"] and w["end"] <= q["start"]:
                mark(i, "backchannel")
    # false starts: phrase of 2-5 words immediately repeated → drop the first take
    if not a.no_repeats:
        keep_idx = [i for i in range(len(W)) if i not in drop]
        toks = [norm(W[i]["word"]) for i in keep_idx]
        k = 0
        while k < len(toks):
            for n in range(5, 1, -1):
                if k + 2 * n <= len(toks) and toks[k:k + n] == toks[k + n:k + 2 * n] and \
                        W[keep_idx[k + n]]["start"] - W[keep_idx[k + n - 1]]["end"] < 1.5:
                    for j in range(k, k + n):
                        mark(keep_idx[j], "repeat")
                    k += n - 1
                    break
            k += 1

    # never cut a word that overlaps a kept word (a backchannel under the guest's sentence can't be removed)
    kept_spans = [(W[i]["start"], W[i]["end"]) for i in range(len(W)) if i not in drop]
    for i in list(drop):
        if any(s < W[i]["end"] and e > W[i]["start"] for s, e in kept_spans):
            drop.discard(i); why.pop(i)
    kept = [i for i in range(len(W)) if i not in drop]
    if not kept:
        raise SystemExit("nothing left to keep")
    t_start = a.range[0] if a.range else max(0, W[kept[0]]["start"] - 0.25)
    t_end = a.range[1] if a.range else W[kept[-1]]["end"] + 0.4
    segs, cuts = [], []
    cur_in = t_start
    for x, y in zip(kept, kept[1:]):
        A, B = W[x], W[y]
        gap = B["start"] - A["end"]
        removed = y - x > 1
        if removed or gap > a.max_gap:
            spoken = sum(W[j]["end"] - W[j]["start"] for j in range(x + 1, y))
            g = max(0.06, min(gap - spoken, a.keep_gap)) if removed else a.keep_gap
            c0, c1 = A["end"] + g / 2, B["start"] - g / 2
            if c1 - c0 >= a.min_cut:
                segs.append({"in": round(cur_in, 3), "out": round(c0, 3), "spk": A.get("speaker")})
                cuts.append((c0, c1, " ".join(W[j]["word"] + f"[{why.get(j, '')}]" for j in range(x + 1, y)) or "(pause)"))
                cur_in = c1
    segs.append({"in": round(cur_in, 3), "out": round(t_end, 3), "spk": W[kept[-1]].get("speaker")})

    # split kept stretches at speaker changes (midpoint of the gap) so framing can follow the talker
    if a.crops:
        crops = json.load(open(a.crops))
        bounds = [((W[x]["end"] + W[y]["start"]) / 2, W[y].get("speaker")) for x, y in zip(kept, kept[1:])
                  if W[x].get("speaker") != W[y].get("speaker")]
        out = []
        for s in segs:
            t, spk = s["in"], next((W[i].get("speaker") for i in kept if W[i]["end"] > s["in"]), s["spk"])
            for b, nxt in bounds:
                if s["in"] < b < s["out"]:
                    out.append({"in": round(t, 3), "out": round(b, 3), "spk": spk, "cut_before": t == s["in"]})
                    t, spk = b, nxt
            out.append({"in": round(t, 3), "out": s["out"], "spk": spk, "cut_before": t == s["in"]})
        # assign framing with a minimum shot length; toggle punch-in on jump cuts inside a shot
        frame, shot_t, zoom, elapsed, last_wide = None, -1e9, 1.0, 0.0, 0.0
        for k, s in enumerate(out):
            want = s["spk"] if s["spk"] in crops else frame
            if frame is None or (want != frame and elapsed - shot_t >= a.min_shot):
                if frame is not None and want != frame:
                    zoom = 1.0
                frame, shot_t = want, elapsed
            elif k and s["cut_before"]:
                zoom = a.punch if zoom == 1.0 else 1.0
            if a.wide_every and "wide" in crops and elapsed - last_wide > a.wide_every and s["out"] - s["in"] > 2:
                s["crop"], last_wide = crops["wide"], elapsed
            elif frame in crops:
                s["crop"] = crops[frame]
                if zoom != 1.0:
                    s["zoom"] = zoom
            elapsed += s["out"] - s["in"]
        segs = out
    for s in segs:
        s.pop("cut_before", None)
    res = {"src": a.src, "segments": segs}
    if a.audio:
        res["audio"] = a.audio
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    src_len = t_end - t_start
    new_len = sum(s["out"] - s["in"] for s in segs)
    kinds = {}
    for r in why.values():
        kinds[r] = kinds.get(r, 0) + 1
    print(f"wrote {a.out}: {len(segs)} segments, {len(cuts)} cuts, {src_len:.1f}s → {new_len:.1f}s; removed words {kinds}")
    if a.report:
        with open(a.report, "w") as f:
            f.write(f"# Cut report\n{src_len:.1f}s → {new_len:.1f}s, {len(cuts)} cuts, removed words {kinds}\n\n| at (src) | len | removed |\n|---|---|---|\n")
            for c0, c1, txt in cuts:
                f.write(f"| {int(c0 // 60)}:{c0 % 60:05.2f} | {c1 - c0:.2f}s | {txt} |\n")
        print(f"report {a.report}")


if __name__ == "__main__":
    main()
