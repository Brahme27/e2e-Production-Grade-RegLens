# 03: Hybrid search and filters

**Files:** `src/reglens/index/store.py`, `src/reglens/retrieve/pipeline.py`

## What
Three searches in one Qdrant request:
1. **dense**: the 30 chunks closest in *meaning* to the question;
2. **sparse (BM25)**: the 30 chunks sharing the most important *exact words*;
3. **fusion**: the two lists merged with **Reciprocal Rank Fusion** (RRF): a chunk scores
   `1/(60 + rank)` in each list and the scores add up. A chunk ranked high in both wins.

Then the **filters** are applied *inside* the search:
- **as of**: only text valid on the date (`valid_from ≤ date < valid_to`); today by default;
- **regulator**: a question naming exactly one regulator searches only that regulator.

## Why hybrid?
| Question | Dense alone | BM25 alone | Hybrid |
|---|---|---|---|
| "duties when a cloud vendor fails" | finds "cloud service provider" text | misses (different words) | finds it |
| "What does SS1/23 Principle 3.4 say?" | blurs the identifier | exact hit | exact hit |

Measured on the golden set: dense (row B) recall@10 = 0.844; hybrid (row C) = 0.866.

## Why filter inside the search, not afterwards?
If we searched first and then dropped repealed text, the top 30 could be mostly repealed
paragraphs (the 2016 KYC direction looks a lot like the 2025 one), leaving too few valid
ones. Filtering inside the search means all 30 candidates are valid on the date.

**Analogy:** asking two librarians, one who knows subjects and one who knows exact titles,
and trusting the books *both* recommend. The date filter means neither even looks at
withdrawn editions.
