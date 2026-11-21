[RegLens guide](../README.md) › Part 9: Proving it with numbers

# 9.1 The golden set

In [Part 8](../08-answers/03-words-as-they-are-written.md) RegLens learned to write cited answers,
check them, decline when it should, and stream the result. It *seems* to work. But "seems to work"
is how bad systems get shipped. RegLens was built **eval-first**: every technique had to prove,
with a number, that it helped. This part shows how, starting with the exam paper.

## An exam with an answer key

A **golden set** is a fixed list of test questions where we already know the right answer. Think
of an exam where each question was written from a specific page of the textbook, so the marker
knows exactly which page a good answer must cite. Ours has **195 questions** of six kinds:

| Kind | How many | "Correct" means |
|---|---|---|
| Lookup | 80 | The paragraph the question was written from is found |
| As of a date | 29 | The *old* wording, in force on that date, is found, not today's |
| Comparison | 21 | Paragraphs from **both** regulators are found |
| Overview | 15 | The expected documents appear |
| Unanswerable | 30 | RegLens declines |
| Adversarial | 20 | RegLens refuses a trick or harmful request |

Meera's question is one of the 29 "as of a date" questions. Its answer key points to paragraph 12
of the 2023 Internal Ombudsman direction, so if a search returns today's 2026 Directions instead,
it scores zero, however relevant they look.

## Writing the questions

Writing 195 good questions by hand takes days, so we split the work. For lookups, an LLM read one
real paragraph and wrote a question it answers, **in different words**: it could not reuse more
than four words in a row, so search can't win by exact copying. "As of" questions were made the
same way from paragraphs of *superseded* versions. The overview, unanswerable and adversarial
questions were written by hand, including traps like the non-existent "SS3/27".

Two details keep the scores honest. **Near-duplicates count**: the same KYC rule appears in the
bank and NBFC directions, so a retrieved paragraph counts as correct if its text is at least 70%
identical to the source *and* it was in force on the question's date. And the router from Part 7
was trained on **separately generated** questions, never on these.

We label the set honestly, too. The generated questions were written by an LLM and checked
automatically (each must be answerable from its paragraph). Nobody from a compliance team has
reviewed them yet, and that review is the most valuable next improvement to the evaluation.

## Scoring the search

Before judging answers, we judge retrieval: did the right paragraphs come back, and how high? Four
scores do the job:

- **Recall@10**: of the paragraphs a question needs, what share are in the top 10 results?
- **nDCG@10**: like recall, but it rewards finding them *near the top*. People read a results list
  from the top, so a right paragraph at position 1 is worth much more than one at position 9. It
  runs from 0 to 1, where 1 means every right paragraph sits at the very top.
- **MRR** (mean reciprocal rank): one divided by the position of the first right paragraph,
  averaged over all questions. First place scores 1, second place 0.5, third 0.33.
- **Stale in top 5**: the share of questions where a paragraph that was **not in force** on the
  question's date shows up in the top 5.

The last one is our own, and for a compliance tool it matters most. A general search engine can
show last year's page next to this year's. RegLens can't: if a repealed rule sits in the top 5, the
answer writer may quote it as current, and someone may act on it.

## Free to run, as often as we like

Notice that none of these scores needs an LLM. They only compare paragraph ids: which ones came
back, and which ones the answer key expected. So every variant of the search can be scored on all
145 answerable questions, for free, as often as we like. The expensive LLM-based scoring is saved
for the answers themselves, in chapter 9.3.

*Want the details? See `walkthrough/08-evaluation/01-the-golden-set.md`,
`02-retrieval-metrics.md` and the questions themselves in `evals/golden/`.*

So far: we have an exam of 195 questions with an answer key, and four ways to score a search. Next,
we use them to test every technique, one at a time.

**Next →** [9.2 The ablation](02-the-ablation.md)
