# ADR 0001: A curated, versioned corpus instead of a full crawl

**Status:** accepted · **Date:** 2026-10-24

## Context
The plan targeted 1,500–3,000 documents. The project runs on a CPU-only laptop (7.7 GB RAM)
and a free LLM tier (1,000 requests/day per model). Every document must be embedded and
evaluated; the golden set must have answers on both sides of cross-regulator questions.

## Decision
Index **37 documents / 48 versions** chosen on six themes shared by RBI, SEBI, FCA and
PRA (KYC, outsourcing, cyber/IT and operational resilience, complaints, governance and
compliance, model risk and AI), deliberately including:
- documents **repealed** by newer ones (RBI KYC 2016 → 2025; IT outsourcing 2023 → 2025;
  Internal Ombudsman 2023 → 2026; SEBI SCORES master circular 2022 → 2023 circular);
- **dated editions** (PRA SS2/21: 2021, 2024, 2026; SS1/21: 2021, 2022; RBI KYC 2025:
  Nov 2025 and Oct 2026);
- **point-in-time** PRA Rulebook snapshots, including a future (2027) version.

## Consequences
- Indexing takes minutes, not hours; evaluation is affordable on the free tier.
- Temporal retrieval and supersession are testable against real version history.
- Coverage is narrow: questions outside the six themes should be **abstained on**, which
  the golden set tests explicitly.
- Scaling up is a matter of adding entries to `configs/sources.yaml`; nothing else changes.
