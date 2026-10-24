# ADR 0004: CPU-sized retrieval models (bge-small + BM25 + MiniLM reranker)

**Status:** accepted · **Date:** 2026-10-24

## Context
The plan named BGE-M3 (dense + sparse) and bge-reranker-v2-m3. Measured on the project
laptop (16 threads, no GPU, ONNX Runtime 1.31 via fastembed 0.9):

| Model | Job | Speed |
|---|---|---|
| BAAI/bge-small-en-v1.5 (33M) | dense embeddings | ~11 chunks/s (≈8 min per 5,203-chunk index) |
| Qdrant/bm25 | sparse vectors | ~1,000 chunks/s |
| Xenova/ms-marco-MiniLM-L-6-v2 (22M) | reranking 30-40 passages | ~1.5-2.1 s per question |
| BAAI/bge-reranker-v2-m3-int8 (568M) | reranking 40 passages | **~36 s per question** |

The latency target is p95 < 6 s end to end, including a hosted LLM call of 1-3 s.

## Decision
- Dense: bge-small; sparse: BM25 with Qdrant's IDF modifier; fusion: RRF inside Qdrant.
- Reranker: MiniLM-L6 over the top 30 candidates in serving and in ablation rows D-G.
- bge-reranker-v2-m3 is kept as a measured **side experiment** (ablation row `D-bge-m3`, on a
  fixed 30-question subset, compared against MiniLM on the same subset).

## Consequences
- Retrieval stays inside the latency budget on a laptop and on a small CPU container.
- All model names are settings (`REGLENS_DENSE_MODEL`, `REGLENS_RERANK_MODEL`, the
  `reranker` field of `RetrievalConfig`). With a GPU (or a hosted reranker) the switch is one
  config change, justified or rejected by the side-experiment numbers.
- English-only dense embeddings: Hindi text in bilingual SEBI circulars is skipped in v1.
