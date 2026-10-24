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
| 06 | [Retrieval](06-retrieval/README.md) | Router, hybrid search with date and regulator filters, reranking, one configurable pipeline |
| 07 | [Answers](07-answers/README.md) | Cited answers, citation verification, abstention, streaming |
| 08 | [Evaluation](08-evaluation/README.md) | Golden set, the ablation table, an LLM judge and every number in the README |
| 09 | [Change impact](09-change-impact/README.md) | Obligations, policy gap judgement, human review, tickets (LangGraph) |
| 10 | [Safety, speed, observability](10-safety-speed-observability/README.md) | Guardrails, semantic cache, tracing with Langfuse |
| 11 | [API and console](11-api-and-console/README.md) | FastAPI endpoints and the Next.js compliance console |
| 12 | [Docker](12-docker/README.md) | The whole stack on one laptop, the way it runs in production |
| 13 | [Cloud and CI](13-cloud-and-ci/README.md) | Terraform for ECS Fargate (validated, not applied) and the CI quality gate |
