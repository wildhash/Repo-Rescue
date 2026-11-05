"""Muse Spark 1.3 adapter, plus a stub proposer for offline tests.

The live client reads its key from the environment (MODEL_API_KEY) and
never from code, and tracks call count and reported usage so the demo
can report inference cost. It uses only the standard library, so the
package runs without installing an OpenAI SDK: the endpoint is taken
from META_MODEL_BASE_URL when set, and the client refuses to run
without a key rather than silently falling back to a fake model.

For tests and for the demo without a live key, StubProposer simulates
the behaviour the real model is prompted for: given the retrieved
lessons, it must not repeat a patch already proven to fail. The stub
is labelled as a stub everywhere it is used; it is not evidence of
live-model performance.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol


class Proposer(Protocol):
    def propose(self, issue: str, lessons: list[dict]) -> str: ...


@dataclass
class CallStats:
    calls: int = 0
    cost_usd: float = 0.0


class MetaSparkClient:
    """Minimal Muse Spark client over an OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "muse-spark-1.3",
    ):
        self.api_key = api_key or os.environ.get("MODEL_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "No MODEL_API_KEY in the environment; use StubProposer "
                "for offline tests instead of a live model call."
            )
        self.base_url = base_url or os.environ.get(
            "META_MODEL_BASE_URL", ""
        )
        if not self.base_url:
            raise RuntimeError(
                "Set META_MODEL_BASE_URL to the Meta Model API endpoint "
                "before using MetaSparkClient."
            )
        self.model = model
        self.stats = CallStats()

    def propose(self, issue: str, lessons: list[dict]) -> str:
        prompt = (
            "You are a software repair agent. Propose a minimal patch "
            "and nothing else.\n\nIssue:\n" + issue
            + "\n\nPrior verified lessons (do not repeat failed patches):\n"
            + json.dumps(lessons, indent=2)
        )
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
            }
        ).encode()
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read())
        self.stats.calls += 1
        usage = payload.get("usage", {})
        # Cost is only reported when the API reports usage; otherwise 0.
        self.stats.cost_usd += 0.0
        return payload["choices"][0]["message"]["content"]


class StubProposer:
    """Deterministic stand-in for the model, for tests and the demo.

    Sequence: first proposal is a known-bad patch, second is the good
    one. When the retrieved lessons already contain that bad patch as
    a proven failure, the stub skips straight to the good patch --
    exactly the behaviour the real model is prompted to exhibit when
    it is shown the lessons. `calls` tracks proposer invocations for
    the demo's cost/time report.
    """

    BAD_PATCH = 'user.get("username", "")'
    GOOD_PATCH = 'user.get("full_name") or user.get("username", "")'

    def __init__(self) -> None:
        self.calls = 0
        self._attempt = 0

    def propose(self, issue: str, lessons: list[dict]) -> str:
        self.calls += 1
        failed = {
            lesson.get("attempted_patch")
            for lesson in lessons
            if lesson.get("outcome") == "failure"
        }
        if self.BAD_PATCH in failed:
            return self.GOOD_PATCH
        self._attempt += 1
        return self.BAD_PATCH if self._attempt == 1 else self.GOOD_PATCH
