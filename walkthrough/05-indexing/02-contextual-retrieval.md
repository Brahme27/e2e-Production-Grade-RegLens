# 02: Contextual retrieval

**File:** `src/reglens/index/context.py`

## What
Before a chunk is turned into vectors, we prepend a short **context header**:

```
FCA handbook chapter: DISP 1 Treating complainants fairly (DISP 1). Section: DISP 1.10
Complaints reporting rules. Paragraph DISP 1.10.1-AG. Document context: The FCA's DISP 1
chapter sets out how firms must handle, resolve and report complaints from eligible
complainants, and applies to all FCA-authorised firms dealing with retail customers.
A firm with only a limited permission ... is required to submit information to the FCA ...
```

## Why
The paragraph alone never says "complaints" or "FCA". A question like *"What must firms
report to the FCA about complaints?"* would struggle to find it. The header adds the words
and meaning the paragraph only implies through its position in the document.

## How it works: two layers (and why not one LLM call per chunk)
Anthropic's "contextual retrieval" asks an LLM to write a custom context for **every**
chunk. For 5,203 chunks that is 5,203 calls, five days of our free-tier quota. So we
split the idea in two:

| Layer | Cost | What it adds | Ablation row |
|---|---|---|---|
| Structural header | Free | Regulator, document, number, heading path, paragraph ref | E1 |
| Document summary | 37 LLM calls (one per document) | What the document covers and who it applies to | E2 |

Each layer has to earn its place in the ablation table; if the summary doesn't improve
recall, it doesn't ship.

**Analogy:** a photocopied page from a binder. Write the binder's name and chapter at the
top of each copy before filing it, and it can still be found and understood later.

## How to run / what you should see
`uv run poe index` writes the summaries to `data/processed/doc_summaries.json`, for example:
```json
"pra-ss1-23": "The PRA's SS1/23 sets out model risk management principles for UK banks ..."
```
