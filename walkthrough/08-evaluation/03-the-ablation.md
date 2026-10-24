# 03: The ablation, from naive RAG to production one change at a time

**Files:** `src/reglens/evals/ablation.py` (the rows), `artifacts/reports/ablation.json` (results),
`evals/baseline.json` (the row CI must not fall below)

## What it is
An *ablation* adds one technique at a time and measures each step on the same 145 answerable
golden questions. Each row keeps everything from the row above it and adds one thing.

**Analogy:** tuning a recipe. You don't change the flour, the oven and the sugar at once and
then guess which one helped. You change one thing, taste, write it down, and move on.

## The results
| Row | What was added | Recall@10 | nDCG@10 | MRR | Stale in top 5 | p95 latency |
|---|---|---|---|---|---|---|
| A | Naive: fixed ~512-token chunks, dense search only | 0.810 | 0.652 | 0.619 | **64%** | 5 ms |
| B | + paragraph-shaped chunks | 0.844 | 0.730 | 0.702 | 60% | 19 ms |
| C | + hybrid search (BM25 keywords + dense, fused with RRF) | 0.866 | 0.754 | 0.736 | 66% | 89 ms |
| D | + cross-encoder reranker (MiniLM-L6) | 0.862 | 0.790 | 0.789 | 59% | 3.3 s |
| E1 | + structural context headers on every chunk | 0.889 | 0.824 | 0.841 | 46% | 3.5 s |
| E2 | + an LLM summary of the document in every chunk | 0.839 | 0.734 | 0.733 | 40% | 4.0 s |
| **F** | E1 + router, as-of date filter, regulator filter (**production**) | **0.914** | **0.853** | **0.869** | **0%** | 3.2 s |
| G | F + document-diverse retrieval for broad questions | 0.907 | 0.850 | 0.868 | 0% | 3.1 s |

Side rows: BM25 alone reaches recall@10 0.818. The bigger `bge-reranker-v2-m3` scored nDCG@10
0.804 against MiniLM's 0.779 on a 30-question subset, but took 15.8 s per question against
1.7 s (see [05](05-what-we-learned.md)).

## How to read it
- **Paragraph chunks (A → B)** gave the largest single jump in ranking quality (nDCG +0.08).
  Regulations are written in numbered paragraphs, so a chunk that follows them is a complete
  rule rather than half of two.
- **Hybrid search (B → C)** helps with exact terms like "Rule 4.3" or "SYSC 8.1.8": keywords
  find them, and meaning-based search finds the paraphrases.
- **The reranker (C → D)** barely changes *whether* the right paragraph is found, but moves it
  up the list (MRR 0.736 → 0.789). It also costs most of the latency.
- **Context headers (D → E1)** prefix each chunk with "RBI › Master Direction KYC › Chapter VI".
  Lookup nDCG rose from about 0.8 to 0.93.
- **E2 is the honest failure:** summaries hurt, so they were not shipped.
- **Row F is the compliance row.** Before it, 46–66% of questions had a repealed or
  not-yet-in-force paragraph in the top 5. With the as-of filter it's **0%**, and temporal
  questions' nDCG rose from 0.63 to 0.79.
- **G was not better than F** (within noise, slightly lower), so production stays on F.

## Where it is still weak
By category on row F, nDCG@10 is lookup 0.93, global 0.97, temporal 0.79 and **comparison
0.58**. "Compare the FCA and PRA on X" needs the right paragraph from *both* regulators.
Splitting the question into one sub-query per regulator helped, but it remains the weakest
category, and the README says so.

## The quality gate
`evals/baseline.json` stores row F's numbers. In CI, `python -m reglens.evals.gate --row F`
re-runs row F on a freshly crawled corpus and fails the build if recall, nDCG or MRR drops by
more than 0.03, or if any stale paragraph reaches the top 5. A regulator changing a page
layout and silently breaking the parser shows up as a red build, not as wrong answers.

## How to run
```bash
uv run poe ablation                                   # all rows (~20 min on a laptop CPU)
uv run python -m reglens.evals.ablation --rows F      # just production
uv run python -m reglens.evals.gate --row F           # compare with the baseline
```

## What you should see
A table like the one above in the log, `artifacts/reports/ablation.json` with per-question
detail, and `gate: pass` from the gate.
