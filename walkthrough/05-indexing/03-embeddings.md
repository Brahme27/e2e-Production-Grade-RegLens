# 03: Embeddings: meaning and exact words

**File:** `src/reglens/index/embed.py`

## What
Each chunk becomes two vectors:

| Vector | Model | Good at | Bad at |
|---|---|---|---|
| **Dense** (384 numbers) | `BAAI/bge-small-en-v1.5` | Meaning: "cloud vendor" ≈ "cloud service provider" | Exact identifiers: "SS1/23", "PRIN 2A.4.1R" |
| **Sparse** (word weights) | BM25 (`Qdrant/bm25`) | Exact words and identifiers | Synonyms |

Hybrid search (phase 06) uses both, which is why we compute both.

## Why these models (and not BGE-M3, as planned)?
BGE-M3 produces dense and sparse vectors from one multilingual model, but it is a
568-million-parameter model: hours to embed on this laptop's CPU, with ~3 GB of RAM in use.
`bge-small` (33M parameters) plus classic BM25 run in minutes, in ONNX form via
`fastembed`, with no PyTorch. Swapping models is one setting
(`REGLENS_DENSE_MODEL`), and the ablation would show whether a bigger model pays off.

## A measured surprise
The first timing test said **3 chunks per second**: hours per index. The cause was not
the model. A 570 MB reranker was downloading in parallel, and Windows was virus-scanning the
new files. Re-measured on a quiet machine: ~11 chunks/second for bge-small, ~1,000/second
for BM25. **Lesson: benchmark on a quiet machine before redesigning anything.**

## The embedding cache
Every vector is stored in `artifacts/embeddings.sqlite`, keyed by a hash of (model, text).
Re-indexing after editing three documents embeds only their changed paragraphs.

**Analogy:** the dense vector is a librarian who knows what a book is *about*; the sparse
vector is the index at the back that lists every exact term. You want both at the desk.

## How to run / what you should see
```bash
uv run poe index
```
Log lines like `embedded model=BAAI/bge-small-en-v1.5 new=5203 cached=0`, then on the next
run `new=0 cached=5203`.
