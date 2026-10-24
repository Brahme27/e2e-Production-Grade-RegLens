# Phase 02: Building the corpus ("collecting the rulebooks")

A copilot is only as good as the documents it reads. In this phase we decide **which**
regulatory documents to index and download them **politely**: real documents from the
real regulators' websites, including **older versions** of the same rule so the system
can later answer "what did the rule say on 1 March 2024?".

| Chunk | What happens |
|---|---|
| [01-choosing-the-corpus.md](01-choosing-the-corpus.md) | 37 documents, 4 regulators, 6 shared themes, and where old versions come from |
| [02-polite-fetcher.md](02-polite-fetcher.md) | Downloading without hammering anyone's server: robots.txt, delays, retries, cache |
| [03-crawl-strategies.md](03-crawl-strategies.md) | Four websites, four shapes: how each regulator's site is crawled |

## Reproduce this phase
```bash
uv run poe crawl            # ~10 minutes the first time; seconds afterwards (cached)
```
