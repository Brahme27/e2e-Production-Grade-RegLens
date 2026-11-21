[RegLens guide](../README.md) › Part 9: Proving it with numbers

# 9.2 The ablation

In the [last chapter](01-the-golden-set.md) we built an exam of 195 questions and four ways to
score a search. Now we use them for the most important experiment in the project: proving which of
our techniques actually help, and by how much.

## Change one thing at a time

An **ablation** starts from the simplest possible system and adds one technique per step,
measuring every step on the same questions. Each row keeps everything from the row above it and
adds one thing.

It's how a careful cook tunes a recipe. You don't change the flour, the oven and the sugar at once
and then guess which one helped. You change one thing, taste, write it down, and move on. And
because of the "recipe with switches" from chapter 7.3, each row is only a different set of
switches on the code that runs in production.

## The results

Here are the main rows, scored on the 145 answerable golden questions:

| Row | What was added | nDCG@10 | Stale in top 5 |
|---|---|---|---|
| A | Naive: fixed-size chunks, meaning-only search | 0.652 | 64% |
| B | + paragraph chunks | 0.730 | 60% |
| C | + hybrid search with RRF | 0.754 | 66% |
| D | + the MiniLM reranker | 0.790 | 59% |
| E1 | + context headers on every chunk | 0.824 | 46% |
| E2 | + an LLM summary of the document in every chunk | 0.734 | 40% |
| **F** | E1 + router, "as of" filter, regulator filter (**production**) | **0.853** | **0%** |

Row A is roughly what a typical "chat with your PDFs" tool does. Row F is RegLens.

## Reading the table

**Paragraph chunks (A to B)** gave the biggest single jump. Regulations are written in numbered
paragraphs, so a chunk that follows them holds a complete rule instead of halves of two.

**Hybrid search (B to C)** helps with exact references, which keywords find and meaning blurs.

**The reranker (C to D)** didn't change *whether* the right paragraph was found, but moved it up
the list. It also costs most of the search time.

**Context headers (D to E1)** lifted ranking again. For plain lookups, nDCG rose from about 0.80 to
0.93, because a lonely paragraph now carries its regulator and document name.

**Row F is the compliance row.** Look at the last column. In every row before it, between 40% and
66% of questions had a repealed or not-yet-in-force paragraph in the top 5. With the "as of" filter
working inside the search, that drops to **zero**, and "as of" questions like Meera's improved
their nDCG from 0.63 to 0.79. Recall@10 for row F is 0.914: the right paragraph is in the top 10
for about nine questions in ten.

One more idea, row G, spread overview questions across more documents. It scored within noise of F,
slightly lower, so production stays on F.

> **A bump on the road:** look at row E2. Adding an LLM-written summary of each document to every
> chunk sounded like a sure improvement. Instead, nDCG *fell* from 0.824 to 0.734. Our reading:
> every chunk of a document received the *same* summary, which pulled them all towards each other
> and towards vague questions; the summary also took up part of the roughly 220 words the reranker
> reads, pushing out the paragraph's own words. So the summaries were **not shipped** for search
> (they're still used as document overviews for "main themes" questions). The lesson: measure
> before you believe. Without the ablation, this idea would be in production, quietly making
> things worse.

## Where it is still weak

Broken down by kind, row F scores nDCG@10 of 0.92 on lookups, 0.97 on overviews, 0.79 on "as of"
questions, and only **0.58 on comparisons**. "Compare the FCA and the PRA on X" needs the right
paragraph from *both* sides, and one side is often missing. Splitting comparisons into one search
per regulator helped, but it remains the weakest category, and the README says so in plain words.

## A gate that guards the numbers

The production row's scores are saved in `evals/baseline.json`. Every week, and whenever code reaches the main line, CI rebuilds the corpus
from the regulators' websites, re-runs row F, and **fails the build** if recall, nDCG or MRR drops
by more than 0.03, or if a single stale paragraph reaches the top 5. If a regulator redesigns a web
page and silently breaks our parser, it shows up as a red build, not as wrong answers to users.

> **Try it:** run `uv run poe ablation`. It scores every row on the golden set, with no LLM calls,
> in about 20 minutes on a laptop, and prints a table like the one above.

*Want the details? See `walkthrough/08-evaluation/03-the-ablation.md`, `05-what-we-learned.md` and
`docs/RESULTS.md`.*

So far: one change at a time, we proved what helped, dropped what didn't, and turned the
production numbers into a contract CI enforces. Next, we score the answers themselves, with a
second model as the examiner.

**Next →** [9.3 The LLM judge](03-the-llm-judge.md)
