# 01: The supersession graph

**File:** `src/reglens/temporal/supersession.py`

## What
A small graph where an arrow means "this newer document replaced (or amended) that one":

```
rbi-cb-internal-ombudsman-2026 ──SUPERSEDES──▶ rbi-md-internal-ombudsman-2023
sebi-scores-2023               ──SUPERSEDES──▶ sebi-scores-master-2022   (from 4 Dec 2023)
sebi-cscrf-clarifications-2025 ──AMENDS──────▶ sebi-cscrf-2024
sebi-cscrf-2024                ──SUPERSEDES──▶ 43 older cyber circulars and letters
```
56 edges in total, each with **evidence** (the document and paragraph where the repeal
clause sits).

## How it works: two extractors
**1. Rules (precise, cheap).** Find sentences with a repeal verb (*repeal, rescind,
supersede, stand withdrawn, deprecated*) that **name** another document, either by its
number (`SEBI/HO/OIAE/IGRD/P/CIR/2022/0150`) or by its full title. Details that mattered:
- "This Circular rescinds the **following** circulars: i. … ii. …": list items inherit
  the verb from the lead-in sentence.
- CSCRF has a **table** of 43 replaced documents under the heading "List of SEBI
  cybersecurity circulars to get supersede[d] with CSCRF". Table rows inherit the verb too.
- "Modification in Cyber Security framework" is the *title* of a listed circular, not a
  verb, so only verb forms ("is hereby amended") count as amendments.
- PDF line wrapping breaks numbers ("CIR/2 022/68"). We repair them before matching.
- "with effect from December 04, 2023" becomes the edge's effective date.

**2. LLM (for vague clauses only).** RBI's 2025–26 directions repeal things generically:
*"the existing Directions, instructions, and guidelines relating to Know Your Customer as
applicable to Commercial Banks stand repealed."* No title, no number. For these clauses
only (9 of them), the model receives the clause and a list of **older documents from the
same regulator**, and answers in JSON which ones the clause covers. Any id the model
invents is thrown away.

**Analogy:** a librarian's catalogue card that says "replaced by…". Explicit
cross-references are copied straight across; for vague ones ("all earlier guidance on
KYC"), a knowledgeable colleague is asked which books that means.

## Why both and not just the LLM?
Rules cost nothing and never hallucinate. The LLM is spent only where rules provably
can't work: 9 calls on the free tier for the whole corpus.

## How to run / what you should see
```bash
uv run poe temporal
```
`supersession_eval rules_f1=0.944 rules_plus_llm_f1=0.982` and `temporal_done edges=56`.
