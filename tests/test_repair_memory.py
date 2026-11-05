import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hackathon.repair_memory import RepairEpisode, RepairMemory  # noqa: E402


class TestRepairMemory(unittest.TestCase):
    def test_persists_across_reopen_and_splits_by_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "m.db"
            mem = RepairMemory(db)
            mem.store(RepairEpisode("r1", "fp", "bad", "python t.py", "fail", "exit=1"))
            mem.store(RepairEpisode("r1", "fp", "good", "python t.py", "pass", "PASS"))
            mem.close()
            # Fresh object, same file: a new session, no shared history.
            mem2 = RepairMemory(db)
            lessons = mem2.retrieve_relevant("fp")
            self.assertEqual(len(lessons["applicable"]), 2)
            self.assertEqual(mem2.failed_patches("fp"), ["bad"])
            self.assertEqual(
                [e.outcome for e in lessons["applicable"]],
                ["failure", "success"],
            )
            mem2.close()

    def test_inapplicable_constraints_are_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = RepairMemory(Path(tmp) / "m.db")
            mem.store(
                RepairEpisode(
                    "r1", "fp", "good", "python t.py", "pass", "PASS",
                    applicability_constraints="python>=3.12",
                )
            )
            lessons = mem.retrieve_relevant("fp", constraints="python>=3.11")
            self.assertEqual(lessons["applicable"], [])
            self.assertEqual(len(lessons["inapplicable"]), 1)
            mem.close()

    def test_unrelated_fingerprint_not_retrieved(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = RepairMemory(Path(tmp) / "m.db")
            mem.store(RepairEpisode("r1", "fp-a", "x", "t", "pass", "PASS"))
            self.assertEqual(mem.retrieve_relevant("fp-b")["applicable"], [])
            mem.close()


if __name__ == "__main__":
    unittest.main()
