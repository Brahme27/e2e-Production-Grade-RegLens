[RegLens guide](../README.md) › Part 5: Time

# 5.1 Who replaced whom

In the [last chapter](../04-parsing/01-from-pages-to-citable-paragraphs.md) every document became
a clean list of numbered paragraphs. But a paragraph on its own doesn't know whether it still
applies. A compliance copilot that ignores time will happily quote a rule that was repealed last
year. In this part we teach RegLens *when* each piece of text applied, starting with a simple
question: which document replaced which?

## A family tree of rules

We build a **supersession graph**. A graph, in this sense, is a set of dots joined by arrows.
Each dot is a document, and each arrow means "this newer document replaced (or amended) that older
one":

```
RBI Internal Ombudsman Directions 2026 ──SUPERSEDES──▶ RBI Internal Ombudsman Direction 2023
SEBI SCORES circular 2023              ──SUPERSEDES──▶ SEBI SCORES master circular 2022
SEBI cyber framework (CSCRF) 2024      ──SUPERSEDES──▶ 43 older cyber circulars and letters
```

The first arrow is Meera's story. In total the graph has 56 arrows, and each one carries its
**evidence**: the document and paragraph where the repeal sentence sits, so a person can check it.

## Rules first

Most repeals are written plainly. A sentence uses a repeal verb (*repeal, rescind, supersede,
stand withdrawn*) and **names** the old document, by its official number or full title. Simple
text-matching rules find these. The details took care: list items under "this circular rescinds
the following circulars" inherit the verb from the sentence above them; PDF line wrapping breaks
numbers like "CIR/2 022/68", so we repair them before matching; and "with effect from December 04,
2023" becomes the arrow's start date.

Rules cost nothing, run instantly and never invent anything. So they always go first.

## An LLM for the vague cases

Some repeals name nothing at all. The RBI's 2025 and 2026 directions say things like *"the existing
Directions, instructions, and guidelines relating to Know Your Customer as applicable to Commercial
Banks stand repealed."* No title, no number. Rules can't resolve that, but a reader who knows the
corpus can.

So, for these clauses only (nine of them in the whole corpus), we ask an LLM. It receives the
clause and a list of **older documents from the same regulator**, and answers in JSON with the ones
the clause covers. It may only pick from the list we gave it; any id it invents is thrown away.
The call goes through the same notebook-keeping client from chapter 2.3, so it is paid for once.

## Marking our own homework honestly

How good is this? We wrote a **gold set**: an answer key of 57 arrows, labelled by reading the
documents themselves, not the extractor's output (otherwise we'd be grading our own homework).
Then we measured two things:

- **Precision**: of the arrows we drew, how many are real?
- **Recall**: of the real arrows, how many did we find?

A fishing net is a good picture. Precision asks how much of the catch is actually fish; recall
asks how many of the fish in the lake ended up in the net. **F1** is a single score that balances
the two, and it is only high when both are.

Rules alone scored an F1 of **0.944**, but found only 3 of the 8 repeals between documents inside
our corpus, because the vague RBI ones were invisible to them. Rules plus the LLM scored **0.982**
and found **all 8**, for the price of nine free API calls.

> **A bump on the road:** the LLM made one confident mistake. It decided that the 2025
> *Governance* Directions also repealed the 2023 *IT Governance* direction, fooled by the shared
> word. In reality, IT governance was repealed eight months later by a different document. That
> wrong arrow would have hidden still-valid text from "as of" questions. A clearer prompt didn't
> change the model's mind. So we didn't keep tweaking the prompt for one example (that would be
> tailoring the test to the answer). Instead, **the model proposes and a person approves**: a
> reviewer's decision, with its reason, lives in `configs/supersession_overrides.yaml` and is
> applied before any dates are worked out. The scores above are for the raw extractor, before
> review, so they stay honest. The lesson: where a mistake is costly, put a human in the path.

> **Try it:** run `uv run poe temporal`. It builds the graph, scores both
> extractors against the gold set (you'll see the two F1 scores in the log), and saves everything.
> The nine LLM calls replay from the notebook, so no key is needed.

*Want the details? See `walkthrough/04-time-and-supersession/01-the-supersession-graph.md`,
`02-measuring-the-extractor.md`, `docs/adr/0003-llm-proposes-human-approves.md` and
`src/reglens/temporal/`.*

So far: RegLens knows which documents replaced which, with evidence, and a person signs off on the
risky arrows. Next, we turn those arrows into dates: when did each piece of text start and stop
applying?

**Next →** [5.2 Valid from, valid to](02-valid-from-valid-to.md)
