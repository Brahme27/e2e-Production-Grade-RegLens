# Phase 04: Time ("what applied on that day?")

Regulation changes in two ways: a **new version** of the same document (an edited
rulebook, a new edition), or a **new document that repeals an old one**. A compliance
copilot that ignores time will happily quote a rule that was repealed last year. This
phase teaches RegLens *when* each piece of text applied.

| Chunk | What happens |
|---|---|
| [01-the-supersession-graph.md](01-the-supersession-graph.md) | Finding "X repeals Y": rules first, an LLM for the vague cases |
| [02-measuring-the-extractor.md](02-measuring-the-extractor.md) | 57 hand-labelled edges, precision/recall, and the one mistake the LLM made |
| [03-validity-intervals.md](03-validity-intervals.md) | valid_from / valid_to for every version and paragraph |
| [04-cached-llm-client.md](04-cached-llm-client.md) | Every LLM call cached and logged: free-tier friendly, CI deterministic |
| [05-the-database.md](05-the-database.md) | Versions and edges in SQL (SQLite locally, Postgres in Docker/AWS) |

## Reproduce this phase
```bash
uv run poe temporal          # ~1 min; 9 LLM calls the first time, 0 afterwards (cached)
```
