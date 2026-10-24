# 05: The parse run

**File:** `src/reglens/parse/run.py`

## What
`uv run poe parse` reads the crawl manifest and sends each version to the right parser
(RBI HTML, FCA sections, PRA part, or PDF). It then fills in the document-level dates and
writes one JSON file per version.

### Which date is "effective from"?
| Version | Effective from |
|---|---|
| An archived edition with a known start (e.g. the 2021 edition of SS2/21) | The date in the source list (31 Mar 2022) |
| RBI page "Updated as on 1 Oct 2026" | 1 Oct 2026 |
| PRA Rulebook as at 30 Jun 2025 | The latest rule change **on or before** that day (31 Dec 2020) |
| FCA chapter | The latest provision date |

## What the corpus looks like
| | |
|---|---|
| Document versions | 48 (37 documents) |
| Paragraphs | 4,838: RBI 1,884 · SEBI 1,473 · PRA 985 · FCA 496 |
| Size | ~2.7 million characters ≈ 680k tokens |
| Paragraph length | Median 324 characters; 95% under 1,750 |

The few very long paragraphs (the KYC definitions paragraph is 22,000 characters) are
split into smaller pieces at indexing time (phase 05). Each piece keeps its paragraph ref.

## How to run / what you should see
```bash
uv run poe parse
```
One `parsed doc=... paragraphs=... effective=...` line per version, then
`parse_done documents=48 paragraphs=4838`.
