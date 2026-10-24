# 05: The retrieval pipeline

**File:** `src/reglens/retrieve/pipeline.py`

## What
One `Retriever` object runs every step, controlled by one `RetrievalConfig`:

```python
RetrievalConfig(
    collection="reglens",      # which index variant (fixed / para / para_ctx …)
    mode="hybrid",             # dense | sparse | hybrid
    reranker="minilm",         # none | minilm | bge-m3
    candidates=30, top_k=8,
    temporal_filter=True,      # "as of" filtering
    regulator_filter=True,     # one named regulator -> search only it
    route=True,                # router + comparison decomposition
    diversify_global=True,     # overview questions: ≤ 2 passages per document
)
```
```
question → read signals → route → [one search per regulator if comparing]
         → hybrid search (filtered) → rerank → (balance / diversify) → top-k chunks
```
It returns the chunks plus the route, the date used and timings per step.

## Why one configurable object?
Because the **ablation table is just a list of configs**. Row A (naive) is
`RetrievalConfig(collection="reglens_fixed", mode="dense", reranker="none", …off)`; row G is
the production setting. The exact code that is measured is the code that runs in production.
No separate "experiment" code path can drift away from reality.

## Two special cases
- **Comparisons** search each named regulator separately (half the candidates each), then
  guarantee at least two passages per regulator after reranking. Otherwise a strong match
  from one regulator can crowd out the other side entirely.
- **Overview questions** take at most two passages per document, so a "main themes"
  answer draws on several documents instead of ten paragraphs of one.

**Analogy:** a recipe with switchable steps. Turning each step on in turn shows exactly
which ingredient made the dish better.
