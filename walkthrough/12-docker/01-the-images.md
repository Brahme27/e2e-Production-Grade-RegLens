# 01: The images

**Files:** `Dockerfile`, `.dockerignore`, `frontend/Dockerfile`

## The API image
Built in two stages: stage 1 installs the **runtime** dependencies with uv from the lockfile;
stage 2 copies only what's needed to run:

| Baked in | Why |
|---|---|
| Parsed documents + validity + supersession edges | The document viewer and the indexer need them |
| `data/policies`, `configs`, `evals` | Impact workflow, settings, golden set |
| `artifacts/router.json`, evaluation reports | The trained router; the console's evaluation page |
| `artifacts/embeddings.sqlite` | The indexer loads Qdrant **without re-embedding** (minutes → seconds) |
| `cache/llm` | Every LLM answer the results were built from: the demo works even without a key |
| bge-small, BM25 and MiniLM ONNX models (~150 MB) | Query embedding and reranking with no download at start-up (`HF_HUB_OFFLINE=1`) |

Not baked in: the 570 MB bge-m3 reranker (rejected in the ablation), raw downloads,
dev tools, tests.

The same image runs three ways: `api` (uvicorn), `indexer` (one-shot load) and `worker`
(scheduled re-crawl).

## Hygiene
- Runs as a non-root numeric user (UID 10001); writable folders are created and owned by it
  before volumes mount on them.
- A container `HEALTHCHECK` hits `/health`.
- `OMP_NUM_THREADS=2` keeps ONNX Runtime from grabbing every core of a shared host.

The console image is Next.js's `standalone` output: a ~150 MB Node server with only the
files it needs.

**Analogy:** a food truck stocked before it leaves the depot: everything for the day's menu
is on board, so service starts the moment it parks.
