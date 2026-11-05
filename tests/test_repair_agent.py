import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hackathon.demo import make_verifier  # noqa: E402
from hackathon.meta_client import StubProposer  # noqa: E402
from hackathon.repair_agent import RepairAgent  # noqa: E402
from hackathon.repair_memory import RepairMemory  # noqa: E402

ISSUE = "serialize_user schema change"
FP = "serialize_user schema change full_name"


def run(memory, proposer):
    with tempfile.TemporaryDirectory() as work:
        agent = RepairAgent(memory, proposer, make_verifier(), "demo-fixture-v1")
        return agent.repair(FP, ISSUE, work, "python test_api.py")


class TestRepairAgent(unittest.TestCase):
    def test_fresh_session_avoids_stored_failure_control_repeats_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "m.db"
            mem = RepairMemory(db)
            first = run(mem, StubProposer())
            self.assertTrue(first.success)
            self.assertEqual(first.attempts, 2)  # bad, then good
            mem.close()

            mem2 = RepairMemory(db)  # fresh session, same memory file
            second = run(mem2, StubProposer())
            self.assertTrue(second.success)
            self.assertEqual(second.attempts, 1)
            self.assertEqual(second.repeated_failed_actions, 0)
            mem2.close()

            mem_off = RepairMemory(Path(tmp) / "empty.db")
            control = run(mem_off, StubProposer())
            self.assertTrue(control.success)
            self.assertEqual(control.attempts, 2)  # repeats the failure
            mem_off.close()

    def test_bounded_attempts_on_unfixable_issue(self):
        def always_fail(patch, work):
            return False, "exit=1"

        with tempfile.TemporaryDirectory() as tmp:
            mem = RepairMemory(Path(tmp) / "m.db")
            with tempfile.TemporaryDirectory() as work:
                agent = RepairAgent(mem, StubProposer(), always_fail, "r1", max_attempts=2)
                result = agent.repair("fp", "issue", work, "t")
            self.assertFalse(result.success)
            self.assertEqual(result.attempts, 2)
            mem.close()


if __name__ == "__main__":
    unittest.main()
