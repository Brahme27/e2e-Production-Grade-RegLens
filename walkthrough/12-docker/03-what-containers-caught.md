# 03: What containers caught (that 161 unit tests didn't)

**What:** the first time the full stack ran in Docker, with real Postgres, a Qdrant server,
Redis and the console, five problems appeared. Every unit test was green at the time.

**Why it matters:** unit tests use stand-ins: SQLite instead of Postgres, Qdrant in memory,
fake LLMs. Each stand-in is a little more forgiving than the real thing. Running the real
images is what finds the gaps between them.

**Analogy:** a dress rehearsal. Every actor knows their lines (unit tests), but only a run on
the real stage, with the real lights and props, shows that a door opens the wrong way.

## 1. A foreign-key bug that SQLite let through
Saving an impact run failed in Docker with `ForeignKeyViolation`: a gap judgement was inserted
before the obligation it points to. SQLAlchemy only orders inserts between tables when the
models are linked by a `relationship()`, and these weren't. Postgres enforces foreign keys;
**SQLite ignores them unless you ask**, so every test passed.
**Fix:** `_save` flushes obligations before adding judgements, and `make_engine` now turns on
`PRAGMA foreign_keys=ON` for SQLite. With that one line, the existing API test failed the same
way Postgres did, and then passed after the fix.

## 2. `docker compose build api` built nothing
Only the one-shot `indexer` service declared `build: .`; `api` just reused the image name.
So `docker compose build api` printed "No services to build", and the API kept running **old
code** after a fix. The smoke test kept failing for a reason that was already fixed.
**Fix:** `api` declares `build: .` too (the second build is fully cached).
**Lesson:** after rebuilding, prove the container has the new code (we checked for the new
function inside the running container) before debugging further.

## 3. The model cited a paragraph number instead of a source number
In the live stack, an answer cited `【12†para12(1)(i)】`. The model put the **paragraph number**
(12) where the **source number** belongs. Source 6 was paragraph 12, and there were only 8
sources, so `[12]` was removed as invalid and the answer was left with no citations. The
evaluation never saw this pattern; the smoke test caught it on the first real question.
**Fix:** when a marker's number is out of range but it carries a `†para …` label, RegLens maps
the label to the one source with that paragraph ref (never guessing when two sources share it).

## 4. Qdrant client and server versions drifted apart
The indexer logged "Qdrant client version 1.20.0 is incompatible with server version 1.16.2".
The Python client had moved on through `uv.lock`; the server image tag had not.
**Fix:** server image `v1.20.0` in compose and Terraform, with a comment to keep the two in
step. Qdrant only guarantees upgrades one minor version at a time, so the local volume was
recreated (`docker compose down -v`) and rebuilt by the indexer in about 20 seconds, rather
than migrated across four versions.

## 5. A real impact run is slower than the demo implied
The console said "about a minute". A cold run of the PRA outsourcing rewrite makes one LLM
call per changed obligation, at about 15 s each under the free tier's tokens-per-minute limit,
which is several minutes in total. The Playwright test timed out at 4 minutes.
**Fix:** honest UI copy ("a few minutes on the free tier; repeat runs are instant"), a test
budget sized for a cold run, and the replies copied out of the container into `cache/llm/` so
the next build replays them.

## How to run
```bash
docker compose up -d --build
uv run python -m reglens.smoke --api http://localhost:8000 --web http://localhost:3000
uv run poe e2e                       # Playwright against the running stack
```

## What you should see
`8/8 PASS` from the smoke test and `8 passed` from Playwright. If an API fix doesn't seem to
take effect, check that the running container has the new code first.
