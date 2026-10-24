# The RegLens Walkthrough

Read in order. Each folder is a phase; each file is one chunk, answering:
**What · Why · How it works · Tech & why · How to run · What you should see.**

| # | Phase | In one sentence |
|---|---|---|
| 00 | [The big picture](00-big-picture/README.md) | Why compliance teams need cited, time-aware answers, and what we're building |
| 01 | [Environment setup](01-environment-setup/README.md) | uv, settings, logging, quality tools, tests, pre-commit, CI (from the template) |
| 02 | [Building the corpus](02-corpus/README.md) | 37 real documents from four regulators, old versions included, downloaded politely |
| 03 | [Parsing](03-parsing/README.md) | Web pages and PDFs become numbered, dated, citable paragraphs |
| 04 | [Time and supersession](04-time-and-supersession/README.md) | Which document replaced which, and what applied on any given day |
| 05 | [Indexing](05-indexing/README.md) | Paragraph chunks with context headers, dense + BM25 vectors, Qdrant with "as of" filters |
