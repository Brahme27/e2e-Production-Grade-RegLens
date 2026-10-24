# ADR 0003: LLM-proposed supersession edges go through human review

**Status:** accepted · **Date:** 2026-10-24

## Context
Generic RBI repeal clauses ("existing directions relating to X as applicable to Y stand
repealed") name no document. Rules find 3 of 8 in-corpus edges; an LLM finds 8 of 8 but
also proposed one wrong edge (Governance Directions 2025 → IT Governance Direction 2023).
A wrong SUPERSEDES edge silently hides still-valid text from "as of" questions, which is
the costliest failure in a compliance tool.

## Decision
- Rules run first; the LLM sees only clauses the rules cannot resolve, and may only pick
  from candidate ids we supply (older, same regulator).
- All edges carry `method` (rule / llm / title) and `evidence` (document + paragraph).
- A reviewer file, `configs/supersession_overrides.yaml`, rejects or adds edges, with a
  reason, before validity intervals are computed. The UI shows LLM edges as "proposed".
- Reported metrics are for the raw extractor (before review).

## Consequences
- Recall of the automated system stays high; precision of what ships is protected by a
  cheap human check on a handful of edges (9 LLM calls → 6 proposals for the whole corpus).
- We did not keep tuning the prompt on the single failure: with one example, that would be
  overfitting the evaluation set.
