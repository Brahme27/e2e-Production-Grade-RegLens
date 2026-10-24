# Phase 05: Indexing ("making the rulebooks searchable")

Search needs an **index**, like the index at the back of a book but for meaning as
well as words. This phase cuts the parsed documents into searchable pieces, gives each
piece the context a reader would have, turns them into numbers (vectors) and loads
them into a vector database.

| Chunk | What happens |
|---|---|
| [01-chunking.md](01-chunking.md) | Fixed 512-token windows (the naive baseline) vs one chunk per paragraph |
| [02-contextual-retrieval.md](02-contextual-retrieval.md) | Headers and LLM document summaries, so a lonely paragraph still makes sense |
| [03-embeddings.md](03-embeddings.md) | Dense (meaning) + sparse (exact words) vectors on a CPU, with a cache |
| [04-qdrant.md](04-qdrant.md) | The vector database: named vectors, "as of" filters, aliases for zero downtime |

## Reproduce this phase
```bash
uv run poe index      # first run ~25 min on a laptop CPU (embedding); re-runs use the cache
```
