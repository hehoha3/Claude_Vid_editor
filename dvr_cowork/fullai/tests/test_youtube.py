"""Channel folder naming of `dvr_cowork youtube login`, on a temp dir (never D:)."""
import tempfile
import unittest
from pathlib import Path

from dvr_cowork.fullai.core import Stop
from dvr_cowork.youtube import camel, channel_folder


class FolderTests(unittest.TestCase):
    def test_camel(self):
        self.assertEqual(camel("Wild Peril"), "WildPeril")
        self.assertEqual(camel("wild  peril - 4K!"), "WildPeril4K")
        self.assertEqual(camel("Hoang dã Việt"), "HoangDãViệt")

    def test_create_keep_rename_and_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.assertEqual(channel_folder("Chann_2", "Wild Peril", base)["action"], "created")
            self.assertEqual(channel_folder("Chann_2", "Wild Peril", base)["action"], "kept")
            (base / "Chann_2_WildPeril" / "vid_1").mkdir()
            self.assertTrue(channel_folder("Chann_2", "Frozen Edge", base)["action"].startswith("renamed"))
            self.assertTrue((base / "Chann_2_FrozenEdge" / "vid_1").is_dir())
            self.assertEqual(channel_folder("Chann_1", "Wild Peril", base)["action"], "created")  # never Chann_12_*
            (base / "Chann_2_Extra").mkdir()
            with self.assertRaises(Stop): channel_folder("Chann_2", "X", base)
            with self.assertRaises(Stop): channel_folder("Chann_3", "!!!", base)
