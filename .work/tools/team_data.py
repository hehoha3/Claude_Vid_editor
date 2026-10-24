"""Team data pack (2026-10-24): the code is shared with every team through git; each team's working data (library
indexes + tags, plans, ledgers, memory notes, licenses...) travels as one zip inside the team, never through git.

    .venv/Scripts/python.exe .work/tools/team_data.py list                      # what counts as team data here
    .venv/Scripts/python.exe .work/tools/team_data.py export D:\\team_data.zip   # pack it (nothing is changed)
    .venv/Scripts/python.exe .work/tools/team_data.py import D:\\team_data.zip [--overwrite]
    .venv/Scripts/python.exe .work/tools/team_data.py clean --pack D:\\team_data.zip [--apply]
    .venv/Scripts/python.exe .work/tools/team_data.py --selftest

Team data = everything under .work/ except .work/tools/ (code, in git), plus input/ and .claude/settings.local.json.
Rebuilt by the tools, so never packed (but removed by clean): .work/memory/ (memory_gateway.py index), tag sheets of
tagged / applied batches, caption vectors, colour frame caches. Sheets of batches still waiting ARE packed (prepare
never re-makes them: the paused retag goes on from the pack).
clean: dry run unless --apply; refuses unless --pack is an export that holds every packed file with the same size;
files are unlinked one by one, empty folders removed with rmdir (never rmtree). The user runs --apply.
"""
import json, os, sys, time, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
EXTRA = ["input", ".claude/settings.local.json"]
REBUILD = [".work/memory", ".work/tag_source/sheets", ".work/doc_edit/caption_emb_e5small.npz",
           ".work/grade/frames320", ".work/grade/frames", ".work/yolo_runs"]
MANIFEST = "team_data_manifest.json"


def rel(p, root):
    return PurePosixPath(p.relative_to(root)).as_posix()


def team_files(root):
    """-> (packed, rebuildable) relative posix paths of the team data under root."""
    out = []
    w = root / ".work"
    if w.is_dir():
        out += [f for f in w.rglob("*") if f.is_file() and not f.is_relative_to(w / "tools")]
    for e in EXTRA:
        p = root / e
        out += [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else []
    names = sorted(rel(f, root) for f in out if "__pycache__" not in f.parts)
    # sheets of batches still waiting to be tagged are packed: prepare never re-makes the sheet of a queued clip
    pending = set()
    for b in (w / "tag_source").glob("batch_*.json") if w.is_dir() else []:
        if "result" not in b.stem and not b.with_name(b.stem + "_result.json").exists():
            pending |= {Path(r["image"]).name for r in json.loads(b.read_text("utf-8")) if r.get("image")}
    rb = [n for n in names if any(n == r or n.startswith(r + "/") for r in REBUILD)
          and not (n.startswith(".work/tag_source/sheets/") and PurePosixPath(n).name in pending)]
    rbs = set(rb)
    return [n for n in names if n not in rbs], rb


def export(root, dst):
    packed, rb = team_files(root)
    dst = Path(dst)
    assert not dst.exists(), f"{dst} exists: choose a new name"
    size = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n in packed:
            z.write(root / n, n)
            size += (root / n).stat().st_size
        z.writestr(MANIFEST, json.dumps({"created": time.strftime("%Y-%m-%d %H:%M"), "files": len(packed),
                                         "bytes": size}, indent=1))
    with zipfile.ZipFile(dst) as z:  # verify
        got = {i.filename: i.file_size for i in z.infolist()}
    bad = [n for n in packed if got.get(n) != (root / n).stat().st_size]
    assert not bad, f"pack incomplete: {bad[:5]}"
    print(f"export: {len(packed)} files, {size / 1e6:.0f} MB -> {dst} ({dst.stat().st_size / 1e6:.0f} MB zipped, verified); "
          f"not packed (rebuilt by the tools): {len(rb)} files")


def safe_name(n):
    p = PurePosixPath(n)
    return not p.is_absolute() and ".." not in p.parts and ":" not in n and \
        (p.parts[:1] == (".work",) and p.parts[1:2] != ("tools",) or p.parts[:1] == ("input",)
         or n == ".claude/settings.local.json" or n == MANIFEST)


def do_import(root, src, overwrite=False):
    with zipfile.ZipFile(src) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        bad = [i.filename for i in infos if not safe_name(i.filename)]
        assert not bad, f"refused, not team data paths: {bad[:5]}"
        new = same = kept = 0
        conflicts = []
        for i in infos:
            if i.filename == MANIFEST:
                continue
            t = root / i.filename
            if t.exists():
                if t.stat().st_size == i.file_size:
                    same += 1
                    continue
                if not overwrite:
                    conflicts.append(i.filename); kept += 1
                    continue
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(z.read(i))
            new += 1
    print(f"import: {new} files written, {same} already the same, {kept} different files kept (--overwrite replaces)"
          + (": " + ", ".join(conflicts[:10]) if conflicts else ""))
    print("next: memory_gateway.py index, library_db.py sync (if PostgreSQL is set up), tag_source.py status")


def clean(root, pack, apply=False):
    packed, rb = team_files(root)
    assert pack and Path(pack).is_file(), "clean needs --pack <zip from export> (the data must be packed first)"
    with zipfile.ZipFile(pack) as z:
        got = {i.filename: i.file_size for i in z.infolist()}
    missing = [n for n in packed if got.get(n) != (root / n).stat().st_size]
    assert not missing, f"{len(missing)} files are not in {pack} as they are now (export again): {missing[:8]}"
    files = packed + rb
    size = sum((root / n).stat().st_size for n in files)
    print(f"clean: {len(files)} files, {size / 1e6:.0f} MB ({len(packed)} in the pack, {len(rb)} rebuildable)")
    for top in sorted({"/".join(n.split("/")[:2]) for n in files}):
        print("  ", top)
    if not apply:
        print("dry run: nothing deleted (add --apply)")
        return
    for n in files:
        (root / n).unlink()
    dirs = sorted({d for n in files for d in (root / n).parents if d != root and d.is_relative_to(root)},
                  key=lambda d: -len(d.parts))
    for d in dirs:
        if d.is_dir() and not any(d.iterdir()) and d not in (root / ".work", root / ".claude"):
            d.rmdir()
    left, _ = team_files(root)
    print(f"deleted {len(files)} files; team data left: {len(left)}")


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = Path(t) / "repo"
        for n, b in {".work/library/a.json": b"{}", ".work/tools/x.py": b"code", ".work/memory/k.db": b"db",
                     ".work/doc_edit/v/plan.json": b"[1]", "input/plan.md": b"p", ".claude/settings.local.json": b"{}",
                     "README.md": b"r"}.items():
            (r / n).parent.mkdir(parents=True, exist_ok=True)
            (r / n).write_bytes(b)
        packed, rb = team_files(r)
        assert packed == [".claude/settings.local.json", ".work/doc_edit/v/plan.json", ".work/library/a.json",
                          "input/plan.md"] and rb == [".work/memory/k.db"], (packed, rb)
        z = Path(t) / "p.zip"
        export(r, z)
        try:
            clean(r, Path(t) / "none.zip")
            raise SystemExit("selftest: clean ran without a pack")
        except AssertionError:
            pass
        (r / ".work/library/a.json").write_bytes(b'{"changed": 1}')
        try:
            clean(r, z, apply=True)
            raise SystemExit("selftest: clean ran with a stale pack")
        except AssertionError:
            pass
        (r / ".work/library/a.json").write_bytes(b"{}")
        clean(r, z, apply=True)
        assert team_files(r) == ([], []) and (r / ".work/tools/x.py").exists() and (r / "README.md").exists()
        do_import(r, z)
        assert (r / ".work/library/a.json").read_bytes() == b"{}" and (r / "input/plan.md").exists()
        assert not safe_name("../evil.py") and not safe_name(".work/tools/x.py") and not safe_name("C:/x")
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None  # noqa: E731
    if a[:1] == ["--selftest"]:
        selftest()
    elif a[:1] == ["list"]:
        p, r = team_files(ROOT)
        tops = {}
        for i, names in enumerate((p, r)):
            for n in names:
                k = "/".join(n.split("/")[:2 if n.startswith(".") else 1])
                tops.setdefault(k, [0, 0])[i] += (ROOT / n).stat().st_size
        print("   packed  rebuildable")
        for k, (a_, b_) in sorted(tops.items()):
            print(f"{a_ / 1e6:7.1f} MB {b_ / 1e6:8.1f} MB  {k}")
        print(f"{len(p)} files packed by export, {len(r)} rebuildable (not packed, removed by clean)")
    elif a[:1] == ["export"] and len(a) > 1:
        export(ROOT, a[1])
    elif a[:1] == ["import"] and len(a) > 1:
        do_import(ROOT, a[1], "--overwrite" in a)
    elif a[:1] == ["clean"]:
        clean(ROOT, opt("--pack"), "--apply" in a)
    else:
        print(__doc__)
