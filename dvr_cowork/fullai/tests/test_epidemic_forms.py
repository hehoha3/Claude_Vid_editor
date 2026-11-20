import unittest
from dvr_cowork.videokey import epidemic_blocked
from dvr_cowork.fullai import intro_music as im

class T(unittest.TestCase):
    def test_epidemic_channels(self):
        f = r"D:\Audio_lib\intro\Song [es-1a2b3c4d] tense.mp3"
        self.assertTrue(epidemic_blocked(f, "Chann_1"))
        self.assertTrue(epidemic_blocked(f, None))
        self.assertFalse(epidemic_blocked(f, "Chann_2"))
        self.assertFalse(epidemic_blocked(f, "Chann_3"))
        self.assertFalse(epidemic_blocked(r"D:\Music\pixabay\x.mp3", "Chann_1"))

    def test_form_is_stable_and_valid(self):
        v = r"D:\Chann_3_FrozenWild\a_en_frozen_201126_1"
        self.assertEqual(im.form_of(v), im.form_of(v))
        self.assertIn(im.form_of(v), im.FORMS)

if __name__ == "__main__": unittest.main()
