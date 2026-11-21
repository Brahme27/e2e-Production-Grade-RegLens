[RegLens guide](../README.md) › Part 7: Finding the right paragraphs

# 7.3 A second, closer reading

In the [last chapter](02-two-searches-and-a-fair-vote.md) hybrid search and RRF gave us a
shortlist of about 30 paragraphs, all in force on Meera's date. The shortlist is good, but its
order is rough, and order matters: the answer writer pays most attention to what comes first. So
we read the shortlist again, this time properly.

## Skimming the spines, then opening the books

The first search was fast because it compared vectors made *separately*: one for the question,
one for each paragraph, computed long before the question arrived. That's like skimming the spines
of books on a shelf. Quick, but shallow.

A **reranker** does the slow, careful version. It's a **cross-encoder**: a model that reads the
question and one paragraph *together*, word against word, and gives a single relevance score. It
notices things a separate comparison can't, such as whether the paragraph actually answers the
"how often" in Meera's question or only mentions the Ombudsman in passing. This is like opening
each of the 30 shortlisted books at the right page and reading it against your question.

Reading together is far more accurate and far slower, which is exactly why we run it only on the
top 30 candidates and keep the best 8.

## The model we chose, and the one we didn't

The plan named a large, excellent reranker, **bge-reranker-v2-m3**, with 568 million parameters.
We measured it against a small one, **MiniLM-L6**, with 22 million, on the same 30 test questions
on our laptop:

| Reranker | Ranking quality (nDCG@10) | Time per question |
|---|---|---|
| MiniLM-L6 (small) | 0.779 | under 2 seconds |
| bge-reranker-v2-m3 (large) | 0.804 | about 9 times longer (median) |

Don't worry about nDCG yet: Part 9 explains it. For now, read it as "how well the right paragraphs
are ordered, out of 1". The large model is a little better, but nine times slower at the median would blow our
answer-time budget of six seconds many times over on a laptop. So MiniLM serves every question,
and the large model is documented as the first upgrade if a graphics card ever becomes available.
Both run through fastembed, like our embeddings.

## The gain from reranking

Across all our test questions, adding the reranker barely changed *whether* the right paragraph
was in the top 10. That's expected: a reranker reorders the candidates; it can't find paragraphs
the first search missed. What changed is *where* the right paragraph sits. Ranking quality rose
from 0.75 to 0.79, and the right paragraph moved noticeably closer to first place. It also costs
most of our search time, about a second and a half per question, which is why we measured it
before accepting it.

## One recipe with switches

All of retrieval runs through a single object with switches, one per technique:

```
question → read signals → route → hybrid search (date + regulator filters)
         → rerank → keep both sides / spread documents → top 8 paragraphs
```

Which index variant? Dense, sparse or hybrid search? Which reranker, or none? Date filter on or
off? Router on or off? Each is one setting. This matters more than it looks. In Part 9, every row of
our big comparison table is a different set of switches on **the same code that runs in
production**. There is no separate "experiment" version that could drift away from what users get.

It's a recipe with switchable steps: turn each step on in turn, taste, and you know exactly which
ingredient made the dish better.

For Meera's question, the switches are all on: temporal route, date filter of 5 January 2025,
hybrid search across all regulators, MiniLM reranking, top 8 kept. Those 8 paragraphs, each with its
document, reference, status and validity window, are what the answer writer gets to read.

*Want the details? See `walkthrough/06-retrieval/04-reranking.md`, `05-the-pipeline.md`,
`docs/adr/0004-cpu-sized-models.md` and `src/reglens/retrieve/rerank.py`.*

So far: RegLens reads the question, searches by meaning and exact words inside a date filter, and
re-reads the shortlist to put the best 8 paragraphs on top. Next, the model finally writes an
answer, with a receipt for every sentence.

**Next →** [8.1 Answers with receipts](../08-answers/01-answers-with-receipts.md)
