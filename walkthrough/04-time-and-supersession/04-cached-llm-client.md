# 04: The cached LLM client

**Files:** `src/reglens/llm/client.py`, `configs/litellm.yaml`, `cache/llm/`

## What
One class, `LLMClient`, through which every model call in the project goes:
1. It builds a **cache key**: a SHA-256 fingerprint of (model alias, messages, settings).
2. If `cache/llm/<key>.json` exists, it returns the stored answer instantly and costs no quota.
3. Otherwise it calls the model through **LiteLLM**, stores the answer, and appends a line
   to `artifacts/llm-usage.jsonl` (model, tokens, latency, purpose).

## Why
- **The free tier is small.** Groq gives 1,000 requests/day and 8,000 tokens/minute *per
  model*. Re-running an evaluation must not spend quota twice.
- **Tests and CI need no key.** The cache is committed to git, so a fresh clone replays every
  LLM answer the results were built from, deterministically.
- **Cost is visible.** The usage log is how the README can say exactly how many tokens a
  feature costs.

## Models and fallbacks (`configs/litellm.yaml`)
| Alias | Model (Oct 2026) | Used for |
|---|---|---|
| `reasoning-large` | `openai/gpt-oss-120b` | Answers, supersession, obligations, gap judgements |
| `fast-small` | `openai/gpt-oss-20b` | Summaries, routing fallback, judging |
| `fallback` | `qwen/qwen3.8-27b` | When the others are rate-limited or down |

Code only ever names the alias. Swapping providers is a config change. Each fallback
model has its own separate quota, so falling back also spreads the load. When Groq says
"try again in 7.5s", the client waits that long and retries, up to three times.

**A real-world note:** while building this project, Groq retired `llama-3.1-8b-instant`,
the fallback used in project 02. Aliases in config meant the fix was one line.

**Analogy:** a research assistant who keeps a notebook of every question they've already
asked an expert. Ask the same question again and they read you the notebook answer
instead of phoning the expert.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_llm.py -q --no-cov
```
Tests prove that a repeated request reaches the model once, that a cache-only client
replays or refuses, that a rate-limit message triggers a wait-and-retry, and that JSON
wrapped in prose or code fences is still parsed.
