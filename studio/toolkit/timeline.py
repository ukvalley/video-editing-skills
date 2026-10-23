"""Source-time -> output-time mapping for a project rendered with edl_render.py.
Reads <project>/edit/phrases.json (id, s, e, text) and segments.json (in, out, d?, transition?) plus the rendered
clip intermediates in <project>/work/render to get exact durations.

    from timeline import Timeline
    tl = Timeline("/path/to/project")
    tl.A("p13", 2)   # output time when word 2 of phrase p13 starts
    tl.E("p14")      # output time when phrase p14 ends
    tl.T, tl.TR      # total duration, [(transition_name, start_time, duration)]
    tl.words()       # caption words in output time (word, start, end, br)
"""
import glob, json, os, subprocess


class Timeline:
    def __init__(self, project):
        self.P = os.path.abspath(project)
        self.phr = json.load(open(f"{self.P}/edit/phrases.json"))
        self.byid = {p["id"]: p for p in self.phr}
        self.segs = json.load(open(f"{self.P}/edit/segments.json"))
        files = []
        for k in range(len(self.segs)):
            fs = sorted(glob.glob(f"{self.P}/work/render/clip_{k:03d}_*.mp4"), key=os.path.getmtime)
            if not fs:
                raise SystemExit(f"clip {k} not rendered yet - run edl_render.py on edit/edit.json first")
            files.append(fs[-1])
        self.durs = [float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                          capture_output=True, text=True).stdout) for f in files]
        self.O = [0.0]; self.TR = []
        for k in range(1, len(self.segs)):
            d = self.segs[k].get("d", 0.0)
            if d:
                d = min(d, self.durs[k - 1] * 0.9, self.durs[k] * 0.9)
                self.TR.append((self.segs[k]["transition"], self.O[-1] + self.durs[k - 1] - d, d))
            self.O.append(self.O[-1] + self.durs[k - 1] - d)
        self.T = self.O[-1] + self.durs[-1]
        self.cuts = [self.O[k] for k in range(1, len(self.segs)) if not self.segs[k].get("d")]
        self._w = self._words_src()

    def m(self, t):
        best = None
        for k, s in enumerate(self.segs):
            if s["in"] - 1e-3 <= t <= s["out"] + 1e-3:
                best = k
        if best is None:
            nxt = [k for k, s in enumerate(self.segs) if s["in"] > t]
            best = nxt[0] if nxt else len(self.segs) - 1
            t = self.segs[best]["in"]
        return self.O[best] + (t - self.segs[best]["in"])

    def _words_src(self):
        out = []
        for p in self.phr:
            ws = p["text"].split(); wt = [len(w.strip(",.?!")) + 2 for w in ws]; tot = sum(wt); t = p["s"]
            for j, (w, k) in enumerate(zip(ws, wt)):
                d = (p["e"] - p["s"]) * k / tot
                out.append({"id": p["id"], "j": j, "w": w, "s": t, "e": t + d, "last": j == len(ws) - 1}); t += d
        return out

    def A(self, pid, j=0):
        return self.m([w for w in self._w if w["id"] == pid and w["j"] == j][0]["s"])

    def E(self, pid):
        return self.m([w for w in self._w if w["id"] == pid and w["last"]][0]["e"])

    def words(self):
        return [{"word": w["w"].strip(",.?!"), "start": round(self.m(w["s"]), 3), "end": round(self.m(w["e"]), 3),
                 "br": w["last"] or w["w"][-1:] in ",.?!"} for w in self._w]
