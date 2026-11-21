[RegLens guide](../README.md) › Part 7: Finding the right paragraphs

# 7.1 Reading the question

In [Part 6](../06-indexing/03-qdrant-the-searchable-shelf.md) we built a searchable, date-aware
library. Now a question arrives. Before we search, it pays to read the question carefully: which
date is it about, which regulator, and what *kind* of question is it? A good receptionist does
the same before passing your call along, jotting "about 2025, about the RBI" on a sticky note.

## Cheap rules for exact things

Some parts of a question are exact and well-formed: dates and regulator names. For these we use
**regular expressions**, patterns that match the shape of text, such as "a day, a month name, a
year". They get it right every time, in microseconds, for free. From Meera's question they pull out:

- the **as-of date**: "As of 05 January 2025" becomes 5 January 2025;
- the **regulators**: Meera's question names none, so the search will look across all four; a
  question that said "RBI" would be searched against RBI text only;
- hints for later: comparison words ("compare", "differ"), overview words ("main themes",
  "summarise"), change words ("amended", "before").

Vague dates get a sensible guess. "In March 2023" becomes the 15th of March, and "in 2022" becomes 1
July: the middle of the period, the day least likely to sit right on the edge of a rule change.

Why not ask an LLM to read the date? It would cost an API call and about a second, and it would be
*less* reliable than a pattern for something this exact.

## Four kinds of question

Questions come in different shapes, and each shape needs different handling:

| Kind | Example | What search does differently |
|---|---|---|
| lookup | "How often must high-risk customers' KYC be updated?" | Standard search, today's rules |
| temporal | Meera's question, "as of 05 January 2025" | Search only the rules in force that day |
| comparison | "How do RBI and FCA outsourcing rules differ?" | One search per regulator, so both sides appear |
| global | "What are the main themes of the Consumer Duty?" | A few passages from each of several documents |

The piece that decides is the **router**. Think of a triage nurse: they don't treat anyone, they
send you down the right corridor.

## A very small model

The router is a **logistic regression**, the simplest kind of classifier. It weighs up pieces of
evidence and gives each route a probability, much as you might guess "rain" from dark clouds plus
wind plus a falling barometer. Its evidence is the question's bge-small vector (the 384 numbers from
chapter 6.2) plus five yes-or-no signals from the rules above, such as "has a date" or "names two
regulators".

Two rules are trusted over the model because they are never wrong: an explicit date means
*temporal*, and two regulators plus a comparison word means *comparison*. So Meera's question goes
straight down the temporal corridor.

Training happens once, offline. An LLM wrote 40 varied example questions for each route (five
cached calls), kept separate from our test questions so the router is never graded on its own
homework. **scikit-learn**, the standard Python library for classic machine learning, fits the
model. Then the learned weights are saved to a small file. At answer time, routing is a single
multiplication of numbers: about a millisecond, no scikit-learn in the production image, and no LLM
call. On 175 test questions it had never seen, the router chose the right route **90%** of the
time. Its most common slip, reading a lookup as an overview, only changes how many documents
contribute passages: a mild cost.

> **A bump on the road:** the first router also learned a fifth route, "out of scope", for things
> like poems and stock tips. It failed badly. It rated real compliance questions as *more*
> off-topic than "What's the weather in Mumbai?", and would have refused 27 legitimate questions.
> We removed it. Off-topic requests are now handled by the guardrails (Part 11) and by declining
> when nothing relevant is found (Part 8), and router accuracy rose from 74% to 90%. The lesson: a
> model that's wrong in the costly direction is worse than no model at all.

> **Try it:** run `uv run poe router`. It trains the router from the cached example questions,
> checks it, and saves the weights for the API to use.

*Want the details? See `walkthrough/06-retrieval/01-reading-the-question.md`, `02-the-router.md`
and `src/reglens/retrieve/router.py`.*

So far: RegLens reads the date and regulators with exact rules, and a tiny model decides what kind
of question it is. Next, the search itself: two searches at once, and a fair way to combine them.

**Next →** [7.2 Two searches and a fair vote](02-two-searches-and-a-fair-vote.md)
