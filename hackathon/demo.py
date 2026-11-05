"""Two-session demo + memory-off control, as specified in the brief.

Session 1 (teach): a fresh agent, no prior lessons. It tries the
known-bad patch first, fails independent verification, then succeeds;
both outcomes are stored with evidence.
Session 2 (fresh session, same memory file, no conversational
history): a new agent object retrieves the lessons and must not
repeat the failed patch.
Control (memory off): a new agent with an empty memory repeats the
failed patch before succeeding.

Run:  python -m hackathon.demo   (from the repo-rescue directory)
Output: JSON report with repair success, repeated failed actions,
attempts, proposer calls and wall-clock time per arm.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .meta_client import StubProposer
from .repair_agent import RepairAgent
from .repair_memory import RepairMemory

FIXTURE = Path(__file__).resolve().parent.parent / "demo_fixture"
ISSUE = (
    "serialize_user fails after a schema change: users now carry "
    "'full_name' instead of 'username'; test_api.py expects "
    "{'id': 42, 'name': 'Ada'} for {'id': 42, 'full_name': 'Ada'}."
)
FINGERPRINT = "serialize_user schema change full_name"
REVISION = "demo-fixture-v1"


def make_verifier():
    def verify(patch: str, working_dir: str):
        work = Path(working_dir)
        shutil.copy(FIXTURE / "api.py", work / "api.py")
        shutil.copy(FIXTURE / "test_api.py", work / "test_api.py")
        src = (work / "api.py").read_text()
        # The patch is the replacement expression for user["username"].
        patched = src.replace('user["username"]', patch)
        (work / "api.py").write_text(patched)
        proc = subprocess.run(
            [sys.executable, "test_api.py"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=30,
        )
        evidence = (proc.stdout + proc.stderr).strip().splitlines()
        evidence_ref = evidence[0] if evidence else f"exit={proc.returncode}"
        return proc.returncode == 0, evidence_ref

    return verify


def run_session(memory: RepairMemory, proposer) -> dict:
    with tempfile.TemporaryDirectory() as work:
        agent = RepairAgent(
            memory=memory,
            proposer=proposer,
            verifier=make_verifier(),
            repo_revision=REVISION,
        )
        result = agent.repair(
            issue_fingerprint=FINGERPRINT,
            issue=ISSUE,
            working_dir=work,
            test_command="python test_api.py",
        )
    return {
        "success": result.success,
        "attempts": result.attempts,
        "repeated_failed_actions": result.repeated_failed_actions,
        "patch": result.patch,
        "elapsed_s": round(result.elapsed_s, 3),
        "proposer_calls": getattr(proposer, "calls", None),
    }


def main() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "repair_memory.db"
        # Session 1: teach.
        memory1 = RepairMemory(db)
        session1 = run_session(memory1, StubProposer())
        memory1.close()
        # Session 2: completely fresh agent, same memory file only.
        memory2 = RepairMemory(db)
        session2 = run_session(memory2, StubProposer())
        memory2.close()
        # Control: fresh agent, empty memory.
        memory_off = RepairMemory(Path(tmp) / "empty.db")
        control = run_session(memory_off, StubProposer())
        memory_off.close()
    report = {
        "session_1_teach": session1,
        "session_2_fresh_with_memory": session2,
        "control_memory_off": control,
        "claim": (
            "Session 2 succeeds in 1 attempt using the stored lessons; "
            "the memory-off control needs 2 attempts, re-trying the "
            "failure session 1 had already stored. Stub proposer "
            "only; not a live-model result."
        ),
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
