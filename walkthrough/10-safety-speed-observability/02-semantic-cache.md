# 02: The semantic cache

**File:** `src/reglens/cache/semantic.py`

## What
"How often must high-risk customers' KYC be refreshed?" and "What is the periodic
updation frequency for high-risk KYC?" are the same question. The semantic cache stores
each answer with the question's embedding; a new question whose embedding is ≥ 0.95
similar gets the stored answer in milliseconds, with no retrieval, reranking or LLM call.

## When a cached answer is NOT reused
The match must also have:
- the **same "as of" date** (an answer about 2024 is not an answer about today);
- the **same regulator filters**;
- the **same index + prompt version** (re-indexing or a new prompt invalidates everything).

Abstentions and refusals are never cached. Entries expire after 7 days.

## Where it lives
| Environment | Backend |
|---|---|
| Docker Compose / AWS | **Redis** (shared by every API replica, capped at 64 MB with LRU eviction) |
| Laptop / tests | A small in-process store |

**Analogy:** the FAQ sheet at a help desk: if someone asks a question already answered
today, in any wording, hand them the same sheet, unless they asked about a different date.
