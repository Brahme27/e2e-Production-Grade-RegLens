[RegLens guide](../README.md) › Part 14: The finish line

# 14.1 Results and weak spots

In [Part 13](../13-shipping-it/02-the-cloud-with-terraform-and-ci.md) we packed RegLens into
containers and wrote its cloud home down as code. The build is done. Now we step back, the way a
good engineer always should, and ask two plain questions: how good is it, and where does it fall
short? Every number below comes from the project's generated results page, measured on real
regulatory documents.

## Back to Meera

Meera asked what the rules said about the Internal Ombudsman on 5 January 2025. RegLens searched
about 4,800 paragraphs from 37 real RBI, SEBI, FCA and PRA documents, kept only text in force on
that day, ranked it, and answered in a few sentences, each citing the exact paragraph of the 2023
direction, marked as since superseded. When the 2026 Directions arrived, it turned them into
obligations, checked Sahyadri Bank's policy, and paused for her review before raising any tickets.

## The results, in plain words

| Question | Answer (naive RAG in brackets) |
|---|---|
| Does it find the right paragraph? | In the top 10 for 91% of questions (81%) |
| Does it show out-of-date rules? | Never in the top 5 (64% of questions) |
| Are answers true to the sources? | 87% of sentences supported, judged by a different model (72%) |
| Are the citations right? | 84% of sentences cite a source that supports them (68%) |
| Does it know when it doesn't know? | Declined every unanswerable test question |
| Can it be tricked? | Refused 9 of 10 adversarial prompts |
| Does it find replaced documents? | Supersession F1 of 0.98 |
| Does it spot policy gaps? | Told "covered" from "needs work" for 93% of 41 planted cases |
| How fast? | 1.4 s typical, 2.2 s slow, on a laptop processor plus the hosted model |

And the bill: building and evaluating everything took 486 LLM calls on the free tier, for **$0**.

## Where it's weak, and we say so

A results page that only lists strengths isn't trustworthy. RegLens's limitations page is as
important as its results, and these are the main points:

- **Comparison questions are the weakest.** "How do the FCA and the PRA differ on X?" scores an
  nDCG of 0.58, against 0.92 for plain lookups. One side is often missing from the top results.
- **It's cautious.** It wrongly declined 18% of answerable questions in the judged test. Safer than
  guessing, but the first thing to improve.
- **Obligation extraction misses some.** It finds 63% of the obligations a human listed. Everything
  it finds is genuine, but a reviewer still needs to read the rule.
- **The test set and the judge are LLM-assisted.** No compliance professional has reviewed the
  golden questions or the judge's labels yet. A human pass would make every number more trustworthy.
- **The policies are synthetic.** On real, messier bank policies, gap judgement would likely score
  lower.
- **Engineering trade-offs.** Paused impact runs live in memory and are lost if the API restarts.
  There are no user accounts in the console, so anyone who can reach it can use it. Hindi text in
  bilingual documents is skipped. The free tier allows about 1,000 requests a day per model; when it
  runs out, RegLens shows the relevant paragraphs instead of an answer.

## Next steps, given time and money

| With… | Next step |
|---|---|
| A graphics card | Swap in the larger reranker, measured as better but too slow on a laptop |
| A week | Give comparison questions a fixed share of results per regulator |
| A compliance expert | Review 50 golden questions and 100 judge labels |
| A real deployment | A database-backed checkpointer, and single sign-on in front of the console |
| A paid LLM tier | Run impact analysis in the background with progress updates |

## The habits that made it work

1. **Measure before believing.** Two techniques from the original plan made things worse in
   practice, including the LLM summaries in every chunk. Without the ablation, we'd have shipped
   them.
2. **Read failures, not only averages.** A perfect judge score turned out to rest on 7 answers.
3. **Run the real thing.** Docker found five problems that a green test suite had missed.
4. **Keep humans in the loop where it matters.** Repeals proposed by the LLM, and every gap
   judgement, go to a person.

> **Try it:** run `uv run poe results`. It rebuilds `docs/RESULTS.md` from the saved reports, so
> every number on that page, and in this chapter, comes from code rather than typing.

*Want the details? See `docs/RESULTS.md`, `docs/LIMITATIONS.md` and
`walkthrough/14-results-and-next-steps/README.md`.*

So far: we know what RegLens achieves, where it falls short, and what we'd do next. One chapter
left: everything we did, turned into a recipe you can reuse for your own project.

**Next →** [14.2 The recipe for your own project](02-the-recipe-for-your-own-project.md)
