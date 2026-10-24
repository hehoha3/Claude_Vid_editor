"""PostgreSQL mirror of the footage library for fast queries (user 2026-10-24). The JSON indexes in .work/library/
and the ledgers stay the source of truth (git); this copy is rebuilt from them, never edited by hand.

    .venv/Scripts/python.exe .work/tools/library_db.py sync            # JSON -> Postgres (whole copy, a few seconds)
    .venv/Scripts/python.exe .work/tools/library_db.py query "SQL"     # tab-separated rows (max 50 unless the SQL has LIMIT)
    .venv/Scripts/python.exe .work/tools/library_db.py --selftest

Connection: env LIBRARY_DB (libpq string, default "dbname=dvr_library"); user / host / password from the usual PG*
variables or %APPDATA%\\postgresql\\pgpass.conf, never written in a file here.

Tables:
  clips(root, id, source, path, subject, duration, width, height, fps, tags jsonb)   -- id = content hash
  usage(workspace, video, rank, clip_id, timeline)   -- rank 0 = newest checked video of the workspace
  slots(video, region, slot, line, start, dur, tag, need, species jsonb, filter jsonb, status, clip_id, path, source,
        intro, vo, rej jsonb)        -- every .work/doc_edit/<video>/plan.json (status OK / WEAK / THIEU / FALLBACK / GFX)
  slot_audio(video, slot, start, track, kw jsonb, status, path)   -- the plans' audio cues (A3-A9)
  audio(root, id, path, category, duration, sample_rate, channels, title_hint, lufs, blocked)  -- audio/sfx/sound
Examples:
  SELECT count(*) FROM clips WHERE tags->'species' ? 'lion' AND tags->>'sex' = 'female' AND tags->'action' ? 'run'
  SELECT path FROM clips c WHERE root = 'africa_video' AND tags->'species' ? 'warthog'
    AND NOT EXISTS (SELECT 1 FROM usage u WHERE u.clip_id = c.id AND u.rank < 6) LIMIT 20
  SELECT species, filter->'act' act, count(*) FROM slots WHERE status = 'THIEU' GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20
  SELECT kw, count(*) FROM slot_audio WHERE status = 'THIEU' GROUP BY 1 ORDER BY 2 DESC
  SELECT a.path FROM audio a WHERE a.category ILIKE '%tense%' AND NOT EXISTS
    (SELECT 1 FROM slot_audio s WHERE s.path = a.path) LIMIT 20
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude" / "skills" / "scan-source" / "scripts"))
from scan_source import ROOTS, index_of  # noqa: E402

DOC_EDIT = ROOT / ".work" / "doc_edit"
LEDGERS = DOC_EDIT / "ledgers"
BLOCKED = ROOT / ".work" / "library" / "audio_blocked.txt"
SCHEMA = """
CREATE TABLE IF NOT EXISTS slots (video text, region text, slot int, line int, start real, dur real, tag text,
  need text, species jsonb, filter jsonb, status text, clip_id text, path text, source text, intro bool, vo bool,
  rej jsonb);
CREATE INDEX IF NOT EXISTS slots_status ON slots (status);
CREATE TABLE IF NOT EXISTS slot_audio (video text, slot int, start real, track int, kw jsonb, status text, path text);
CREATE TABLE IF NOT EXISTS audio (root text, id text, path text, category text, duration real, sample_rate int,
  channels int, title_hint text, lufs real, blocked bool, PRIMARY KEY (root, id));
CREATE TABLE IF NOT EXISTS clips (root text, id text, source text, path text, subject text, duration real,
  width int, height int, fps real, tags jsonb, PRIMARY KEY (root, id));
CREATE INDEX IF NOT EXISTS clips_tags ON clips USING gin (tags);
CREATE INDEX IF NOT EXISTS clips_id ON clips (id);
CREATE TABLE IF NOT EXISTS usage (workspace text, video text, rank int, clip_id text, timeline text);
CREATE INDEX IF NOT EXISTS usage_clip ON usage (clip_id);
"""


def clip_rows(name, idx):
    for k, c in idx["clips"].items():
        yield (name, k, c.get("source") or ROOTS[name][2], c["path"], c.get("subject"), c.get("duration"),
               c.get("width"), c.get("height"), c.get("fps"), json.dumps(c.get("tags") or {}, ensure_ascii=False))


def usage_rows(ledger):
    for rank, v in enumerate(ledger["videos"]):  # newest first, as ledger.py keeps them
        for tl, key in (("edit", "clips"), ("open", "open_clips")):
            for cid in v.get(key) or []:
                yield ledger["workspace"], v["video"], rank, cid, tl


def slot_rows(video, plan):
    """-> (slot rows, audio rows) of one plan.json; the slot's [tag] is the need's leading bracket."""
    sr, ar = [], []
    for s in plan["slots"]:
        need = s.get("need") or ""
        tag = need[1:need.index("]")] if need.startswith("[") and "]" in need else None
        f = s.get("filter") or {}
        sr.append((video, plan.get("region"), int(s["slot"]), s.get("line"), s.get("start"), s.get("dur"), tag, need,
                   json.dumps(f.get("sp") or []), json.dumps(f, ensure_ascii=False), s.get("status"), s.get("id"),
                   s.get("path"), s.get("source"), s.get("intro"), s.get("vo"),
                   json.dumps(s.get("rej") or {}, ensure_ascii=False)))
        ar += [(video, int(s["slot"]), s.get("start"), a.get("track"), json.dumps(a.get("kw") or []), a.get("status"),
                a.get("path")) for a in s.get("audio") or []]
    return sr, ar


def audio_rows(name, idx, lufs, blocked):
    root = ROOTS[name][0]
    for k, c in idx["clips"].items():
        full = os.path.join(str(root), c["path"])
        # full path: joins slot_audio.path and loudness.json
        yield (name, k, full, c.get("category"), c.get("duration"), c.get("sample_rate"), c.get("channels"),
               c.get("title_hint"), lufs.get(full), any(b.lower() in full.lower() for b in blocked))


def sync():
    import psycopg
    with psycopg.connect(os.environ.get("LIBRARY_DB", "dbname=dvr_library")) as db, db.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute("TRUNCATE clips, usage, slots, slot_audio, audio")
        s, cues = 0, []  # one COPY at a time per connection (a second command inside a COPY blocks forever)
        with cur.copy("COPY slots FROM STDIN") as cp:
            for p in DOC_EDIT.glob("*/plan.json"):
                sr, ar = slot_rows(p.parent.name, json.loads(p.read_text(encoding="utf-8")))
                for r in sr:
                    cp.write_row(r)
                s += len(sr)
                cues += ar
        with cur.copy("COPY slot_audio FROM STDIN") as cp:
            for r in cues:
                cp.write_row(r)
        sa = len(cues)
        lp = DOC_EDIT / "loudness.json"
        lufs = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {}
        blocked = [x.strip() for x in BLOCKED.read_text(encoding="utf-8").splitlines() if x.strip()] \
            if BLOCKED.exists() else []
        au = 0
        with cur.copy("COPY audio FROM STDIN") as cp:
            for name, (root, kind, _) in ROOTS.items():
                if kind == "audio" and index_of(root).exists():
                    for r in audio_rows(name, json.loads(index_of(root).read_text(encoding="utf-8")), lufs, blocked):
                        cp.write_row(r)
                        au += 1
        print(f"synced: {s} plan slots of {len(list(DOC_EDIT.glob('*/plan.json')))} videos, {sa} audio cues, "
              f"{au} audio files")
        n = 0
        with cur.copy("COPY clips FROM STDIN") as cp:
            for name, (root, kind, _) in ROOTS.items():
                if kind == "video" and index_of(root).exists():
                    for r in clip_rows(name, json.loads(index_of(root).read_text(encoding="utf-8"))):
                        cp.write_row(r)
                        n += 1
        u = 0
        with cur.copy("COPY usage FROM STDIN") as cp:
            for p in LEDGERS.glob("*.json"):
                for r in usage_rows(json.loads(p.read_text(encoding="utf-8"))):
                    cp.write_row(r)
                    u += 1
    print(f"synced: {n} clips, {u} usage rows")


def query(sql):
    import psycopg
    with psycopg.connect(os.environ.get("LIBRARY_DB", "dbname=dvr_library")) as db, db.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            print(cur.statusmessage)
            return
        rows = cur.fetchmany(50) if "limit" not in sql.lower() else cur.fetchall()
        print("\t".join(d.name for d in cur.description))
        for r in rows:
            print("\t".join("" if x is None else str(x) for x in r))
        print(f"({len(rows)} rows{'' if 'limit' in sql.lower() or len(rows) < 50 else ', first 50 shown'})")


def selftest():
    idx = {"clips": {"ab12": {"path": "lion\\a.mp4", "subject": "lion", "duration": 9.5, "tags": {"sex": "female"}}}}
    r = list(clip_rows("africa_video", idx))
    assert r[0][:5] == ("africa_video", "ab12", "real", "lion\\a.mp4", "lion") and json.loads(r[0][9]) == {"sex": "female"}
    led = {"workspace": "W", "videos": [{"video": "v2", "clips": ["x"]}, {"video": "v1", "clips": ["y"], "open_clips": ["z"]}]}
    assert list(usage_rows(led)) == [("W", "v2", 0, "x", "edit"), ("W", "v1", 1, "y", "edit"), ("W", "v1", 1, "z", "open")]
    plan = {"region": "africa", "slots": [{"slot": 3, "need": "[WH] Lợn con", "filter": {"sp": ["warthog"]},
                                           "status": "THIEU", "audio": [{"track": 8, "kw": ["splash"], "status": "THIEU"}]}]}
    sr, ar = slot_rows("v", plan)
    assert sr[0][6] == "WH" and json.loads(sr[0][8]) == ["warthog"] and ar == [("v", 3, None, 8, '["splash"]', "THIEU", None)]
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if a[:1] == ["sync"]:
        sync()
    elif a[:1] == ["query"] and len(a) > 1:
        query(a[1])
    elif a[:1] == ["--selftest"]:
        selftest()
    else:
        print(__doc__)
