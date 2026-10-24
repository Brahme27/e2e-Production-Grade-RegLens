# Phase 10: Safety, speed and observability

Three production concerns that sit around the question-answering core:

| Chunk | What happens |
|---|---|
| [01-guardrails.md](01-guardrails.md) | Refusing prompt injections, jailbreaks and harmful requests; dropping poisoned passages |
| [02-semantic-cache.md](02-semantic-cache.md) | The same question, in other words, answered in milliseconds |
| [03-tracing.md](03-tracing.md) | Every request traced step by step, locally and in Langfuse; feedback as scores |
| [04-the-qa-service.md](04-the-qa-service.md) | One service that runs every step, used by the API *and* the evaluation |
