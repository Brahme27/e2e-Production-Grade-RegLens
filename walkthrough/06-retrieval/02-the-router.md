# 02: The router

**Files:** `src/reglens/retrieve/router.py`, `src/reglens/retrieve/train_router.py`

## What
Questions come in different shapes and need different handling:

| Route | Example | What retrieval does differently |
|---|---|---|
| `lookup` | "How often must high-risk customers' KYC be updated?" | Standard search, today's rules |
| `temporal` | "What did the PRA expect on outsourcing as of June 2025?" | Search the rules in force on that date |
| `comparison` | "How do RBI and FCA outsourcing rules differ?" | One search **per regulator**, so both sides appear |
| `global` | "What are the main themes of the Consumer Duty?" | At most two passages per document, for breadth |

## How it works
A **logistic regression**, the simplest classifier there is, over two kinds of input: the
question's bge-small embedding (384 numbers) and five yes/no rule signals (has a date,
names two regulators, …). Two rules that are never wrong override the model: two regulators
plus a comparison word means `comparison`; an explicit date means `temporal`.

Training happens offline (`uv run poe router`):
1. The LLM writes 40 varied example questions per route (5 calls, cached), separate from the
   golden test set, so we don't grade the router on its own homework.
2. scikit-learn fits the model; 5-fold cross-validation checks it.
3. The weights are exported to `artifacts/router.json`. At serving time it's one matrix
   multiplication in numpy: ~1 ms, no scikit-learn in the API image, no LLM call.

## Results
| | Accuracy |
|---|---|
| Cross-validation (training questions) | 0.976 |
| Golden set (175 questions it never saw) | **0.903** (target ≥ 0.90) |

The main confusion: 11 lookups read as "global", which only changes how many documents
contribute passages (a mild cost).

## The class we removed
Version 1 also learned an `out_of_scope` class ("write me a poem", "stock tips"). It failed
badly: it rated real compliance questions as *more* off-topic than chit-chat (0.33–0.63
vs 0.13 for "What's the weather in Mumbai?"), which would have refused 27 legitimate
questions. Off-topic requests are now handled by the guardrails (phase 11) and by
abstention when nothing in the corpus matches. **A model that is wrong in the costly
direction is worse than no model.**

**Analogy:** the triage nurse who decides which specialist sees you. It doesn't treat
anyone; it just sends you down the right corridor.
