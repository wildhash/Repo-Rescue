"""Persistent, evidence-linked repair episodes.

This is the piece RepoMan's pattern/strategy memory does not have: a
durable record of one attempted repair, tied to the repository revision
and test evidence that proved it, so a later, independent session can
retrieve it and decide whether it still applies.

Design rules carried over from the Repo Rescue brief:
- Store successful AND failed attempts, with provenance.
- Never silently convert an unverified claim into a fact: an episode is
  only stored after an independent verifier has run.
- Retrieval is relevance-gated: exact issue fingerprint first; an
  episode whose applicability constraints do not match the current
  task is returned as inapplicable, not silently applied.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RepairEpisode:
    repo_revision: str
    issue_fingerprint: str
    attempted_patch: str
    test_command: str
    verifier_result: str  # "pass" or "fail"
    evidence_ref: str
    applicability_constraints: str = ""
    outcome: str = ""  # "success" or "failure", derived from verifier_result
    created_at: float = field(default_factory=time.time)
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.outcome:
            self.outcome = "success" if self.verifier_result == "pass" else "failure"


class RepairMemory:
    """SQLite-backed repair-episode store. One file, no server."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS repair_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_revision TEXT NOT NULL,
                issue_fingerprint TEXT NOT NULL,
                attempted_patch TEXT NOT NULL,
                test_command TEXT NOT NULL,
                verifier_result TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                applicability_constraints TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def store(self, episode: RepairEpisode) -> RepairEpisode:
        cur = self._conn.execute(
            """INSERT INTO repair_episodes
               (repo_revision, issue_fingerprint, attempted_patch, test_command,
                verifier_result, evidence_ref, applicability_constraints,
                outcome, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode.repo_revision,
                episode.issue_fingerprint,
                episode.attempted_patch,
                episode.test_command,
                episode.verifier_result,
                episode.evidence_ref,
                episode.applicability_constraints,
                episode.outcome,
                episode.created_at,
            ),
        )
        self._conn.commit()
        episode.id = cur.lastrowid
        return episode

    def retrieve_relevant(
        self, issue_fingerprint: str, constraints: str = ""
    ) -> dict[str, list[RepairEpisode]]:
        """Return episodes for this fingerprint, split by applicability.

        An episode is 'applicable' when it has no constraints, or its
        constraints string appears in the current task's constraints.
        Anything else is reported under 'inapplicable' so the caller
        can see it was considered and rejected, not silently dropped.
        """
        rows = self._conn.execute(
            """SELECT id, repo_revision, issue_fingerprint, attempted_patch,
                      test_command, verifier_result, evidence_ref,
                      applicability_constraints, outcome, created_at
               FROM repair_episodes
               WHERE issue_fingerprint = ?
               ORDER BY created_at ASC""",
            (issue_fingerprint,),
        ).fetchall()
        applicable: list[RepairEpisode] = []
        inapplicable: list[RepairEpisode] = []
        for row in rows:
            ep = RepairEpisode(
                id=row[0],
                repo_revision=row[1],
                issue_fingerprint=row[2],
                attempted_patch=row[3],
                test_command=row[4],
                verifier_result=row[5],
                evidence_ref=row[6],
                applicability_constraints=row[7],
                outcome=row[8],
                created_at=row[9],
            )
            if not ep.applicability_constraints or (
                constraints and ep.applicability_constraints in constraints
            ):
                applicable.append(ep)
            else:
                inapplicable.append(ep)
        return {"applicable": applicable, "inapplicable": inapplicable}

    def failed_patches(self, issue_fingerprint: str) -> list[str]:
        """Patches already proven to fail for this fingerprint."""
        return [
            ep.attempted_patch
            for ep in self.retrieve_relevant(issue_fingerprint)["applicable"]
            if ep.outcome == "failure"
        ]

    def close(self) -> None:
        self._conn.close()

    def as_json(self, episodes: list[RepairEpisode]) -> list[dict]:
        return [asdict(ep) for ep in episodes]
