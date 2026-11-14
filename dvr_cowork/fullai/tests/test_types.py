"""Video types v3 (user 2026-11-12): f_ / fa_ / a_ prefix, frozen region, 8-180 min, stories from the runtime."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from dvr_cowork import profile as dvr_profile, vtypes
from dvr_cowork.fullai import core, story


def scene(j, phase, seconds, k_story):
    shots = [] if phase == "hook" else [
        {"duration_s": 5, "title": f"Shot {j}/{k}", "characters": ["M", "K"], "action": f"Action {j}/{k}",
         "camera": f"camera {k}", "direction": "left to right", "start_state": f"ledge {j}-{k}",
         "end_state": f"ledge {j}-{k + 1}", "beats": [f"Leap {j}/{k}/a", f"Sprint {j}/{k}/b"],
         "hook_role": "none", "intensity": min(k, 5)} for k in range(seconds // 5)]
    voice = [{"en": " ".join([f"line{j}_{i}"] * 32), "vi": f"Lời dẫn thử {j} phần {i}, chỉ để kiểm tra thời gian."}
             for i in range(seconds // 15)]
    sc = {"id": f"S{j}", "title": f"Scene {j}", "phase": phase, "change": f"Change {j}", "voice": voice, "story": k_story}
    if shots:
        sc["shots"] = shots
    return sc


def two_story_source():
    """20 min: 90 s hook, story 1 (30 s setup + 8 x 60 + 60 ending), story 2 (60 setup + 7 x 60 + 60 ending)."""
    plan = [("hook", 90, 1), ("setup", 30, 1)] + [("story", 60, 1)] * 8 + [("ending", 60, 1)] \
        + [("setup", 60, 2)] + [("story", 60, 2)] * 7 + [("ending", 60, 2)]
    return {"schema": 2, "title": "Two stories", "target_minutes": 20, "fps": 24, "wpm": 145,
            "premise": "p", "central_question": "q", "payoff": "a",
            "characters": [{"id": "M", "species": "ibex", "count": 1, "terms": ["mother"], "lock": "One adult female",
                            "details": ["leads"]},
                           {"id": "K", "species": "ibex", "count": 1, "terms": ["kid"], "lock": "One small kid",
                            "details": ["follows"]}],
            "environment": "Neutral daylight, white snow.", "geography": "One cliff.",
            "synthetic_disclosure": "AI-generated dramatization.", "count_lock": ["2 ibex"], "zones": ["shelf"],
            "terrain_lock": ["rock"], "light_lock": ["daylight"],
            "scenes": [scene(j, ph, sec, k) for j, (ph, sec, k) in enumerate(plan)]}


class TypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_prefix_detection_and_pin_resolves_long_intro(self):
        a = self.root / "Chann_3_x" / "a_frozen_121126_1"
        a.mkdir(parents=True)
        info = dvr_profile.detect(a)
        self.assertEqual((info["source"], info["type"], info["profile"], info["region"]), ("name", "full_ai", "full_ai", "frozen"))
        dvr_profile.create(a, "full_ai", minutes=20)
        d, p = dvr_profile.pinned(a)
        self.assertEqual((d["region_id"], p["intro"]["duration_s"], "intro_long" in p), ("frozen", 90, False))
        self.assertEqual(dvr_profile.detect(a)["source"], "descriptor")
        short = self.root / "Chann_3_x" / "a_frozen_121126_2"
        short.mkdir()
        dvr_profile.create(short, "full_ai", minutes=12)
        self.assertEqual(dvr_profile.pinned(short)[1]["intro"]["duration_s"], 30)
        f = self.root / "Chann_1_y" / "f_africa_121126_1"
        f.mkdir(parents=True)
        self.assertEqual(dvr_profile.detect(f)["type"], "footage")
        self.assertEqual(dvr_profile.context(f, "edit")["ai_max"], 0.0)
        with self.assertRaisesRegex(core.Stop, "is a footage film"):
            dvr_profile.create(f, "full_ai", minutes=10)

    def test_two_story_film_compiles_and_counts_are_checked(self):
        p = dvr_profile.for_runtime(dvr_profile.load("full_ai"), 20)
        plan = story.compile_story(two_story_source(), None, p)
        self.assertEqual(plan["runtime_f"], 20 * 60 * 24)
        self.assertEqual(plan["slots"][0]["end_f"], 90 * 24)
        self.assertEqual(sorted({sc["story"] for sc in plan["scenes"]}), [1, 2])
        self.assertIn("## Story 2 · ", story.documents(plan)["screenplay.md"])
        one = two_story_source()
        for sc in one["scenes"]:
            sc["story"] = 1
        one["scenes"][11]["phase"] = "story"  # story 2's setup becomes a story scene of story 1
        one["scenes"][10]["phase"] = "story"  # ... and story 1's ending a plain scene
        with self.assertRaisesRegex(core.Stop, "1 stories in 20 min"):
            story.compile_story(copy.deepcopy(one), None, p)
        one["stories_reason"] = "user asked for one long story"
        story.compile_story(one, None, p)
        bad = two_story_source()
        bad["scenes"][12]["phase"] = "setup"  # a setup inside story 2, not its first scene
        with self.assertRaisesRegex(core.Stop, "setup only as scene 2"):
            story.compile_story(bad, None, p)

    def test_region_alias_and_story_math(self):
        self.assertEqual(story.region_locks("himalaya"), story.region_locks("frozen"))
        self.assertEqual(vtypes.stories(15)["options"][1]["story_min"], [8.0, 6.0])
        self.assertEqual(vtypes.check_dir("himalaya").parts[-2:], ("_frozen", "_check"))


if __name__ == "__main__":
    unittest.main()
