# 02: Citations and verification

**Files:** `src/reglens/generate/verify.py`, `src/reglens/generate/answer.py`

## What
After the model answers, three cheap checks run on **every** answer (no extra LLM call):

| Check | Example problem | What happens |
|---|---|---|
| **Valid markers** | `[9]` when there are only 8 sources | The marker is removed and reported |
| **Every claim cited** | A sentence about deadlines with no marker | Flagged "uncited" |
| **Lexical support** | "Banks must notify the RBI within **30 days** [2]" but source 2 says 10 days | Flagged "unsupported": content words (and *all* numbers) of the sentence must appear in the cited source |

The UI shows a green "Every statement cites a retrieved paragraph that supports it", or an
amber "2 statement(s) need checking against the sources".

## Why a cheap check *and* an LLM judge?
The lexical check is fast and catches the most dangerous error, a wrong number, but it's
blunt: a faithful paraphrase can score low. So it's a **warning light**, not a verdict. The
evaluation suite (phase 08) uses a separate LLM judge, from a different model family, to measure
true faithfulness and citation precision on a test set.

## From markers to citations
Each used marker becomes a citation object the UI can render: label (`[SS1/23 §2.4]`),
regulator, document title, status, validity dates, the paragraph text and links to the
document viewer and the regulator's website. Clicking a marker in the answer opens it.

**Analogy:** a proof-reader with a highlighter. They don't judge the argument; they check
every footnote points to a real page, and that the numbers in the sentence appear on it.
