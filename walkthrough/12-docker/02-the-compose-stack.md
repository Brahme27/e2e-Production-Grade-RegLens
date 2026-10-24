# 02: The compose stack

**File:** `docker-compose.yml`

```
postgres ─┐
qdrant ───┼─▶ indexer (one-shot) ─▶ api ─▶ frontend
redis ────┘                         │
                                    └─ optional: worker (daily re-crawl), prometheus + grafana
```

| Service | Role | Memory cap |
|---|---|---|
| `postgres` | Document versions, supersession edges, obligations, reviews, feedback | 256 MB |
| `qdrant` | The vector search server | 512 MB |
| `redis` | The semantic answer cache | 96 MB |
| `indexer` | Loads the time model into Postgres, then the serving index into Qdrant (from cached embeddings), then exits | 1 GB |
| `api` | FastAPI; starts only after the indexer **completed successfully** | 1.5 GB |
| `frontend` | The console; starts when the API is healthy | 256 MB |

## Why a one-shot indexer instead of loading at API start-up?
- **One job, one place.** Re-running the indexer (after a new crawl) doesn't restart the API.
- **Safe start order.** `depends_on: condition: service_completed_successfully` means the
  API never serves an empty index.
- **Same as the cloud.** On AWS the indexer is an ECS task run on demand.

## Profiles
`--profile worker` adds the daily crawl/re-index loop; `--profile monitoring` adds Prometheus
(with alert rules: abstention rate, refusal spikes, p95 latency, negative feedback) and a
Grafana dashboard provisioned as code.

**Analogy:** a restaurant opening: deliveries arrive (databases), the kitchen is stocked
(indexer), and only then are the doors opened (API, console).
