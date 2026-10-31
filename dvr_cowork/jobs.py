r"""Durable doc-edit workflow state (V2 spec PR 2-6, user 2026-10-30): SQLite WAL .work/automation/jobs.sqlite3.
Python only (no Claude supervisor): the stage of a video comes from its files (state.py stage), the user's per-video
decision (Case 1 / Case 2) and every Resolve write (logged by resolve_ops.backup_timeline) are stored here.

    python -m dvr_cowork.jobs status                                   every recent video: stage, decision, last write
    python -m dvr_cowork.jobs decide <video> ingest|fill-existing "<user words>"   Case 1 / Case 2 of one video
    python -m dvr_cowork.jobs check <video>                            Case 1: new, finished, decodable files of _check
    python -m dvr_cowork.jobs fill-report <video>                      Case 2: slots by tier, THIEU left + why
    python -m dvr_cowork.jobs reject <video> "<clip path fragment>" "<why>"   plan.py never picks it again for <video>
    python -m dvr_cowork.jobs metrics [--days=7]                       Claude tokens per day, Resolve writes
    python -m dvr_cowork.jobs --selftest

One Resolve writer at a time: backup_timeline() takes .work/automation/resolve_writer.lock for the life of its
process (the OS frees it when the process ends, even killed); a second writer stops with who holds it. A write row
stays RUNNING when its process was killed = interrupted: `status` names it with its backup timeline (rollback point).
"""
import atexit, datetime as dt, json, os, re, sqlite3, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".work" / "doc_edit"
DECISIONS = {"ingest": "INGEST_CHECK", "fill-existing": "FILL_EXISTING"}
VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".mkv", ".m4v"}
RECENT_DAYS = 10  # status lists videos whose plan.json changed in the last N days (or that have a decision)
SCHEMA = """
create table if not exists decisions(id integer primary key, video text, decision text, words text, at text);
create table if not exists writes(id integer primary key, project text, channel text, timeline text, backup text,
    script text, pid integer, status text, started text, ended text);
create table if not exists checked(hash text primary key, video text, path text, size integer, status text,
    note text, at text);
create table if not exists rejected(id integer primary key, video text, fragment text, why text, at text);
"""


def db_path():
    return Path(os.environ.get("DVR_JOBS_DB") or ROOT / ".work" / "automation" / "jobs.sqlite3")  # tests: a tmp file


def db():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=15)
    c.execute("pragma journal_mode=wal")
    c.executescript(SCHEMA)
    return c


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def script_name():
    p = Path(sys.argv[0])
    return p.parent.name if p.name == "__main__.py" else p.name  # python -m dvr_cowork vo-sync -> dvr_cowork


# ------------------------------------------------------------------ one Resolve writer (PR 2 / 5)
_lock, _rows, _failed = None, [], []


def _try_lock(f):
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def writer_busy():
    """Holder text of the Resolve writer lock when another live process has it, else None."""
    if _lock:
        return None
    p = db_path().with_name("resolve_writer.lock")
    if not p.exists():
        return None
    with open(p, "a+") as f:
        if _try_lock(f):
            return None
    who = p.with_suffix(".who")
    return who.read_text("utf-8").strip() if who.exists() else "another process"


def writer_begin(project, channel, timeline, backup):
    """Called by resolve_ops.backup_timeline before every Resolve change: takes the writer lock for this process
    (RuntimeError when another live process holds it) and logs the write (RUNNING -> ended / FAILED at exit)."""
    global _lock
    if _lock is None:
        p = db_path().with_name("resolve_writer.lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        f = open(p, "a+")
        if not _try_lock(f):
            f.close()
            raise RuntimeError(f"another Resolve write is running ({writer_busy()}): wait for it, never two at once")
        _lock = f
        p.with_suffix(".who").write_text(f"pid {os.getpid()} {script_name()} since {now()}", "utf-8")
        prev = sys.excepthook
        sys.excepthook = lambda *a: (_failed.append(1), prev(*a))
        atexit.register(_writer_end)
    try:  # the log never blocks a write
        with db() as c:
            _rows.append(c.execute("insert into writes(project, channel, timeline, backup, script, pid, status, started)"
                                   " values(?,?,?,?,?,?,?,?)", (project, channel, timeline, backup,
                                                               script_name(), os.getpid(), "RUNNING", now())
                                   ).lastrowid)
    except sqlite3.Error:
        pass


def _writer_end():
    try:
        with db() as c:
            for r in _rows:
                c.execute("update writes set status=?, ended=? where id=?", ("FAILED" if _failed else "ended", now(), r))
    except sqlite3.Error:
        pass


# ------------------------------------------------------------------ videos, decisions (PR 2)
def plan_of(video):
    p = DOC / video / "plan.json"
    if not p.exists():
        raise SystemExit(f"{video}: no .work/doc_edit/{video}/plan.json (plan it first)")
    return json.loads(p.read_text("utf-8"))


def place_of(video):
    """'vid_291026/Chann_2' (place.py's project.txt) or None."""
    p = DOC / video / "project.txt"
    return p.read_text("utf-8").strip() if p.exists() else None


def decide(video, kind, words):
    plan_of(video)
    with db() as c:
        c.execute("insert into decisions(video, decision, words, at) values(?,?,?,?)",
                  (video, DECISIONS[kind], words, now()))
    print(f"{video}: {DECISIONS[kind]} recorded ({words!r})")


def last_decision(c, video):
    return c.execute("select decision, at from decisions where video=? order by id desc limit 1", (video,)).fetchone()


def status():
    sys.path.insert(0, str(ROOT / ".claude/skills/doc-edit/scripts"))
    from state import stage
    cut = time.time() - RECENT_DAYS * 86400
    with db() as c:
        decided = {r[0] for r in c.execute("select distinct video from decisions")}
        vids = sorted({d.name for d in DOC.glob("*") if (d / "plan.json").exists()
                       and (d / "plan.json").stat().st_mtime > cut} | decided)
        busy = writer_busy()
        print(f"Resolve writer: {busy or 'free'}")
        for v in vids:
            pj = plan_of(v)
            vdir = Path(pj["video_dir"])
            if not vdir.is_dir():  # finished (moved to _done) or a test plan's folder: not in progress
                continue
            st, nxt = stage(vdir, False)
            d = last_decision(c, v)
            prompts = vdir / "missing_prompts.txt"
            if st.startswith("planned") and not place_of(v):  # place.py writes project.txt
                st, nxt = "planned, not placed", "/doc-edit <audios> (A2 + intro music + place)"
            elif st.startswith("planned, prompts out") and (not d or d[1] < dt.datetime.fromtimestamp(
                    prompts.stat().st_mtime).isoformat(timespec="seconds")):
                st, nxt = "WAITING_FOR_USER", "user: Case 1 (clips in _check) or Case 2 (fill THIẾU)"
            where = place_of(v)
            w = None
            if where:
                proj, _, ch = where.partition("/")
                w = c.execute("select status, script, backup, started from writes where project=? and "
                              "coalesce(channel,'')=? order by id desc limit 1", (proj, ch)).fetchone()
            line = f"  {v:<16} {pj.get('region', 'amazon'):<7} {where or '-':<20} {st:<22}"
            line += f" decision {d[0]} {d[1][:16]}" if d else ""
            if w:
                bad = w[0] == "RUNNING" and not busy
                line += f" | last write {w[1]} {w[3][:16]} {'INTERRUPTED' if bad else w[0]}"
                line += f" (rollback: backup {w[2]})" if bad or w[0] == "FAILED" else ""
            print(line + (f" | next: {nxt}" if nxt and nxt != "-" else ""))


# ------------------------------------------------------------------ Case 1: _check intake (PR 3)
def check_dir(region):
    from .config import load_config
    ai = Path(load_config()["paths"]["ai_video"])
    return ai / "_africa" / "_check" if region == "africa" else ai / "_check"


def decodes(p):
    """'' when ffprobe sees a video stream and the last second decodes (a truncated download fails here)."""
    sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
    from scan_source import probe
    m = probe(p)
    if not m.get("width") or (m.get("duration") or 0) < 0.5:
        return "no video stream / no duration"
    r = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-1", "-i", str(p), "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stderr.strip().splitlines() or ["ffmpeg failed"])[0][:80] if r.returncode else ""


def check(video, wait=3.0):
    """New files of the video's region _check: still copying (size moving), broken (not decodable) or ok; files seen
    by an earlier check are named, not re-read. Nothing is moved or deleted (the user removes broken files)."""
    sys.path.insert(0, str(ROOT / ".claude/skills/scan-source/scripts"))
    from scan_source import fast_hash
    region = plan_of(video).get("region", "amazon")
    d = check_dir(region)
    files = sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS) if d.is_dir() else []
    size = {p: p.stat().st_size for p in files}
    if files:
        time.sleep(wait)
    out = defaultdict(list)
    with db() as c:
        for p in files:
            if not p.exists() or p.stat().st_size != size[p] or size[p] == 0:
                out["copying"].append(p.name)
                continue
            h = fast_hash(p)
            if (r := c.execute("select video, status from checked where hash=?", (h,)).fetchone()) and r[1] == "ok":
                out["seen"].append(f"{p.name} ({r[0]})")
                continue
            why = decodes(p)
            c.execute("insert or replace into checked values(?,?,?,?,?,?,?)",
                      (h, video, str(p), size[p], "broken" if why else "ok", why, now()))
            out["broken" if why else "ok"].append(f"{p.name}: {why}" if why else p.name)
        others = [v for (v,) in c.execute("select distinct video from decisions where decision='INGEST_CHECK'")
                  if v != video and (DOC / v / "plan.json").exists()
                  and plan_of(v).get("region", "amazon") == region and last_decision(c, v)[0] == "INGEST_CHECK"]
    print(f"{video} ({region}) {d}: {len(files)} files | new ok {len(out['ok'])} | still copying "
          f"{len(out['copying'])} | broken {len(out['broken'])} | seen before {len(out['seen'])}")
    for k in ("copying", "broken"):
        if out[k]:
            print(f"  {k}: " + "; ".join(out[k]))
    if others:
        print(f"  SHARED _check: {', '.join(others)} also wait for clips in this region -> which clip is whose? ask")
    return out


# ------------------------------------------------------------------ Case 2: fill report + feedback (PR 4)
def tier(s):
    """Spec tier of one slot: A exact, B strong, C context, D last resort, THIEU (plan.py status / why / tier)."""
    st, why, t = s.get("status"), s.get("why") or "", s.get("tier") or ""
    if st in ("THIEU", "GFX"):
        return st
    if st == "OK":
        return "A exact"
    if st == "WEAK":
        return "B strong"
    if t.startswith(("species", "kin", "companion")) or why.startswith("same species"):
        return "B strong" if t.startswith("species") or why.startswith("same species") else "C context"
    if t.startswith(("scenery", "landscape")) or why == "side shot":
        return "C context"
    return "D last resort"


def clock(s):
    return f"{int(s) // 60:02d}:{s % 60:04.1f}"


def fill_report(video, show=40):
    slots = plan_of(video)["slots"]
    by = defaultdict(list)
    for s in slots:
        by[tier(s)].append(s)
    print(f"{video}: {len(slots)} slots | " + " | ".join(f"{k} {len(by[k])}" for k in
                                                         ("A exact", "B strong", "C context", "D last resort", "THIEU", "GFX")))
    sub = [s for s in slots if s.get("status") == "FALLBACK"]
    for s in sub[:show]:
        flag = " | any light: look" if "any light" in (s.get("tier") or "") else ""
        print(f"  {clock(s['start'])} #{s['slot']} {tier(s)} ({s.get('tier') or s.get('why')}) -> "
              f"{Path(s.get('path') or '').name}{flag}")
    for s in by["THIEU"][:show]:
        rej = ", ".join(f"{k} {n}" for k, n in (s.get("rej") or {}).items())
        print(f"  {clock(s['start'])} #{s['slot']} THIEU: {s.get('need', '')[:60]}" + (f" | refused: {rej}" if rej else ""))
    if len(sub) > show or len(by["THIEU"]) > show:
        print(f"  ... ({len(sub)} FALLBACK, {len(by['THIEU'])} THIEU in plan.md)")


def reject(video, fragment, why):
    plan_of(video)
    with db() as c:
        c.execute("insert into rejected(video, fragment, why, at) values(?,?,?,?)", (video, fragment, why, now()))
    print(f"{video}: clips matching {fragment!r} are never planned again ({why})")


def rejected(video):
    """Lower-case path fragments the user rejected for <video> (plan.py drops those clips; hard gates unchanged)."""
    try:
        with db() as c:
            return [r[0].lower() for r in c.execute("select fragment from rejected where video=?", (video,))]
    except sqlite3.Error:
        return []


# ------------------------------------------------------------------ measure (PR 6)
def transcripts():
    base = Path.home() / ".claude" / "projects"
    slug = re.sub(r"[^a-z0-9]", "-", str(ROOT).lower())
    return [p for d in base.glob("*") if d.name.lower() == slug for p in d.rglob("*.jsonl")]


def tokens(days, files=None):
    """{day: {input, output, cache_read, cache_write, calls}} from Claude Code transcripts (each API message once)."""
    cut = time.time() - days * 86400
    out, seen = defaultdict(lambda: defaultdict(int)), set()
    for f in files if files is not None else transcripts():
        if f.stat().st_mtime < cut:
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                m = o.get("message") or {}
                u, key = m.get("usage"), (m.get("id"), o.get("requestId"))
                if not u or key in seen or (o.get("timestamp") or "")[:10] < dt.date.fromtimestamp(cut).isoformat():
                    continue
                seen.add(key)
                d = out[o["timestamp"][:10]]
                d["input"] += u.get("input_tokens", 0)
                d["output"] += u.get("output_tokens", 0)
                d["cache_read"] += u.get("cache_read_input_tokens", 0)
                d["cache_write"] += u.get("cache_creation_input_tokens", 0)
                d["calls"] += 1
    return out


def metrics(days=7):
    t = tokens(days)
    print(f"Claude tokens per day (last {days} days, this workspace, subagents included):")
    for day in sorted(t):
        d = t[day]
        print(f"  {day}: input {d['input']:,} | output {d['output']:,} | cache read {d['cache_read']:,} | "
              f"cache write {d['cache_write']:,} | calls {d['calls']}")
    with db() as c:
        rows = c.execute("select script, status, started, ended from writes where started >= ?",
                         ((dt.datetime.now() - dt.timedelta(days=days)).isoformat(),)).fetchall()
    by = defaultdict(list)
    for s, st, a, b in rows:
        by[s].append((st, (dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds() if b else None))
    print("Resolve writes:" + ("" if by else " none logged yet"))
    for s, xs in sorted(by.items()):
        secs = [x for _, x in xs if x is not None]
        print(f"  {s}: {len(xs)} | median {sorted(secs)[len(secs) // 2]:.0f}s" if secs else f"  {s}: {len(xs)}", end="")
        print(f" | FAILED {sum(st == 'FAILED' for st, _ in xs)} | interrupted {sum(st == 'RUNNING' for st, _ in xs)}")


# ------------------------------------------------------------------ selftest
def selftest():
    import tempfile
    global DOC
    tmp = Path(tempfile.mkdtemp())
    os.environ["DVR_JOBS_DB"] = str(tmp / "jobs.sqlite3")
    DOC = tmp / "doc_edit"
    (DOC / "v1").mkdir(parents=True)
    (DOC / "v1" / "plan.json").write_text(json.dumps({"video_dir": str(tmp / "v1"), "region": "amazon", "slots": [
        {"slot": 1, "start": 0, "status": "OK"}, {"slot": 2, "start": 5, "status": "FALLBACK", "why": "late substitute",
                                                 "tier": "species"},
        {"slot": 3, "start": 9, "status": "FALLBACK", "why": "late substitute (broad)", "tier": "birds/insects, any light"},
        {"slot": 4, "start": 12, "status": "THIEU", "rej": {"sex": 2}}]}), "utf-8")
    assert [tier(s) for s in plan_of("v1")["slots"]] == ["A exact", "B strong", "D last resort", "THIEU"]
    assert tier({"status": "FALLBACK", "why": "side shot"}) == "C context"
    decide("v1", "fill-existing", "không generate nữa")
    with db() as c:
        assert last_decision(c, "v1")[0] == "FILL_EXISTING"
    reject("v1", r"Jaguar\run_3", "wrong species")
    assert rejected("v1") == [r"jaguar\run_3"] and rejected("v2") == []
    writer_begin("vid_1", "Chann_1", "Edit", "Edit_bak_x")  # lock taken by this process; a second call reuses it
    writer_begin("vid_1", "Chann_1", "Edit", "Edit_bak_y")
    assert writer_busy() is None
    r = subprocess.run([sys.executable, "-c", "from dvr_cowork import jobs; print(jobs.writer_busy())"],
                       capture_output=True, text=True, cwd=ROOT, env=os.environ)
    assert r.stdout.strip().startswith("pid "), r.stdout + r.stderr  # another process sees the holder
    r = subprocess.run([sys.executable, "-c", "from dvr_cowork import jobs; jobs.writer_begin('p', None, 'Edit', 'b')"],
                       capture_output=True, text=True, cwd=ROOT, env=os.environ)
    assert r.returncode and "another Resolve write is running" in r.stderr, r.stderr[-300:]
    with db() as c:
        assert c.execute("select count(*) from writes where status='RUNNING'").fetchone()[0] == 2
    _writer_end()
    with db() as c:
        assert c.execute("select count(*) from writes where status='ended'").fetchone()[0] == 2
    f = tmp / "t.jsonl"
    msg = {"timestamp": dt.date.today().isoformat() + "T10:00:00Z", "requestId": "r1",
           "message": {"id": "m1", "usage": {"input_tokens": 5, "output_tokens": 7, "cache_read_input_tokens": 100}}}
    f.write_text("\n".join(json.dumps(m) for m in (msg, msg, dict(msg, requestId="r2"))) + "\nnot json\n", "utf-8")
    d = tokens(1, [f])[dt.date.today().isoformat()]
    assert (d["input"], d["output"], d["cache_read"], d["calls"]) == (10, 14, 200, 2), dict(d)  # duplicate line once
    print("selftest ok")


def main(argv):
    a = [x for x in argv if not x.startswith("--")]
    if "--selftest" in argv:
        return selftest()
    cmd = a[0] if a else "status"
    if cmd == "status":
        status()
    elif cmd == "decide":
        decide(a[1], a[2], a[3] if len(a) > 3 else "")
    elif cmd == "check":
        check(a[1])
    elif cmd == "fill-report":
        fill_report(a[1])
    elif cmd == "reject":
        reject(a[1], a[2], a[3] if len(a) > 3 else "")
    elif cmd == "metrics":
        metrics(int(next((x.split("=")[1] for x in argv if x.startswith("--days=")), 7)))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
