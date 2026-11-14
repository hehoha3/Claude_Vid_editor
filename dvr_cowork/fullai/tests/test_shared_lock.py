import unittest

from dvr_cowork.fullai import core
from dvr_cowork import jobs


class SharedWriterLock(unittest.TestCase):
    def test_8p_holds_the_1h_writer_lock(self):
        # Fails if a real Resolve write is running right now: rerun after it.
        self.assertEqual(core.WRITER, jobs.db_path().with_name("resolve_writer.lock"))
        with core.resolve_lock():
            self.assertIn("dvr_cowork ai", jobs.writer_busy() or "")
        self.assertIsNone(jobs.writer_busy())


if __name__ == "__main__":
    unittest.main()
