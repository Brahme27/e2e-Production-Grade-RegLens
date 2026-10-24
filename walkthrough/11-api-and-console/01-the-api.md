# 01: The API

**Files:** `src/reglens/api/app.py`, `src/reglens/api/deps.py`, `src/reglens/api/routes/*.py`

## Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /v1/ask` | Question (+ optional `as_of`, `regulators`) → streamed answer (SSE), or JSON with `?stream=false` |
| `POST /v1/feedback` | 👍 / 👎 on an answer (by trace id) |
| `GET /v1/documents`, `/v1/documents/{id}` | Versions, validity, status, supersession links |
| `GET /v1/documents/{id}/versions/{v}` | Full text, paragraph by paragraph (the citation viewer) |
| `GET /v1/documents/{id}/diff?from=&to=` | Paragraph-level changes between versions |
| `GET /v1/graph/supersession` | Who replaced or amended whom |
| `GET /v1/changes?since=` | The change feed: in force, upcoming, superseded |
| `POST /v1/impact`, `PATCH /v1/gaps/{id}`, `POST /v1/impact/{run}/approve` | Change-impact workflow with review |
| `GET /v1/obligations`, `/v1/impact/{run}/tickets.csv` | Obligation register and tickets |
| `GET /v1/meta`, `/v1/entities`, `/v1/reports/{name}` | Corpus overview, firms, evaluation reports |
| `GET /health`, `/ready`, `/metrics` | Liveness, readiness, Prometheus metrics |

## Production basics
- **API key** on every `/v1` route, compared in constant time (`secrets.compare_digest`).
- **Rate limit**: a token bucket per API key (or IP) on `/v1/ask`, 30 per minute by default,
  so one client can't burn the whole LLM quota.
- **Validation**: pydantic models reject bad input before any work (a 1-character
  question, an unknown regulator "ECB", an impact override without a status).
- **Allow-lists, not paths**: report names and ticket run ids are checked against an
  allow-list or a strict pattern; `../../etc/passwd` gets a 404.
- **Metrics**: requests by endpoint, answers by outcome (answered / abstained / refused /
  cached), answer latency histogram, feedback counts.
- **Lazy services**: the expensive objects (ONNX models, Qdrant client, LangGraph workflow)
  are built on first use and shared, so `/health` answers immediately at start-up.

**Analogy:** a bank counter with a queue system: show your card (API key), take a ticket (rate
limit), fill in the right form (validation), and every transaction is logged (metrics).
