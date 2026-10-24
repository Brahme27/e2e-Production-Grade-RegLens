# Phase 08: Evaluation ("prove every claim with a number")

RegLens is built **eval-first**: every technique had to earn its place in a table. This
phase explains the test set, the metrics, the ablation and the judge, and what the
numbers taught us (including the techniques that did *not* ship).

| Chunk | What happens |
|---|---|
| [01-the-golden-set.md](01-the-golden-set.md) | 195 questions with known answers, and how they were made |
| [02-retrieval-metrics.md](02-retrieval-metrics.md) | Recall, nDCG, MRR, and "stale in top 5" (the compliance-specific one) |
| [03-the-ablation.md](03-the-ablation.md) | From naive RAG to production, one change at a time, with the results |
| [04-the-llm-judge.md](04-the-llm-judge.md) | Faithfulness and citation precision, judged by a different model family |
| [05-what-we-learned.md](05-what-we-learned.md) | Four things that didn't work, and what we did instead |

## Reproduce this phase
```bash
uv run poe ablation          # retrieval rows A-G (no LLM; ~20 min on a laptop CPU)
uv run poe eval-answers      # calibrate abstention + LLM-judged answers (free tier, cached)
uv run poe eval-impact       # obligation extraction + gap judgement
uv run poe results           # write docs/RESULTS.md
```
