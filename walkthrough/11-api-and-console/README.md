# Phase 11: The API and the console

| Chunk | What happens |
|---|---|
| [01-the-api.md](01-the-api.md) | FastAPI endpoints, API key, rate limiting, metrics |
| [02-the-console.md](02-the-console.md) | The Next.js console: ask, documents, change feed, impact board, evaluation |
| [03-the-proxy.md](03-the-proxy.md) | Why the browser never sees the API key, and how streaming survives the proxy |

## Reproduce this phase
```bash
uv run poe api                       # http://127.0.0.1:8000/docs
pnpm --dir frontend dev              # http://localhost:3000 (API_URL / API_KEY in env)
```
