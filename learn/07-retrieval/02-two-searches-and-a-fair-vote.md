[RegLens guide](../README.md) › Part 7: Finding the right paragraphs

# 7.2 Two searches and a fair vote

In the [last chapter](01-reading-the-question.md) RegLens read Meera's question: it's about 5
January 2025, and it's a "temporal" question. Now we search. Remember from chapter 6.2 that every
chunk has two vectors, one for meaning and one for exact words. We use both at once, and then we
need a fair way to merge two different opinions into one list.

## Two librarians

Picture two librarians. The first knows every *subject*: ask about "duties when a cloud vendor
fails" and she brings books about outsourcing to cloud providers, whatever words they use. The
second knows every *exact title and reference*: ask for "SS1/23 Principle 3.4" and he walks
straight to it. Each misses what the other finds.

| Question | Meaning only | Exact words only | Both |
|---|---|---|---|
| "duties when a cloud vendor fails" | finds "cloud service provider" text | misses it (different words) | finds it |
| "What does SS1/23 Principle 3.4 say?" | blurs the reference | exact hit | exact hit |

Using both is called **hybrid search**. In one request to Qdrant, RegLens asks for the 30 chunks
closest in meaning (the dense search) and the 30 chunks with the best keyword match (the BM25
search). For Meera's question, the exact words "Internal Ombudsman" and the meaning of "rejects the
Ombudsman's decision" can each pull paragraph 12 into one of the lists.

## Merging two rankings fairly

Now we have two ranked lists, and a problem: their scores are on completely different scales.
A meaning score of 0.83 and a keyword score of 14.2 can't be added up. It would be like adding
marks out of 10 to marks out of 100.

**Reciprocal Rank Fusion**, or **RRF**, sidesteps the problem by ignoring the scores and using
only the *positions*. Each chunk gets a little credit from each list: one divided by (60 plus its
rank). First place earns 1/61, second place 1/62, and so on. Add the credits from both lists, and
re-sort. The 60 softens the gap between neighbouring places, so no single list can overrule the
other on its own. A chunk that ranks high in *both* lists wins.

Think of two judges at a cooking contest who each rank the dishes. You don't trust their raw marks
(one is a harsh marker), but a dish both judges put near the top is a safe winner.

Did it help? In our measurements (Part 9 explains them properly), the share of questions whose
right paragraph appeared in the top 10 rose from 84% with meaning-only search to 87% with hybrid
search. A modest gain, and a welcome one: keywords catch exact references like "SYSC 8.1.8",
while meaning catches the paraphrases.

## Filters inside the search

Before any ranking happens, two filters narrow what can come back at all, both applied *inside*
the search as we saw in chapter 6.3:

- **As of**: only text in force on the date. That's 5 January 2025 for Meera; today for questions
  with no date.
- **Regulator**: a question that names exactly one regulator searches only that regulator's text.

## Special handling for two kinds of question

The router's decision from the last chapter changes the search for two kinds of question.

**Comparisons** ("How do the RBI and the FCA differ on outsourcing?") get one search per named
regulator, each with half the candidates. Later, at least two passages from each regulator are kept.
Without this, a very strong match from one regulator could crowd the other side out entirely, and
the answer would compare something with nothing.

**Overviews** ("What are the main themes of the Consumer Duty?") take at most two passages from any
single document, so the answer draws on several documents instead of ten paragraphs of one.

Meera's question is neither. It's a temporal lookup, so it gets a straight hybrid search with the
date filter, and passes about 30 candidates on to the next step.

*Want the details? See `walkthrough/06-retrieval/03-hybrid-search-and-filters.md`,
`05-the-pipeline.md` and `src/reglens/retrieve/pipeline.py`.*

So far: two searches, one by meaning and one by exact words, merged fairly by rank, inside a date
filter. The shortlist is good, but its order is rough. Next, we read the shortlist closely and put
the best paragraphs on top.

**Next →** [7.3 A second, closer reading](03-a-second-closer-reading.md)
