# 03: Validity intervals

**File:** `src/reglens/temporal/validity.py`

## What
Every document version gets three facts:

| Field | Meaning | Example (RBI IT Governance Direction 2023) |
|---|---|---|
| `valid_from` | First day the text applied | 2024-04-01 (the direction says it "shall come into effect from April 1, 2024") |
| `valid_to` | First day it **no longer** applied (empty = still in force) | 2026-07-31 (repealed by the 2026 cybersecurity directions) |
| `status` | As of today: current / superseded / future | superseded |

## The rules, in order
1. **Start:** a stated commencement ("shall come into force from…") beats an edition date,
   which beats the issue date.
2. **End (versions):** a version ends when the next version of the same document starts.
   SS2/21's 2021 edition ends on 1 Nov 2024, when the 2024 update starts.
3. **End (repeals):** the last version ends when another document repeals it. The date is
   the stated "with effect from" date if there is one (SEBI SCORES: 4 Dec 2023), otherwise
   the date the repealing document was first issued.
4. **Future:** the PRA Rulebook already shows versions dated 1 Jan 2027. They are stored
   with status `future`, so "what will apply next year?" can be answered.

## Paragraph-level dates for old documents
We hold the 2025 text of the 2016 KYC direction. Treating the whole document as "valid
from 14 Aug 2025" would hide it from every question about 2024. So for the **oldest**
version we hold of a document, each paragraph is valid from its own date: the RBI
amendment footnote, FCA/PRA provision date, or else the original issue date. For later
versions, earlier wording sits in the earlier snapshot, so paragraphs simply follow
their version.

## What the corpus looks like now
32 current versions, 14 superseded, 2 future.

**Analogy:** the "valid from / valid until" printed on a bus timetable. Last year's
timetable isn't thrown away (you might need to check a journey you took then), but
nobody should read it to plan tomorrow.

## How to run / what you should see
`data/processed/validity.json`, e.g.
```json
"sebi-scores-master-2022@current": {"valid_from": "2022-11-07", "valid_to": "2023-12-04",
  "status": "superseded", "superseded_by": "sebi-scores-2023"}
```
