# 02: Obligations

**File:** `src/reglens/impact/obligations.py` (extraction)

## What
An **obligation** is one thing the firm must (or must not) do, in a fixed shape:

```json
{"text": "The bank must report a vacancy in the IO post to the RBI within 10 working days
          and appoint a new IO within three months.",
 "actor": "bank", "action": "inform RBI and appoint a new IO", "condition": "if the IO post
 falls vacant for reasons beyond the bank's control", "deadline": "10 working days; 3 months",
 "source_ref": "8", "severity": "high"}
```

The LLM reads up to three paragraphs at a time (cheaper than one call per paragraph) and
returns all obligations it finds. Two guard rails:
- definitions, applicability clauses and "the RBI *may*…" statements are excluded by the prompt;
- every obligation must cite one of the paragraphs it was shown. An obligation pointing at
  a paragraph that wasn't in the batch is dropped.

## Which paragraphs?
If an older version of the document exists, only paragraphs that **changed substantively**
are sent (via the paragraph diff from phase 04 and the document viewer). A rule that moved a
comma doesn't generate work. A brand-new document is read in full.

## How it is measured (phase 08)
- **Recall** against the 41 hand-labelled obligations: did it find the ones a human flagged?
  (Matched by meaning: embedding similarity ≥ 0.80 within the same paragraph.)
- **Precision** by a judge model: is each extracted item a genuine obligation in that paragraph?
  (The gold list covers the important obligations, not every minor one, so unmatched extras
  aren't automatically wrong.)

**Analogy:** turning a dense legal letter into a to-do list, with each to-do pointing back to
the sentence it came from.
