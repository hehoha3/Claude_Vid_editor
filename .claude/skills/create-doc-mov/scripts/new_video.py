"""Name and create the folders of new films: <region>_DDMMYY_<n>.

usage: python new_video.py CHANN:REGION [CHANN:REGION ...] [--date DDMMYY] [--apply]
       python new_video.py --selftest

  1:africa 2:africa  -> D:\\Chann_1_*\\africa_051126_1\\audios + D:\\Chann_2_*\\africa_051126_1\\audios
                        work .work\\doc_edit\\africa_051126_1__Chann_1 + africa_051126_1__Chann_2
Every film is in the day project vid_DDMMYY. Each channel numbers its own films (user 2026-11-09): n = 1 + the
highest n that channel used today (its folder and _done, its .work\\doc_edit keys; a name without _n counts as 1;
never inside _pushed), so Chann_3's first film of the day is _1 even when Chann_1 already made one
(dvr_cowork/videokey.py day_index; the full-AI `ai next-video` uses the same rule). One film per channel per call.
A name that lands in 2+ channels gets the work key <video>__Chann_N (videokey.py, so doc-edit finds the same folder);
a name in one channel keeps the plain key. A new twin of a film that still has the plain key would hide that film's
work folder from doc-edit: stop and ask the user. Dry run unless --apply; --apply creates <video>\\audios and
.work\\doc_edit\\<key> (additive only) and verifies them.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from dvr_cowork.videokey import SEP, channel_of, day_index, homes  # noqa: E402

D = Path("D:/")
WORK = ROOT / ".work" / "doc_edit"
TYPES = ("amazon", "africa", "himalaya")  # regions (user 2026-11-05): congo films are amazon


def plan(jobs, day, d_root, work):
    """[(video, channel folder, work key)] for CHANN:REGION jobs; stops on a bad or repeated channel, or on a twin of a
    film in another channel that still uses the plain work key."""
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
    films = [(f"{kind}_{day}_{day_index(day, c, work)}", c) for c, kind in chann]
    out = []
    for video, c in films:
        there = {channel_of(h) for h in homes(video, [str(d_root / "Chann_*")])} - {channel_of(c)}
        if there and (work / video).is_dir():
            sys.exit(f"STOP {video}: {', '.join(sorted(there))} already has {video} with the plain work key "
                     f"{work / video}; a second {video} in {channel_of(c)} would hide it from doc-edit. Ask the user.")
        chans = there | {channel_of(c2) for v2, c2 in films if v2 == video}
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
        w = t / "work"
        # each channel numbers its own day: Chann_1 used 1 and 4, the homeless plain key africa_301026_2 counts for all
        assert [v for v, _, _ in plan(["1:amazon", "2:africa", "3:himalaya"], "301026", t, w)] == \
            ["amazon_301026_5", "africa_301026_3", "himalaya_301026_3"]
        (w / "africa_301026_6__Chann_2").mkdir()  # a key of Chann_2 counts for Chann_2 only
        assert [v for v, _, _ in plan(["2:africa", "3:amazon"], "301026", t, w)] == ["africa_301026_7", "amazon_301026_3"]
        p = plan(["1:africa", "2:africa"], "311026", t, w)  # same name, both keyed by channel
        assert [(v, k) for v, _, k in p] == [("africa_311026_1", "africa_311026_1__Chann_1"),
                                             ("africa_311026_1", "africa_311026_1__Chann_2")]
        p = plan(["1:amazon", "2:africa", "3:africa"], "311026", t, w)  # keys per shared name
        assert [(v, k) for v, _, k in p] == [("amazon_311026_1", "amazon_311026_1"),
                                             ("africa_311026_1", "africa_311026_1__Chann_2"),
                                             ("africa_311026_1", "africa_311026_1__Chann_3")]
        (t / "Chann_1_x" / "africa_311026_1").mkdir()  # Chann_1's first film today (user's example)
        (w / "africa_311026_1__Chann_1").mkdir()
        assert [(v, k) for v, _, k in plan(["3:himalaya"], "311026", t, w)] == [("himalaya_311026_1", "himalaya_311026_1")]
        assert [v for v, _, _ in plan(["1:africa"], "311026", t, w)] == ["africa_311026_2"]
        assert [k for _, _, k in plan(["2:africa"], "311026", t, w)] == ["africa_311026_1__Chann_2"]  # keyed twin
        (t / "Chann_1_x" / "amazon_311026_1").mkdir()
        (w / "amazon_311026_1").mkdir()  # Chann_1's film with the plain key: a twin in Chann_2 must stop
        for jobs in (["2:amazon"], ["1:africa", "1:amazon"]):
            try:
                plan(jobs, "311026", t, w)
                raise AssertionError(f"{jobs} must stop")
            except SystemExit:
                pass
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
