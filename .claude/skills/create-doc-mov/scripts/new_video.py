"""Name and create the folders of new films: <story_type>_DDMMYY_<n>.

usage: python new_video.py CHANN:TYPE [CHANN:TYPE ...] [--date DDMMYY] [--apply]
       python new_video.py --selftest

  1:amazon 2:africa  -> D:\\Chann_1_*\\amazon_301026_3\\audios, D:\\Chann_2_*\\africa_301026_4\\audios
n = one index per day across every channel, in argument order, after the highest one already used today
(D:\\Chann_*\\ and its _done, .work\\doc_edit; a name without _n counts as 1), so a video name is unique for
.work\\doc_edit. Never looks inside _pushed. Dry run unless --apply; --apply creates <video>\\audios and
.work\\doc_edit\\<video> (additive only) and verifies them.
"""
import re
import sys
from datetime import date
from pathlib import Path

D = Path("D:/")
WORK = Path(__file__).resolve().parents[4] / ".work" / "doc_edit"
TYPES = ("amazon", "africa", "congo")


def used_today(day, chann_dirs, work):
    pat = re.compile(rf"^[a-z]+_{day}(?:_(\d+))?$", re.I)
    names = [p.name for p in work.iterdir()] if work.is_dir() else []
    for c in chann_dirs:
        for p in c.iterdir():
            if p.name == "_pushed":  # the user's alone (CLAUDE.md rule 5)
                continue
            names += [q.name for q in p.iterdir()] if p.name == "_done" else [p.name]
    return max([int(m.group(1) or 1) for n in names if (m := pat.match(n))], default=0)


def main():
    day = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else date.today().strftime("%d%m%y")
    jobs = [a for a in sys.argv[1:] if ":" in a]
    chann = {}
    for j in jobs:
        n, kind = j.split(":", 1)
        hits = sorted(D.glob(f"Chann_{n}_*"))
        if len(hits) != 1 or kind.lower() not in TYPES:
            sys.exit(f"STOP {j}: channel folders {[h.name for h in hits]}, type must be one of {TYPES}")
        chann[j] = (hits[0], kind.lower())
    idx = used_today(day, sorted(D.glob("Chann_*")), WORK)
    for j in jobs:
        c, kind = chann[j]
        idx += 1
        video = f"{kind}_{day}_{idx}"
        audios, src = c / video / "audios", WORK / video
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
                  "Chann_2_y/_pushed/africa_301026_7", "work/africa_301026_2"):
            (t / p).mkdir(parents=True)
        assert used_today("301026", [t / "Chann_1_x", t / "Chann_2_y"], t / "work") == 4
        assert used_today("311026", [t / "Chann_1_x"], t / "nowork") == 0
    print("selftest PASS")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
