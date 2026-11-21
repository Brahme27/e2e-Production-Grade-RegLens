[RegLens guide](../README.md) › Part 1: The idea

# 1.2 Following one question

In the [last chapter](01-rules-that-keep-changing.md) we saw why compliance teams need answers
that are cited and dated. Now let's jump ahead to the end. Imagine RegLens is finished, and follow
one real question through it, one stop at a time. Every stop is a part of this guide, so this
chapter is also your map.

## Meera's question

Meera is a compliance analyst at **Sahyadri Bank**, an Indian bank with 140 branches. (Both Meera
and the bank are invented; the project uses Sahyadri Bank as its test firm.) The auditors are
reviewing complaints the bank handled in early 2025, and they need to know what the rules said
about the bank's **Internal Ombudsman**: an independent senior person inside the bank who reviews
complaints the bank has rejected, before the customer goes to the RBI.

Here is her question, word for word as it appears in our test set:

> *"As of 05 January 2025, how often must the Internal Ombudsman report to the Board committee
> handling customer service and protection, and what is required if the regulated entity rejects
> the Ombudsman's decision?"*

There is a twist. The rule that applied on that day, the RBI's 2023 Master Direction on Internal
Ombudsmen, has since been **replaced** by new 2026 Directions for commercial banks. An answer
from today's rules would be wrong. The right answer lives in the old document, in paragraph 12.

## The route

```
Meera's question
      │
      ▼
① Guardrails ─────────── "Is this a genuine question, or a trick?"
      │
      ▼
② Reading the question ─ date: 5 Jan 2025 · kind: "as of a date"
      │
      ▼
③ Search ─────────────── only paragraphs in force on 5 Jan 2025
      │
      ▼
④ A closer reading ───── the best 8 paragraphs move to the top
      │
      ▼
⑤ Answer ─────────────── the LLM writes, with a [1] marker after every sentence
      │
      ▼
⑥ Checks ─────────────── every marker must point to a paragraph that supports it,
                          or RegLens says "I could not find this"
```

Let's walk it slowly.

**① Guardrails** come first: checks that catch tricks such as "ignore your instructions".
Meera's question is genuine, so it passes. That's Part 11.

**② Reading the question** happens with cheap, exact rules: they spot the date and any regulator
named.
A tiny trained model then decides what kind of question it is: a plain lookup, an "as of a date"
question, a comparison between regulators, or a request for an overview. That's Part 7.

**③ Search** relies on work done long before Meera typed anything. The documents were downloaded
(Part 3), cut into numbered paragraphs (Part 4), stamped with the dates they were in force (Part
5) and made searchable (Part 6). Now the search looks only at text that applied on 5 January
2025. The 2026 Directions didn't exist yet, so they are invisible. That's Part 7.

**④ A closer reading** re-reads the shortlist against the question and puts the best paragraphs
on top, where the answer writer pays the most attention. Also Part 7.

**⑤ The answer** is written by an LLM that sees only those paragraphs and must cite them. Our test
set records the right answer: the Ombudsman reports **at least every six months, preferably every
quarter**, and rejecting the Ombudsman's decision **needs the approval of the bank's Competent
Authority**. The words appear on screen as they are written. That's Part 8.

**⑥ The checks** make sure every citation points to a real paragraph that supports the sentence.
If the documents don't contain an answer, RegLens declines politely instead of guessing. Also
Part 8.

## When the rule changes

Meera's story has a second half. The new 2026 Directions bring new duties, and her bank's own
complaints policy was written in 2024. RegLens reads the new rule, turns it into a list of
**obligations** (things the bank must or must not do), finds the matching clauses in Sahyadri's
policy, and judges each one: covered, partly covered, or not covered.

One example: the new rule says rejected complaints must reach the Internal Ombudsman **within 20
days**, while the policy says **25 days**. That's "partly covered". Then the workflow **stops** and
waits for a person to agree or disagree with each judgement. Only after approval does it create
tickets for the work. That's Part 10.

## Proving it works

We built a test set of 195 questions with known answers (Meera's is one of them) and measured
each technique, one at a time, keeping only what helped. That's Part 9. Around it sits the
engineering: an API and a web console (Part 12), Docker and cloud files for AWS (Part 13).

## The finished picture

When we finish, one command starts everything on a laptop. You open the console, type Meera's
question, pick 5 January 2025 as the date, and watch a cited answer appear, with each citation
clickable. Every number in the project's README is produced by code, not typed by hand.

*Want the details? See `walkthrough/00-big-picture/README.md` and
`walkthrough/14-results-and-next-steps/README.md`.*

So far: you have seen the whole route once, with one real question. Next, we name the big idea
behind it and open the toolbox.

**Next →** [1.3 The toolbox, and what RAG means](03-the-toolbox.md)
