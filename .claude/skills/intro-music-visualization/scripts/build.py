"""intro-music-visualization: music_map.json + cuts.txt -> a NEW timeline (music pieces on A7, shots on V1, AI clip
audio on A1 at -12 dB, hit / bar markers). Builds into the named timeline only if it exists and is completely empty;
a timeline with anything on it is never edited (a new name _2, _3... is used). "Edit" / "Master" are refused.

    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/build.py <name> [--check]
    .venv/Scripts/python.exe .claude/skills/intro-music-visualization/scripts/build.py --selftest

<name> = folder .work/intro_mv/<name>/ with music_map.json (music_map.py: the music pieces, gains, fades) and cuts.txt:
    # TIMELINE Open         name of the new timeline
    ## BUILD                section comment, ignored
    1.03 | 4.79 | sunset-over-river | auto | world, first hit
    <in> | <out> | <file path fragment, e.g. eagle/shot_049> | <source in, s, or auto> | <note>
Times are intro-timeline seconds (= music_map times). Time not covered by a line = black.
Clip lookup: unique match in bin "7. Open" first, then anywhere in the media pool, then the tagged library (imported
into "7. Open"). --check validates everything and changes nothing.
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent), str(ROOT / ".claude/skills/doc-edit/scripts"),
                str(ROOT / ".claude/skills/scan-source/scripts")]
WORK = ROOT / ".work" / "intro_mv"
A1_DB = -12
MIN_SHOT = 0.25  # s; shorter flashes do not read
TRACKS = {1: "Audio v1", 2: "Narrator Voice", 3: "Ambience 1", 4: "Ambience 2", 5: "Ambience 3", 6: "Natural sounds",
          7: "Music", 8: "SXF 1", 9: "SXF 2"}
MARK = {5: "Red", 4: "Yellow"}
FLAT, FLAT_SPAN = 4, 0.4  # same as doc-edit plan.py: 4 shots within 0.4 s of each other = metronome


def parse(text, end=None):
    """-> (header dict, [shot dict]) or SystemExit listing every bad line."""
    head, shots, err = {}, [], []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("##"):
            continue
        if s.startswith("#"):
            k, _, v = s[1:].strip().partition(" ")
            head[k.upper()] = v.strip()
            continue
        p = [x.strip() for x in s.split("|")]
        try:
            a, b = float(p[0]), float(p[1])
            src = None if p[3].lower() == "auto" else float(p[3])
            shots.append({"line": n, "in": a, "out": b, "clip": p[2], "src": src, "note": p[4] if len(p) > 4 else ""})
        except (ValueError, IndexError):
            err.append(f"line {n}: expected 'in | out | clip | src|auto | note': {s}")
    prev = None
    for s in shots:
        if s["out"] - s["in"] < MIN_SHOT:
            err.append(f"line {s['line']}: shot {s['out'] - s['in']:.2f} s < {MIN_SHOT} s")
        if prev and s["in"] < prev["out"] - 1e-6:
            err.append(f"line {s['line']}: starts {s['in']} before line {prev['line']} ends {prev['out']}")
        if s["in"] < 0 or (end and s["out"] > end + 1e-6):
            err.append(f"line {s['line']}: outside the music 0-{end} s")
        prev = s
    if not shots:
        err.append("no shot lines")
    if err:
        raise SystemExit("cuts.txt errors:\n  " + "\n  ".join(err))
    return head, shots


def flat(shots, n=FLAT, span=FLAT_SPAN):
    """Runs of n+ adjacent shots whose lengths differ by < span s: a metronome, the viewer stops feeling the cuts."""
    out, d = [], [s["out"] - s["in"] for s in shots]
    i = 0
    while i <= len(d) - n:
        j = i + n
        if max(d[i:j]) - min(d[i:j]) < span:
            while j < len(d) and max(d[i:j + 1]) - min(d[i:j + 1]) < span:
                j += 1
            out.append(f"flat rhythm: lines {shots[i]['line']}-{shots[j - 1]['line']} all ~{d[i]:.2f} s "
                       "(cut some on pickups / hold some 2 bars)")
            i = j
        else:
            i += 1
    return out


def put(mp, tl, it, media, track, rec, n, src_in, fps):
    """Place exactly n timeline frames of `it` at timeline frame rec (doc-edit place.py: endFrame exclusive,
    other-fps clips re-placed until the length is exact)."""
    from dvr_cowork.resolve_ops import clip_fps
    cf = clip_fps(it, fps)
    a, k = round(src_in * cf), round(n * cf / fps)
    for _ in range(3):
        res = mp.AppendToTimeline([{"mediaPoolItem": it, "startFrame": a, "endFrame": a + k,
                                    "mediaType": media, "trackIndex": track, "recordFrame": rec}])
        ti = res[0] if res else None
        if not ti:
            return None
        d = int(ti.GetEnd()) - int(ti.GetStart())
        if d == n:
            return ti
        tl.DeleteClips([ti], False)  # only the item this call just placed
        k += round((n - d) * cf / fps) or (1 if n > d else -1)
    return None


def find(frag, scopes):
    """First scope with matches decides; -> (path, item or library clip) or an error string."""
    f = frag.lower().replace("/", "\\")
    for label, rows in scopes:
        hits = {p: x for p, x in rows if f in p}
        if len(hits) == 1:
            return next(iter(hits.items()))
        if hits:
            return f"'{frag}' matches {len(hits)} clips in {label}: {[Path(h).name for h in list(hits)[:4]]}"
    return f"'{frag}' not found in bin 7. Open, the media pool or the library"


def load(name):
    """cuts.txt + music_map.json -> (pm, project, mp, top bin, music map, header, shots resolved to clips and source
    in-points, files to import). Shared by build.py and storyboard.py so both show the same frames."""
    from dvr_cowork.config import load_config
    from dvr_cowork.resolve_conn import connect
    from dvr_cowork.resolve_ops import get_project
    from plan import load_clips, usable
    from pool import bin_clips, bin_tree, norm

    work = WORK / name
    mmap = json.loads((work / "music_map.json").read_text("utf-8"))
    end = mmap["duration"]
    head, shots = parse((work / "cuts.txt").read_text("utf-8"), end)
    pm, project = get_project(connect(load_config()))
    mp = project.GetMediaPool()
    top, _ = bin_tree(mp)
    lib = {norm(c["abs"]): c for c in load_clips()}
    scopes = [("bin 7. Open", [(norm(it.GetClipProperty("File Path")), it) for _, it in bin_clips(top)]),
              ("the media pool", [(norm(it.GetClipProperty("File Path")), it) for _, it in bin_clips(mp.GetRootFolder())]),
              ("the library", list(lib.items()))]
    err, imports = [], []
    for s in shots:
        hit = find(s["clip"], scopes)
        if isinstance(hit, str):
            err.append(f"line {s['line']}: {hit}")
            continue
        path, x = hit
        c = lib.get(path)
        dur = s["out"] - s["in"]
        if isinstance(x, dict):
            imports.append(path)
            full = x["duration"]
        else:
            full = c["duration"] if c else float(x.GetClipProperty("Frames") or 0) / float(x.GetClipProperty("FPS") or 24)
        a, z = usable(c) if c else (0.0, full)
        if s["src"] is None:
            s["src"] = round(max(0.0, a + (z - a - dur) / 2) if z - a >= dur else max(0.0, (full - dur) / 2), 2)
        if s["src"] + dur > full + 1e-3:
            err.append(f"line {s['line']}: source {s['src']}+{dur:.2f} s runs past the clip end {full:.2f} s")
        s.update(item=None if isinstance(x, dict) else x, path=path,
                 ai=bool(c and c["source"] == "ai") or "\\ai_video\\" in path)
    if err:
        raise SystemExit("clip errors:\n  " + "\n  ".join(err))
    return pm, project, mp, top, mmap, head, shots, imports


def main(name, check):
    from dvr_cowork.resolve_ops import ensure_audio_track, find_bin, find_clip, list_timelines, timeline_fps
    from pool import norm

    pm, project, mp, top, mmap, head, shots, imports = load(name)
    end = mmap["duration"]
    black = sum(b["in"] - a["out"] for a, b in zip(shots, shots[1:])) + shots[0]["in"] + end - shots[-1]["out"]
    print(f"cuts.txt ok: {len(shots)} shots, music {end:.1f} s in {len(mmap['pieces'])} piece(s), black {black:.1f} s, "
          f"{sum(s['ai'] for s in shots)} AI clips, {len(set(imports))} clips to import from the library")
    edges = [0.0] + [x for s in shots for x in (s["in"], s["out"])] + [end]
    print("black:", ", ".join(f"{a:.2f}-{b:.2f}" for a, b in zip(edges[::2], edges[1::2]) if b - a > 0.01) or "none")
    for w in flat(shots):
        print("warning:", w)
    if check:
        print("--check: nothing changed")
        return

    root = mp.GetRootFolder()
    if imports:
        mp.SetCurrentFolder(top)
        got = {norm(i.GetClipProperty("File Path")): i for i in mp.ImportMedia(sorted({os.path.normpath(p) for p in imports})) or []}
        for s in shots:
            s["item"] = s["item"] or got.get(s["path"])
    tls = {t.GetName(): t for t in list_timelines(project)}
    base = head.get("TIMELINE", "Open")
    assert base.lower() not in ("edit", "master"), f'timeline "{base}" is never touched'
    tl = tls.get(base)
    if tl and any(tl.GetItemListInTrack(k, i) for k in ("video", "audio") for i in range(1, int(tl.GetTrackCount(k)) + 1)):
        tl = None  # not empty: never edited, a new name is used instead
    tname = base if tl or base not in tls else next(f"{base}_{k}" for k in range(2, 99) if f"{base}_{k}" not in tls)
    orig = project.GetCurrentTimeline()
    mp.SetCurrentFolder(top)
    if tl:
        print(f'timeline "{base}" exists and is empty: building into it')
    else:
        tl = mp.CreateEmptyTimeline(tname)
    assert tl, f"cannot create timeline {tname}"
    project.SetCurrentTimeline(tl)
    ensure_audio_track(tl, 9, 2, lambda *_: None)
    for i, n in TRACKS.items():
        tl.SetTrackName("audio", i, n)
    fps = timeline_fps(tl, project)
    t0 = int(tl.GetStartFrame())
    f = lambda sec: round(sec * fps)  # noqa: E731  intro seconds -> frames from the timeline start
    failed, a1 = [], 0
    for p in mmap["pieces"]:
        it = find_clip(root, p["path"])
        if not it:
            b = find_bin(root, "4. Audio") or mp.AddSubFolder(root, "4. Audio")
            mp.SetCurrentFolder(b)
            it = (mp.ImportMedia([os.path.normpath(p["path"])]) or [None])[0]
        n = f(p["tl"] + p["out"] - p["in"]) - f(p["tl"])
        ti = it and put(mp, tl, it, 2, 7, t0 + f(p["tl"]), n, p["in"], fps)
        if not ti:
            failed.append(f"music {Path(p['path']).name}")
            continue
        if p["gain"]:
            ti.SetProperty("AudioVolume", p["gain"])
        fi, fo = round(p["fade_in"] * fps), round(p["fade_out"] * fps)
        if fi or fo:
            ti.SetFades({"FadeIn": fi, "FadeOut": fo})
    for s in shots:
        n = f(s["out"]) - f(s["in"])
        if not s["item"] or not put(mp, tl, s["item"], 1, 1, t0 + f(s["in"]), n, s["src"], fps):
            failed.append(f"line {s['line']} {Path(s['path']).name}")
            continue
        if s["ai"]:
            au = put(mp, tl, s["item"], 2, 1, t0 + f(s["in"]), n, s["src"], fps)
            a1 += bool(au and au.SetProperty("AudioVolume", A1_DB))
    marks = 0
    for e in mmap.get("events", []):
        if e["level"] in MARK:
            marks += bool(tl.AddMarker(f(e["t"]), MARK[e["level"]], f"B{e['level']} {e['kind']}", f"hit {e['t']} s", 1,
                                       "intro_mv"))
    for a, b in mmap.get("breaks", []):
        if b - a >= 0.8:
            marks += bool(tl.AddMarker(f(a), "Blue", "break", f"{a}-{b} s", max(1, f(b) - f(a)), "intro_mv"))
    for p in mmap["pieces"][1:]:
        marks += bool(tl.AddMarker(f(p["tl"]), "Purple", "music join", Path(p["path"]).name[:60], 1, "intro_mv"))
    pm.SaveProject()
    if orig:
        project.SetCurrentTimeline(orig)
    v = sorted(tl.GetItemListInTrack("video", 1) or [], key=lambda t: t.GetStart())
    starts = {int(ti.GetStart()) - t0 for ti in v}
    off = sum(f(s["in"]) not in starts for s in shots)
    print(f'timeline "{tname}": V1 {len(v)}/{len(shots)} shots ({off} off their frame), A1 {a1} AI clip audio at {A1_DB} dB, '
          f"A7 {len(mmap['pieces'])} music piece(s), {marks} markers (Red B5, Yellow B4, Blue break, Purple join); "
          f"failed: {failed or 'none'}")
    if orig:
        print(f'back on timeline "{orig.GetName()}"')


def selftest():
    h, s = parse("# TIMELINE Open\n## OPEN\n0.86 | 2.9 | eyes | 0.25 | B5\n4.33 | 6.3 | eagle/shot_049 | auto |\n", 20)
    assert h["TIMELINE"] == "Open" and len(s) == 2 and s[1]["src"] is None
    for bad in ("1 | 2 | a\n", "1 | 1.1 | a | 0 |\n", "1 | 3 | a | 0 |\n2 | 4 | b | 0 |\n", "18 | 21 | a | 0 |\n"):
        try:
            parse(bad, 20)
            raise AssertionError(bad)
        except SystemExit:
            pass
    sh = [{"line": i, "in": 0, "out": d} for i, d in enumerate([3.7, 1.85, 1.85, 1.9, 1.84, 3.6, 1.5, 2.2])]
    assert len(flat(sh)) == 1 and "lines 1-4" in flat(sh)[0], flat(sh)
    rows = [("x:\\ai\\eagle\\shot_049.mp4", 1), ("x:\\ai\\anaconda\\shot_049.mp4", 2)]
    assert find("eagle/shot_049", [("bin", rows)])[1] == 1
    assert "matches 2" in find("shot_049", [("bin", rows)])
    assert find("shot_049", [("bin", []), ("pool", rows[:1])])[1] == 1  # falls through an empty scope
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    selftest() if a == ["--selftest"] else main(a[0], "--check" in a) if a else print(__doc__)
