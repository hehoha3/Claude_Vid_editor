import unittest
from dvr_cowork.resolve_ops import story_start
from dvr_cowork.fullai.tests.fake_resolve import Item


class StoryStart(unittest.TestCase):
    def test_black_gap_nearest_the_plan_intro(self):
        # intro cuts to 2160, story 1 landscape under the intro music to 2268, black, story shot at 2316
        v = [Item(None, a, b, 0) for a, b in ((0, 60), (60, 2160), (2160, 2268), (2316, 2500), (2520, 2600))]
        self.assertEqual(story_start(v, 2160, 240), 3)  # the gap at 2268-2316, not the plan's 2160
        self.assertEqual(story_start(v, 2600, 10), 0)   # no gap near: caller falls back on the plan


if __name__ == "__main__":
    unittest.main()
