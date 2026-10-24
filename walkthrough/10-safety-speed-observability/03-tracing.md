# 03: Tracing (local + Langfuse)

**File:** `src/reglens/obs/tracing.py`

## What
Every question produces a **trace**: one record with a **span** per step, each with its
input, output and duration:

```
ask "How often must high-risk KYC be updated?"            2,940 ms
 ├─ guard      verdict=allow, prompt-guard score 0.003       180 ms
 ├─ cache      hit=false                                       55 ms
 ├─ retrieve   route=lookup, as_of=2026-10-24, 8 hits        1,620 ms
 └─ generate   model=reasoning-large, abstained=false      1,085 ms
```

Traces go to two places:
1. **Always:** `artifacts/traces.jsonl`, one JSON line per request, searchable with any tool.
2. **When keys are set:** **Langfuse**, an open-source LLM observability platform, through its
   public ingestion API. There you get the trace tree, latency per step and user feedback.

## Feedback closes the loop
The 👍/👎 buttons call `POST /v1/feedback`: stored in Postgres, counted in Prometheus, and sent
to Langfuse as a **score** on that trace. A thumbs-down can be opened next to exactly what was
retrieved and generated.

## Design choices
- **No SDK, just HTTP**: the ingestion API is small and stable; one `httpx` client keeps the
  image lean and is easy to test with a fake server.
- **Never in the way**: sending runs in a background thread; if Langfuse is down, the request
  still succeeds and a warning is logged.
- **Self-hosting**: Langfuse v3 needs Postgres, ClickHouse, Redis and S3, too much for an
  8 GB laptop next to the app, so we point at Langfuse Cloud's free tier (just two keys).

**Analogy:** a flight data recorder for every question: when something goes wrong, you
replay exactly what happened, step by step.
