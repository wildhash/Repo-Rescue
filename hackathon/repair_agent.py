"""Bounded repair loop: retrieve, propose, verify independently, store.

Safety boundaries from the Repo Rescue brief, enforced here:
- The proposer never verifies its own work; a separate verifier
  callable (a test command run in a sandbox/working copy) decides.
- Nothing is merged or deployed: the agent returns a patch and a
  verification result; a human reviews before any merge.
- Failed patches are recorded, not hidden, and are passed back as
  lessons on the next attempt so they are not repeated.
- The loop is bounded (max_attempts); it stops rather than looping
  forever on a failing repair.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .repair_memory import RepairEpisode, RepairMemory

# Verifier: (patch_text, working_dir) -> (passed: bool, evidence_ref: str)
Verifier = Callable[[str, str], tuple[bool, str]]


@dataclass
class RepairResult:
    success: bool
    attempts: int
    repeated_failed_actions: int
    patch: str | None
    elapsed_s: float
    episodes: list[RepairEpisode] = field(default_factory=list)


class RepairAgent:
    def __init__(
        self,
        memory: RepairMemory,
        proposer,
        verifier: Verifier,
        repo_revision: str,
        max_attempts: int = 3,
    ):
        self.memory = memory
        self.proposer = proposer
        self.verifier = verifier
        self.repo_revision = repo_revision
        self.max_attempts = max_attempts

    def repair(
        self,
        issue_fingerprint: str,
        issue: str,
        working_dir: str,
        test_command: str,
        constraints: str = "",
    ) -> RepairResult:
        start = time.time()
        lessons = self.memory.retrieve_relevant(issue_fingerprint, constraints)
        applicable = lessons["applicable"]
        lesson_dicts = [
            {
                "attempted_patch": ep.attempted_patch,
                "outcome": ep.outcome,
                "verifier_result": ep.verifier_result,
                "evidence_ref": ep.evidence_ref,
            }
            for ep in applicable
        ]
        known_failed = {
            ep.attempted_patch for ep in applicable if ep.outcome == "failure"
        }
        repeated = 0
        episodes: list[RepairEpisode] = []
        for attempt in range(1, self.max_attempts + 1):
            patch = self.proposer.propose(issue, lesson_dicts)
            if patch in known_failed:
                repeated += 1
            passed, evidence_ref = self.verifier(patch, working_dir)
            episode = self.memory.store(
                RepairEpisode(
                    repo_revision=self.repo_revision,
                    issue_fingerprint=issue_fingerprint,
                    attempted_patch=patch,
                    test_command=test_command,
                    verifier_result="pass" if passed else "fail",
                    evidence_ref=evidence_ref,
                    applicability_constraints=constraints,
                )
            )
            episodes.append(episode)
            if passed:
                return RepairResult(
                    success=True,
                    attempts=attempt,
                    repeated_failed_actions=repeated,
                    patch=patch,
                    elapsed_s=time.time() - start,
                    episodes=episodes,
                )
            # Feed the new failure back in so the next attempt cannot
            # claim ignorance of it, even within this session.
            lesson_dicts.append(
                {
                    "attempted_patch": patch,
                    "outcome": "failure",
                    "verifier_result": "fail",
                    "evidence_ref": evidence_ref,
                }
            )
            known_failed.add(patch)
        return RepairResult(
            success=False,
            attempts=self.max_attempts,
            repeated_failed_actions=repeated,
            patch=None,
            elapsed_s=time.time() - start,
            episodes=episodes,
        )
