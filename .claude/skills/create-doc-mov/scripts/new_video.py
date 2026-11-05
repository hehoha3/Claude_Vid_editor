"""Name and create the folders of new films: <region>_DDMMYY_<n>.

usage: python new_video.py CHANN:REGION [CHANN:REGION ...] [--date DDMMYY] [--apply]
       python new_video.py --selftest

  1:africa 2:africa  -> D:\\Chann_1_*\\africa_051126_1\\audios + D:\\Chann_2_*\\africa_051126_1\\audios
                        work .work\\doc_edit\\africa_051126_1__Chann_1 + africa_051126_1__Chann_2
One call = one day project vid_DDMMYY_<n> (user 2026-11-02): every channel of the call gets the SAME n, the next one
after the highest used today (D:\\Chann_*\\ and its _done, .work\\doc_edit; a name without _n counts as 1; never looks
inside _pushed). One film per channel per call. A name that lands in 2+ channels gets the work key <video>__Chann_N
(dvr_cowork/videokey.py, so doc-edit finds the same folder); a name in one channel keeps the plain key.
Dry run unless --apply; --apply creates <video>\\audios and .work\\doc_edit\\<key> (additive only) and verifies them.
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.videokey import SEP, channel_of, homes  # noqa: E402

D = Path("D:/")
WORK = ROOT / ".work" / "doc_edit"
TYPES = ("amazon", "africa", "himalaya")  # regions (user 2026-11-05): congo films are amazon


def used_today(day, chann_dirs, work):
    pat = re.compile(rf"^[a-z]+_{day}(?:_(\d+))?(?:{SEP}chann_\d+)?$", re.I)
    names = [p.name for p in work.iterdir()] if work.is_dir() else []
    for c in chann_dirs:
        for p in c.iterdir():
            if p.name == "_pushed":  # the user's alone (CLAUDE.md rule 5)
                continue
            names += [q.name for q in p.iterdir()] if p.name == "_done" else [p.name]
    return max([int(m.group(1) or 1) for n in names if (m := pat.match(n))], default=0)


def plan(jobs, day, d_root, work):
    """[(video, channel folder, work key)] for CHANN:REGION jobs; stops on a bad or repeated channel."""
    chann, seen = [], set()
    for j in jobs:
        n, kind = j.split(":", 1)
        hits = sorted(d_root.glob(f"Chann_{n}_*"))
        if len(hits) != 1 or kind.lower() not in TYPES:
            sys.exit(f"STOP {j}: channel folders {[h.name for h in hits]}, region must be one of {TYPES}")
        if n in seen:
            sys.exit(f"STOP {j}: Chann_{n} twice in one call (one film per channel per day project)")
        seen.add(n)
        chann.append((hits[0], kind.lower()))
    idx = used_today(day, sorted(d_root.glob("Chann_*")), work) + 1
    out = []
    for c, kind in chann:
        video = f"{kind}_{day}_{idx}"
        chans = {channel_of(h) for h in homes(video, [str(d_root / "Chann_*")])}
        chans |= {channel_of(c2) for c2, k2 in chann if k2 == kind}
        key = f"{video}{SEP}{channel_of(c)}" if len(chans) > 1 else video
        out.append((video, c, key))
    return out


def main():
    day = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else date.today().strftime("%d%m%y")
    for video, c, key in plan([a for a in sys.argv[1:] if ":" in a], day, D, WORK):
        audios, src = c / video / "audios", WORK / key
        if "--apply" in sys.argv:
            audios.mkdir(parents=True, exist_ok=False)
            src.mkdir(parents=True, exist_ok=True)
        ok = "OK" if audios.is_dir() and src.is_dir() else ("MISSING" if "--apply" in sys.argv else "dry-run")
        print(f"{video} | {audios} | src {src / 'four_files.src.md'} | {ok}")


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        for p in ("Chann_1_x/amazon_301026", "Chann_1_x/_done/amazon_301026_4", "Chann_2_y/africa_291026_9",
                  "Chann_2_y/_pushed/africa_301026_7", "work/africa_301026_2", "Chann_3_z"):
            (t / p).mkdir(parents=True)
        assert used_today("301026", [t / "Chann_1_x", t / "Chann_2_y"], t / "work") == 4
        assert used_today("311026", [t / "Chann_1_x"], t / "nowork") == 0
        (t / "work" / "africa_301026_6__Chann_2").mkdir()
        assert used_today("301026", [t / "Chann_1_x"], t / "work") == 6
        p = plan(["1:africa", "2:africa"], "311026", t, t / "work")  # same name, both keyed by channel
        assert [(v, k) for v, _, k in p] == [("africa_311026_1", "africa_311026_1__Chann_1"),
                                             ("africa_311026_1", "africa_311026_1__Chann_2")]
        p = plan(["1:amazon", "2:africa", "3:africa"], "311026", t, t / "work")  # same n, keys per shared name
        assert [(v, k) for v, _, k in p] == [("amazon_311026_1", "amazon_311026_1"),
                                             ("africa_311026_1", "africa_311026_1__Chann_2"),
                                             ("africa_311026_1", "africa_311026_1__Chann_3")]
        assert [k for _, _, k in plan(["2:africa"], "311026", t, t / "work")] == ["africa_311026_1"]
        (t / "Chann_1_x" / "africa_311026_1").mkdir()  # the name already lives in another channel
        assert [k for _, _, k in plan(["2:africa"], "311026", t, t / "work")] == ["africa_311026_2"]
        try:
            plan(["1:africa", "1:amazon"], "311026", t, t / "work")
            raise AssertionError("a channel twice in one call must stop")
        except SystemExit:
            pass
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
