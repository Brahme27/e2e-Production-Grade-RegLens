[RegLens guide](../README.md) › Part 8: Answers you can check

# 8.2 Checking receipts, and saying "I don't know"

In the [last chapter](01-answers-with-receipts.md) the model wrote an answer with a `[1]`-style
marker after every sentence, and RegLens turned the markers into real citations. But a rule in a
prompt is a request, not a guarantee. In this chapter we check the receipts, and we teach RegLens
the most underrated skill in AI: declining to answer.

## Three cheap checks on every answer

**Citation verification** means checking that each citation really backs up the sentence it's
attached to. RegLens runs three quick checks on every single answer, with no extra LLM call:

| Check | Example problem | What happens |
|---|---|---|
| Real markers | `[9]` when there are only 8 sources | The marker is removed and reported |
| Every claim cited | A sentence about a deadline with no marker | Flagged as "uncited" |
| Words support it | "within **30 days** [2]", but source 2 says 10 days | Flagged as "unsupported" |

The third check is the clever one. The meaningful words of a sentence, and **every number** in it,
must appear in the source it cites. Wrong numbers are the most dangerous mistake in compliance (a
deadline of 30 days instead of 10 could cost a bank dearly), and this check catches them instantly.

The console then shows either a green note, "Every statement cites a retrieved paragraph that
supports it", or an amber one, such as "2 statement(s) need checking against the sources". Think
of a proof-reader with a highlighter. They don't judge the argument; they check that every footnote
points to a real page, and that the numbers in the sentence appear on it.

The check is blunt, though. A faithful paraphrase that uses different words can fail it. So it's
a **warning light, not a verdict**. To measure true faithfulness, Part 9 brings in a second model
as a judge.

> **A bump on the road:** reading the first full evaluation by hand, we found 5 of 60 answers
> marked "uncited" even though they had citations. gpt-oss sometimes writes its markers in its own
> native style, with heavy square brackets, `【1】`, instead of `[1]`, and the checker didn't
> recognise them. The fix was to tidy all markers into one style before checking. The lesson:
> models have habits. Normalise what they write before you judge it.

## Saying "I don't know"

**Abstention** means the system deliberately declining to answer. In compliance, a confident wrong
answer is worse than no answer, because someone may act on it. RegLens abstains in two places.

**Before the LLM, for free.** If even the best reranked paragraph scores below a threshold, the
corpus almost certainly doesn't cover the question. Ask "What leverage ratio does the PRA require?"
when no leverage rules are indexed, and RegLens replies at once with a polite "I could not find
this", without spending an API call.

**By the LLM.** If the paragraphs are related but don't contain the answer, the prompt's rule makes
the model reply `NOT_FOUND`, which becomes the same polite message.

## A threshold chosen by data, not by hand

Where should the threshold sit? Too high, and RegLens refuses questions it could answer. Too low,
and it bluffs. We don't guess. The evaluation step **calibrates** it: it runs retrieval on test
questions we know are answerable and on ones we know aren't, then picks the reranker score that best
separates the two groups, counting both kinds of mistake equally. The chosen value is saved in a
small report file that the API loads at start-up.

Our test set includes deliberate traps that *sound* real, such as "What did the PRA's SS3/27 on AI
governance require?" There is no SS3/27. A system that answers that question is making things up.

The result, measured in Part 9: RegLens declined **every one** of the unanswerable test questions.
The price of that caution is honest too: it also declined **18%** of questions it *could* have
answered, mostly tricky comparison and "as of" questions whose best paragraph scored under the
line. A good librarian who says "we don't hold that; try the regulator's site" is more useful than
one who hands you the nearest book and hopes, but 18% is the first thing we'd improve next.

*Want the details? See `walkthrough/07-answers/02-citations-and-verification.md`,
`03-abstention.md` and `src/reglens/generate/verify.py`.*

So far: every answer is checked for real markers, cited claims and matching numbers, and RegLens
declines when the corpus can't support an answer. Next, we make the answer appear word by word, the
way people now expect.

**Next →** [8.3 Words as they are written](03-words-as-they-are-written.md)
