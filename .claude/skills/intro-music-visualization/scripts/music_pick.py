"""intro-music-visualization: which tense track (or cut / splice of tracks) gives an intro of the wanted length.
Reads the music folders (READ ONLY), analyses each file once (cache .work/intro_mv/music_index.json, keyed by
path + size + mtime), prints three short lists. No tokens, nothing written to Resolve.

    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_pick.py [--len 45-120] [--top 12]
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/music_pick.py --selftest

FITS   whole track already inside the length range.
CUT    longer track: exit hits (a final-drop-like hit followed by a fall-off) inside the range -> end there
       (music_map.py "<file>@0-<exit + 2>" gives the hit room to ring; build fades the tail).
SPLICE piece A (start -> one of its exits) + piece B (one of its entries -> end or an exit), tempo within 4 %
       (or half / double) and keys compatible (same, relative, fifth, parallel). The join lands on B's entry hit.
slow = seconds before the music starts driving (first 4 s window with >= 4 B3+ hits): the user likes 8-15 s.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from music_map import NOTES, OUT, analyse, decode  # noqa: E402

FOLDERS = [Path(r"Z:\Unseen\Amazona\audio\openning"), Path(r"Z:\Unseen\Sound\DonDap_KichTinh"),
           Path(r"Z:\Unseen\Sound\RinhRap_NguyHiem"), Path(r"Z:\Unseen\Sound\BiAn_KhamPha")]  # calm / neutral moods left out
EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
CACHE = OUT / "music_index.json"


def summary(m):
    ev = m["events"]
    strong = [e["t"] for e in ev if e["level"] >= 3]
    slow = next((t for t in strong if sum(t <= x < t + 4 for x in strong) >= 4), m["duration"])
    return {"dur": m["duration"], "bpm": m["bpm"], "conf": m["conf"], "key": m["key"], "key_conf": m["key_conf"],
            "slow": round(slow, 1), "b5": [e["t"] for e in ev if e["level"] == 5],
            "entries": [[e["t"], e["level"]] for e in ev if "entry" in e["flag"]],
            "exits": [[e["t"], e["level"], e["post"]] for e in ev if "exit" in e["flag"]], "breaks": m["breaks"]}


def scan():
    cache = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}
    files = [f for d in FOLDERS if d.exists() for f in sorted(d.rglob("*")) if f.suffix.lower() in EXTS]
    new = 0
    for f in files:
        st = f.stat()
        k = f"{f}|{st.st_size}|{int(st.st_mtime)}"
        if k not in cache:
            try:
                cache[k] = summary(analyse(decode(f)))
            except Exception as e:  # noqa: BLE001  unreadable file: listed, not fatal
                cache[k] = {"error": str(e)[:80]}
            new += 1
            if new % 10 == 0:
                CACHE.write_text(json.dumps(cache), "utf-8")
    CACHE.write_text(json.dumps(cache), "utf-8")
    live = {k.split("|")[0]: v for k, v in cache.items() if Path(k.split("|")[0]) in set(files)}
    return live, new


def key_fit(a, b):
    """1 same / relative, 0.7 fifth, 0.5 parallel, 0 otherwise."""
    (pa, ma), (pb, mb) = [(NOTES.index(k.split()[0]), k.split()[1]) for k in (a, b)]
    rel = lambda p, m: p if m == "major" else (p + 3) % 12  # noqa: E731  relative major
    if rel(pa, ma) == rel(pb, mb):
        return 1.0
    if ma == mb and (pa - pb) % 12 in (5, 7):
        return 0.7
    return 0.5 if pa == pb else 0.0


def tempo_fit(a, b):
    if not a or not b:
        return False
    r = max(a, b) / min(a, b)
    return abs(r - 1) <= 0.04 or abs(r - 2) <= 0.08


def splices(tracks, lo, hi):
    out = []
    for pa, a in tracks.items():
        for pb, b in tracks.items():
            if pa == pb or not tempo_fit(a["bpm"], b["bpm"]) or not (kf := key_fit(a["key"], b["key"])):
                continue
            for xa, la, _ in a["exits"]:
                if xa < 12:  # piece A must at least carry the slow opening
                    continue
                for eb, lb in b["entries"]:
                    ends = [(b["dur"], "end")] + [(x, f"exit {x}") for x, _, _ in b["exits"] if x > eb + 8]
                    for end, how in ends:
                        total = xa + end - eb
                        if lo <= total <= hi:
                            score = kf + 0.2 * (la + lb) / 5 + (0.3 if 8 <= a["slow"] <= 15 else 0)
                            out.append((score, total, pa, xa, pb, eb, end, how))
    best = {}  # one line per track pair: the best join, prefer a total near the middle of the range
    for x in sorted(out, key=lambda x: (-x[0], abs(x[1] - (lo + hi) / 2))):
        best.setdefault((x[2], x[4]), x)
    return sorted(best.values(), key=lambda x: -x[0])


def main(argv):
    lo, hi = (float(x) for x in (argv[argv.index("--len") + 1] if "--len" in argv else "45-120").split("-"))
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 12
    live, new = scan()
    ok = {p: v for p, v in live.items() if "error" not in v and v["bpm"]}
    print(f"{len(live)} tracks in {len(FOLDERS)} folders ({new} analysed now, {len(live) - len(ok)} unreadable / no tempo); "
          f"target {lo:.0f}-{hi:.0f} s")
    name = lambda p: f"{Path(p).parent.name}/{Path(p).name[:55]}"  # noqa: E731
    head = lambda v: f"{v['bpm']:.0f} BPM ({v['conf']}) {v['key']} ({v['key_conf']}) | slow {v['slow']} s"  # noqa: E731
    fits = sorted((p for p, v in ok.items() if lo <= v["dur"] <= hi), key=lambda p: (not 8 <= ok[p]["slow"] <= 15, ok[p]["dur"]))
    print(f"\nFITS ({len(fits)})")
    for p in fits[:top]:
        v = ok[p]
        print(f"  {v['dur']:6.1f} s | {head(v)} | B5 {v['b5'][:4]} | {name(p)}")
    cuts = [(p, [x for x in ok[p]["exits"] if lo <= x[0] + 2 <= hi]) for p, v in ok.items() if v["dur"] > hi]
    cuts = sorted([c for c in cuts if c[1]], key=lambda c: (not 8 <= ok[c[0]]["slow"] <= 15, -max(x[1] for x in c[1])))
    print(f"\nCUT ({len(cuts)} long tracks with an exit hit in range)")
    for p, ex in cuts[:top]:
        best = sorted(ex, key=lambda x: (-x[1], x[2]))[:3]
        print(f"  {ok[p]['dur']:6.1f} s | {head(ok[p])} | end at " +
              ", ".join(f"{t:.2f} (B{l}, then {post:+.0f} dB)" for t, l, post in best) + f" | {name(p)}")
    sp = splices(ok, lo, hi)
    print(f"\nSPLICE ({len(sp)} track pairs, best join each; top {top})")
    for score, total, pa, xa, pb, eb, end, how in sp[:top]:
        print(f"  {total:6.1f} s | fit {score:.2f} | A {name(pa)} 0-{xa + 0.05:.2f} ({ok[pa]['key']}, {ok[pa]['bpm']:.0f}) "
              f"+ B {name(pb)} {eb - 0.4:.2f}-{end:.2f} [{how}] ({ok[pb]['key']}, {ok[pb]['bpm']:.0f})")
    print(f"\ncache -> {CACHE}")


def selftest():
    assert key_fit("D minor", "F major") == 1.0 and key_fit("A minor", "E minor") == 0.7
    assert key_fit("C major", "C minor") == 0.5 and key_fit("C major", "F# major") == 0.0
    assert tempo_fit(110, 112) and tempo_fit(70, 140) and not tempo_fit(110, 120)
    t = {"a": {"bpm": 110, "key": "D minor", "dur": 60, "slow": 10, "exits": [[40.0, 4, -12]], "entries": []},
         "b": {"bpm": 111, "key": "F major", "dur": 70, "slow": 3, "exits": [], "entries": [[20.0, 5]]}}
    s = splices(t, 45, 120)
    assert s and s[0][2] == "a" and abs(s[0][1] - 90) < 1e-6, s  # 40 s of A + 50 s of B
    print("selftest ok")


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["--selftest"] else main(sys.argv[1:])
