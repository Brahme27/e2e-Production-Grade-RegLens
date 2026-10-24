# Phase 14: Results and next steps ("what did we build, how good is it, what's next")

This is the end of the build story. It sums up what RegLens can do, how well it does it, where
it's weak, and what a team would do next with more time, a GPU or a budget.

## What we built, in one paragraph
A compliance analyst asks "What did the RBI require for periodic KYC updates as of March
2024?". RegLens searches 4,835 paragraphs from 37 real RBI, SEBI, FCA and PRA documents. It
keeps only text that was in force on that date, ranks it, and answers in a few sentences, each
citing the exact paragraph. If the answer isn't in the sources, it says so. When a regulator
publishes a new version, RegLens works out what changed, turns the changes into obligations,
checks a bank's own policies for each one, and pauses for a human to approve the gaps before
creating tickets.

## How good is it?
Full tables: [docs/RESULTS.md](../../docs/RESULTS.md). The headline numbers:

| Question | Answer |
|---|---|
| Does it find the right paragraph? | In the top 10 for 91% of questions (naive RAG: 81%) |
| Does it show out-of-date rules? | Never in the top 5 (naive RAG: 64% of questions) |
| Are the answers true to the sources? | 87% of sentences supported, judged by a different model (naive: 72%) |
| Are the citations right? | 84% of sentences cite a source that supports them (naive: 68%) |
| Does it know when it doesn't know? | Declined all 12 unanswerable questions |
| Can it be tricked? | Refused 9 of 10 adversarial prompts |
| Does it spot policy gaps? | Told "covered" from "gap" correctly for 93% of 41 planted cases |
| How fast? | 1.4 s typical, 2.2 s slow (p95), on a laptop CPU |

## Where it's weak (and we say so)
- **Comparison questions** ("FCA vs PRA on outsourcing") are the hardest: one side is often
  missing from the top results.
- **It is cautious:** 18% of answerable questions were declined.
- **Obligation extraction** finds 63% of the obligations a human listed (everything it finds is
  right, but it misses some).
- The test questions and the judge are LLM-assisted, not checked by compliance professionals.

All of this is in [docs/LIMITATIONS.md](../../docs/LIMITATIONS.md).

## What we'd do next
| With… | Next step | Expected gain |
|---|---|---|
| A GPU | Swap MiniLM for bge-reranker-v2-m3 (+0.025 nDCG measured, too slow on CPU) | Better ranking, especially comparisons |
| A week | Per-regulator retrieval budgets for comparison questions | The weakest category |
| A compliance expert | Review 50 golden items and 100 judge labels | Trustworthy, calibrated numbers |
| A deployment | Postgres checkpointer for LangGraph, SSO in front of the console | Survives restarts; knows who approved what |
| A paid LLM tier | Run impact analysis asynchronously with progress updates | Minutes → seconds of waiting |

## The habits that made it work
1. **Measure before believing.** Two techniques from the original plan made things worse and
   were not shipped. Without the ablation, we'd have shipped them.
2. **Read failures, not just averages.** A perfect judge score turned out to rest on only 7
   answers.
3. **Run the real thing.** Docker found five bugs that 161 green unit tests missed.
4. **Keep humans in the loop where it matters.** Repeals proposed by the LLM, and every gap
   judgement, go to a person.

## Reproduce everything
```bash
uv sync && uv run poe pipeline       # data → indexes (polite crawling with per-host delays)
uv run poe ablation && uv run poe eval-answers && uv run poe eval-impact && uv run poe results
docker compose up -d --build && uv run python -m reglens.smoke --api http://localhost:8000 --web http://localhost:3000
```
