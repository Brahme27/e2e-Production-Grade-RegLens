# 04: Qdrant, the vector database

**Files:** `src/reglens/index/store.py`, `src/reglens/index/build.py`

## What
Qdrant stores each chunk as a **point**: an id, two named vectors (`dense`, `bm25`) and a
**payload** (the chunk's text and metadata). It answers "the 40 points most similar to
this question vector, among those matching this filter".

We build **four collections**, one per index variant, so the ablation can compare them:
`reglens_fixed`, `reglens_para`, `reglens_para_ctx`, `reglens_para_ctx_sum`.

## The "as of" filter
Dates are stored as day numbers (`valid_from_day`, `valid_to_day`). "As of 1 March 2024"
becomes the filter `valid_from_day ≤ D < valid_to_day`, applied *inside* the search: only
text in force on that day can come back. Repealed rules never compete with current ones.

## Aliases: re-indexing with zero downtime
The application never reads `reglens_para_ctx_sum` directly. It reads the alias **`reglens`**.
To re-index, we build a new collection and then swap the alias in one atomic operation.
Users never see a half-built index, and rolling back is another swap.

## Local vs server
| Where | Qdrant runs as |
|---|---|
| Laptop / tests | Embedded: a folder `artifacts/qdrant` (or `:memory:` in tests), no server |
| Docker Compose / AWS | The Qdrant server container (`REGLENS_QDRANT_URL=http://qdrant:6333`) |

The same code talks to both.

**Analogy:** a library catalogue where every card also has a "valid from / valid to" stamp,
and the catalogue can hide every card that wasn't valid on the date you ask about.

## How to run / what you should see
```bash
uv run poe index
```
`indexed variant=fixed chunks=1120`, `variant=para chunks=5203`, … and finally
`alias alias=reglens target=para_ctx_sum`.
