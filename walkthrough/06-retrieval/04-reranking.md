# 04: Reranking

**File:** `src/reglens/retrieve/rerank.py`

## What
The first search compares vectors computed *separately* for the question and each
paragraph: fast, but shallow. A **cross-encoder** reads the question and a paragraph
*together*, word against word, and outputs a relevance score. That's more accurate and much
slower, so we run it only on the top 30 candidates and keep the best 8–10.

## The decision we measured
| Reranker | Size | Time per question (30–40 passages, laptop CPU) |
|---|---|---|
| `ms-marco-MiniLM-L-6-v2` | 22M parameters | ~1.6 s (p95 3.3 s) |
| `bge-reranker-v2-m3` (int8), the plan's choice | 568M parameters | **~36 s** |

The plan's model is excellent but would blow the 6-second answer budget six times over on
this hardware. We serve MiniLM and keep bge-m3 as a side experiment on a fixed 30-question
subset, so the README can state exactly what quality a GPU would buy (ADR 0004).

## What reranking bought
Row C → D: MRR 0.736 → 0.789 and nDCG@10 0.754 → 0.790. Recall@10 hardly moves
(0.866 → 0.862), as expected: a reranker *reorders* the 30 candidates, it can't find
paragraphs the first search missed. What improves is that the right paragraph moves near the
top, where the answer generator pays most attention.

**Analogy:** the first search is skimming the shelf by spine labels; the reranker opens each
of the 30 shortlisted books at the right page and reads it against your question.
