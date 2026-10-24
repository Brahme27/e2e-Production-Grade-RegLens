# 01: Chunking

**File:** `src/reglens/index/chunking.py`

## What
A **chunk** is the piece of text the search engine returns. We build two kinds, so that
phase 08 can measure which works better:

| Strategy | How | Chunks |
|---|---|---|
| `fixed` (naive baseline) | Glue a document's text together and cut every ~380 words (~512 tokens) | 1,120 |
| `paragraph` | One chunk per numbered paragraph; very long paragraphs split at sub-item boundaries | 5,203 |

Every chunk carries everything needed to cite it and to filter it by date: document,
version, regulator, paragraph ref, heading path, `valid_from`/`valid_to`, status.

## Why paragraphs?
Regulation is written and cited by paragraph. A fixed window often starts mid-rule ("…
and the Board shall") and mixes two unrelated obligations, which confuses both the search
and the answer. A paragraph chunk is a complete thought with a ref an auditor can check:
`[RBI/DOR/2025-26/171 §95]`.

## The tricky parts
- **Giant paragraphs.** The KYC definitions paragraph has 22,000 characters. It is split
  at line boundaries (sub-items "(i)", "(ii)") into pieces of at most ~300 words, each
  still cited as paragraph 3 (part 2 of 9).
- **Validity per chunk.** For the oldest version we hold of a document, each chunk's
  `valid_from` comes from its own paragraph date (amendment footnote, FCA/PRA provision
  date, or the original issue date). See phase 04.
- **Stable ids.** A chunk's id is a hash of (document, version, position, ref, part), so
  re-indexing the same text overwrites rather than duplicates.

**Analogy:** cutting a cookbook into recipes (paragraph) instead of into equal-length
strips of paper (fixed). Strips are easy to make, but nobody can cook from half a recipe.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_index_retrieve.py -q --no-cov -k chunk
```
