# 04: Streaming

**Files:** `src/reglens/llm/client.py` (stream), `src/reglens/generate/answer.py`, `src/reglens/api/routes/ask.py`

## What
Answers appear word by word, using **Server-Sent Events** (SSE), a simple standard
for a server to push a stream of messages over one HTTP response:

```
event: meta     data: {"trace_id": "..."}
event: sources  data: {"route": "lookup", "as_of": "2026-10-24", "sources": [...]}
event: delta    data: {"text": "The Board must "}
event: delta    data: {"text": "approve a framework [1]."}
event: final    data: {"answer": {... citations, verification ...}}
event: done     data: {}
```
The sources arrive *before* the answer, so the user sees what's being read.

## Three details that matter
- **Holding back NOT_FOUND.** If the model's first characters could be the start of
  `NOT_FOUND`, we hold them until we know. Otherwise "NOT_F…" would flash on screen before
  turning into the polite message. A test checks that an answer starting with "NBFCs…"
  keeps its first letter.
- **Cache replay looks the same.** A cached answer is replayed in small pieces, so
  the UI code has one path.
- **Proxies must not buffer.** The response sets `Cache-Control: no-cache` and
  `X-Accel-Buffering: no`, and the Next.js proxy passes the stream through untouched, and the
  AWS load balancer allows a 120-second idle timeout.

**Analogy:** a live news ticker instead of a printed newspaper: you start reading the
first line while the rest is still being written.
