# 01: The golden set

**Files:** `src/reglens/evals/golden.py`, `evals/golden/golden_v1.jsonl`, `evals/golden/handwritten.yaml`

## What
195 questions with known right answers:

| Type | n | How it was made | "Correct" means |
|---|---|---|---|
| Lookup | 80 | The LLM read one real paragraph (20 per regulator, spread across documents) and wrote a question it answers, in different words | That paragraph (or a near-duplicate) is retrieved |
| As of a date | 29 | Same, from paragraphs of **superseded** versions, asked "As of <date when it applied>, …" | The *old* wording is retrieved, not today's |
| Comparison | 21 | Two similar paragraphs from different regulators on the same topic | **Both** sides are retrieved |
| Overview | 15 | Hand-written ("Summarise the PRA Fundamental Rules") | The expected documents appear |
| Unanswerable | 30 | Hand-written: topics we don't index, plus traps like "SS3/27" (doesn't exist) | The system abstains |
| Adversarial | 20 | Hand-written: injections, jailbreaks, harmful or off-topic requests | The system refuses |

## Details that keep the scores honest
- **Near-duplicates count.** The same KYC rule appears in the bank and NBFC directions; unchanged
  PRA rules appear in every snapshot. A retrieved paragraph is correct if its text is ≥ 70%
  identical (5-word shingles) to the source **and** it was in force on the question's date.
- **Paraphrase, not copy.** The question writer may not reuse more than 4 consecutive words, so
  retrieval can't win by exact string matching alone.
- **Separate from training.** The router was trained on different, separately generated questions.

## An honest label
The generated items are **LLM-written and automatically validated** (each must be answerable from
its paragraph; the generator can refuse). The unanswerable and adversarial items were written by
hand. A full human review of every generated question is still open: it's the most valuable
next improvement to the evaluation.

**Analogy:** an exam paper where each question was written from a specific textbook page, so
the marker knows exactly which page a good answer must cite.
