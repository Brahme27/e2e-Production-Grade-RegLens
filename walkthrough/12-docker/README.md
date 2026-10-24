# Phase 12: Docker ("the whole system on one laptop, the way it runs in production")

| Chunk | What happens |
|---|---|
| [01-the-images.md](01-the-images.md) | What is baked into the API image, and why |
| [02-the-compose-stack.md](02-the-compose-stack.md) | Postgres, Qdrant, Redis, a one-shot indexer, the API and the console |
| [03-what-containers-caught.md](03-what-containers-caught.md) | Problems that only appeared when running the real images |

## Reproduce this phase
```bash
uv run poe pipeline          # corpus, parse, time model, indexes, router (once)
docker compose up -d --build
uv run python -m reglens.smoke --api http://localhost:8000 --web http://localhost:3000
```
