# 04: The QA service

**File:** `src/reglens/qa.py`

## What
`QAService.ask_stream()` runs every step, in order, and yields events:

```
guard ─▶ semantic cache ─▶ retrieve (route, filters, rerank) ─▶ context rail
      ─▶ generate (streamed) ─▶ verify citations ─▶ cache + trace
```
It's used by the API (streaming and JSON) **and** by the answer evaluation in phase 08.

## Why one service for both?
If the evaluation called retrieval and generation directly, it would skip the guardrails, the
cache and the context rail, and measure a system nobody uses. Here, the numbers in the
README are produced by exactly the code path a user hits.

## Failure behaviour
| Failure | Behaviour |
|---|---|
| Guard says no | Polite refusal; nothing else runs (no tokens spent) |
| Retrieval finds nothing relevant | "Not found" message; no LLM call |
| LLM provider down or rate-limited | The retrieved passages are returned with an "answer service unavailable" note, so the user can still read the sources |
| Langfuse unreachable | Logged; the user notices nothing |

**Analogy:** an assembly line where quality control, packing and labelling are part of the
line itself, not optional extra stations.
