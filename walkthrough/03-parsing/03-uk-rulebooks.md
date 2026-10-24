# 03: The UK rulebooks: FCA Handbook and PRA Rulebook

**File:** `src/reglens/parse/handbooks.py`

## What
The UK regulators publish their rules as **structured** web pages, which makes them the
easiest and most valuable sources:

| | FCA Handbook | PRA Rulebook |
|---|---|---|
| Unit | Provision card: `SYSC 8.1.1` + type letter | Rule row: `2.1` |
| Type | **R** rule (binding), **G** guidance, **E** evidential, **D** direction | rule |
| Date | Date the current wording took effect (`03/01/2018`) | Same, per rule |
| Headings | Section (`SYSC 8.1 General outsourcing requirements`) › sub-heading | Chapter (`2 Outsourcing`) |

We cite FCA provisions the way the FCA does, with the type letter glued on:
**SYSC 8.1.1R** is a rule, **PRIN 2A.1.3G** is guidance. Compliance teams care about
the difference: a rule *must* be followed; guidance explains how.

## Why paragraph-level dates matter
A chapter "last updated 23/10/2025" doesn't mean every provision changed then. Most of
SYSC 8 dates from 2018; a few provisions changed in October 2025. With a date **per
provision**, the time-aware search (phase 04) can tell what applied on any day.

## A gotcha
`[deleted]` provisions still appear on the pages (with their number) so that numbering
stays stable. We skip them because there's nothing to retrieve.

**Analogy:** a well-kept rulebook where every rule has a sticker saying "in force since…".
We just read the stickers.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_parse.py -q --no-cov -k "fca or pra"
```
