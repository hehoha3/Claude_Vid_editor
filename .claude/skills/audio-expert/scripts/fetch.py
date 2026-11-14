"""audio-expert fetch: Epidemic Sound / Suno download URL -> audio_lib/<category>/<sub>/ + <stem>.license.txt.

    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/fetch.py --batch .work/audio_expert/fetch.jsonl
    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/fetch.py --have      # counts per folder + ids
    .venv/Scripts/python.exe .claude/skills/audio-expert/scripts/fetch.py --selftest

The MCP tools only hand out signed URLs (Epidemic DownloadRecording / DownloadSoundEffect / DownloadRecordingEdit,
Suno audio-download); this script does the rest so a session spends one Bash call per batch. One JSON object per
line: {"url", "source": "epidemic"|"suno", "id", "dest": "music/DonDap_KichTinh", "title", "author", "tags": "a b",
"bpm"}. dest = <category>/<sub> as plan.py pools it (music, Nature_sound, SXF, ambience_sound; intro = intro.py
only). The file name carries title + tags (plan.py matches keywords on the path) and "[es-<id8>]" / "[suno-<id8>]":
an id already in the library is skipped before any download. Then scan_source.py audio_lib + index.py.
"""
import json, re, subprocess, sys, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.config import load_config  # noqa: E402

LIB = Path(load_config()["paths"]["audio_lib"])
CATS = ("music", "intro", "Nature_sound", "SXF", "ambience_sound")
TAG = {"epidemic": "es", "suno": "suno"}
LICENSE = {"epidemic": "Epidemic Sound subscription; YouTube channel must be whitelisted in the Epidemic account",
           "suno": "Suno Premier: made while subscribed, commercial use allowed"}
EXT = (".mp3", ".wav")


def tag(source, cid):
    return f"[{TAG[source]}-{cid.replace('-', '')[:8].lower()}]"


def clean(s, n=60):
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\[\]]+', " ", s or "")).strip()[:n].strip()


def name(e, ext):
    words = " ".join(dict.fromkeys(clean(e.get("tags", ""), 80).lower().split()))
    author = clean(e.get("author", ""), 30)
    return " ".join([clean(e["title"])] + (["-", author] if author else []) + [tag(e["source"], e["id"]), words]).strip() + ext


def have():
    """{tag: path} of every track already in the library."""
    return {m[0]: p for p in LIB.rglob("*") if p.suffix.lower() in EXT
            for m in [re.findall(r"\[(?:es|suno)-[0-9a-f]{8}\]", p.name)] if m}


def get(e, known):
    assert e["source"] in TAG and e["dest"].replace("\\", "/").split("/")[0] in CATS, f"bad source/dest: {e}"
    t = tag(e["source"], e["id"])
    if t in known:
        return f"skip {t} (in library: {known[t].relative_to(LIB)})"
    ext = next((x for x in EXT if x in e["url"].split("?")[0].lower()), ".mp3")
    d = LIB / e["dest"]
    d.mkdir(parents=True, exist_ok=True)
    out = d / name(e, ext)
    part = out.with_name(out.name + ".part")
    req = urllib.request.Request(e["url"], headers={"User-Agent": "dvr-cowork"})
    with urllib.request.urlopen(req, timeout=120) as r, open(part, "wb") as f:
        while b := r.read(1 << 20):
            f.write(b)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(part)], capture_output=True, text=True).stdout.strip() or 0)
    if dur <= 0:
        part.unlink()  # our own half-written download, never a library file
        return f"FAIL {t}: not audio (expired URL?) -> ask the MCP for a new URL"
    part.replace(out)
    out.with_suffix(".license.txt").write_text(
        f"Source: {'Epidemic Sound' if e['source'] == 'epidemic' else 'Suno'}\nTitle: {e['title']}\n"
        f"Author: {e.get('author', '')}\nID: {e['id']}\nBPM: {e.get('bpm', '')}\nTags: {e.get('tags', '')}\n"
        f"License: {LICENSE[e['source']]}\nDownloaded: {date.today()}\n", "utf-8")
    known[t] = out
    return f"ok {dur:5.0f}s {out.relative_to(LIB)}"


def main(argv):
    if "--have" in argv:
        known = have()
        by = {}
        for p in known.values():
            k = str(p.parent.relative_to(LIB))
            by[k] = by.get(k, 0) + 1
        print(f"{LIB}: {len(known)} tracks | " + ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
        print("ids: " + " ".join(sorted(known)))
        return
    rows = [json.loads(x) for x in Path(argv[argv.index("--batch") + 1]).read_text("utf-8").splitlines() if x.strip()]
    known, bad = have(), 0
    for e in rows:
        try:
            msg = get(e, known)
        except Exception as x:  # one bad URL never stops the batch
            msg = f"FAIL {e.get('id')}: {x}"
        bad += msg.startswith("FAIL")
        print(msg)
    print(f"{len(rows) - bad}/{len(rows)} ok -> next: scan_source.py audio_lib, then audio-expert index.py")


def selftest():
    e = {"source": "epidemic", "id": "13c0a06b-f0ef-3fd8", "title": 'Arbalest: Rain?', "author": "Sam Will",
         "tags": "chase Epic chase", "dest": "music/DonDap_KichTinh"}
    assert name(e, ".mp3") == "Arbalest Rain - Sam Will [es-13c0a06b] chase epic.mp3", name(e, ".mp3")
    assert tag("suno", "AB12CD34-xx") == "[suno-ab12cd34]"
    assert re.findall(r"\[(?:es|suno)-[0-9a-f]{8}\]", name(e, ".mp3")) == ["[es-13c0a06b]"]
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    selftest() if "--selftest" in sys.argv else main(sys.argv[1:])
