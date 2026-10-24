# Phase 06: Retrieval ("finding the right paragraphs")

Given a question, find the handful of paragraphs that answer it, from the right
regulator, valid on the right date, in under a few seconds on a laptop CPU.

| Chunk | What happens |
|---|---|
| [01-reading-the-question.md](01-reading-the-question.md) | Dates, regulators and firm types pulled out of the question with rules |
| [02-the-router.md](02-the-router.md) | Lookup, "as of", comparison or overview? A tiny trained classifier decides |
| [03-hybrid-search-and-filters.md](03-hybrid-search-and-filters.md) | Meaning + exact words, fused; the "as of" and regulator filters |
| [04-reranking.md](04-reranking.md) | A second, sharper reader re-orders the top 30, and why we chose the small one |
| [05-the-pipeline.md](05-the-pipeline.md) | One configurable object, so every ablation row is just a setting |

## Reproduce this phase
```bash
uv run poe router      # train the router (5 LLM calls the first time, cached)
uv run poe ablation    # every retrieval configuration scored on the golden set
```
