# Repo Rescue — standalone hackathon package (Oct 30 milestone)

Built standalone in the workspace on 2026-10-30 so the Oct 30 milestone
(API integration + durable repair memory) is not blocked on the open
SIS-access decision. No SIS files were touched; this package is
designed to drop into `wildhash/SIS` as `hackathon/` once SIS access
is available, and nothing here merges or deploys code.

## What it is

An evidence-driven repair agent: retrieve prior repair lessons,
propose a minimal patch, verify it with an independent test run,
and store the outcome (success or failure) with provenance.

- `hackathon/repair_memory.py` — SQLite repair episodes: repo
  revision, issue fingerprint, attempted patch, test command,
  verifier result, evidence reference, applicability constraints.
- `hackathon/meta_client.py` — Muse Spark 1.3 adapter (key from
  `MODEL_API_KEY`, endpoint from `META_MODEL_BASE_URL`; refuses to
  run without a key) plus `StubProposer` for offline tests.
- `hackathon/repair_agent.py` — bounded retrieve → propose →
  verify → store loop. No auto-merge, no auto-deploy.
- `hackathon/demo.py` — two-session demo + memory-off control.

## Verified 2026-10-30 (this machine, stdlib only, no live API key)

```
python3 -m unittest discover -s tests -v   # 5 tests, OK
python3 -m hackathon.demo
```

Demo result (stub proposer, not a live-model result):
- Session 1 (teach): succeeds in 2 attempts — bad patch fails
  verification and is stored, good patch passes and is stored.
- Session 2 (fresh agent, same memory file, no shared history):
  succeeds in 1 attempt, using the stored lessons.
- Memory-off control: succeeds in 2 attempts, re-trying the
  failure session 1 had already stored.

## Still open — Will's decisions

1. SIS access: make SIS readable / share a copy (build inside SIS),
   or keep this standalone package and drop it into SIS later.
2. Live Muse key: set `MODEL_API_KEY` (+ `META_MODEL_BASE_URL`)
   to replace the stub proposer with a real Muse Spark run; the
   demo numbers above do not prove live-model performance.
3. Submission deadline: Nov 4, 2026, 6:00pm PT. Remaining schedule
   from the brief: Oct 31 first verified repair cycle, Nov 1
   fresh-session retrieval, Nov 2 memory-on/off evaluation,
   Nov 3 demo/README, Nov 4 submission.
