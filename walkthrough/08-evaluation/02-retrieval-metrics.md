# 02: Retrieval metrics

**File:** `src/reglens/evals/retrieval_metrics.py`

| Metric | Plain-English meaning |
|---|---|
| **Recall@10** | Of the paragraphs a question needs, what share are in the top 10? (Comparisons need both sides.) |
| **nDCG@10** | Like recall, but rewards finding them *near the top*. Rank 1 is worth more than rank 9 |
| **MRR** | 1 ÷ the rank of the first correct paragraph (1.0 = always first) |
| **Stale in top 5** | Share of questions where a paragraph that was **not in force** on the question's date appears in the top 5 |
| **p95 latency** | 95% of questions are retrieved faster than this |

## Why "stale in top 5" matters most here
A general search engine can show last year's page next to this year's. A compliance tool cannot:
if a repealed rule sits in the top 5, the answer model may quote it as current, and someone may
act on it. This metric makes that failure visible. Without date filters it's **40–64%** of
questions; with them, **0%**.

## Why no LLM is needed
Retrieval metrics only compare paragraph ids, so every row of the ablation runs on all 145
answerable questions for free, as often as we like. LLM-judged metrics (next chunks) are
reserved for the generation step.
