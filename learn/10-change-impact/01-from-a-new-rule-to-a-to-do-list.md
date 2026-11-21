[RegLens guide](../README.md) › Part 10: Change impact

# 10.1 From a new rule to a to-do list

In [Part 9](../09-evaluation/03-the-llm-judge.md) we proved RegLens answers questions well. But
answering questions is only half of Meera's job. On 14 January 2026, the RBI's new Internal
Ombudsman Directions for commercial banks took over from the 2023 direction. Her real question now
isn't "what does it say?" but "**what must Sahyadri Bank change?**" This is the work compliance
teams actually pay for, and RegLens drafts it in two steps: find the obligations, then judge the
gaps.

## Two invented banks with planted gaps

To test this, we need a bank's internal policies, and real banks don't publish theirs. So we wrote
our own for two fictional firms: **Sahyadri Bank Ltd** in India, regulated by the RBI, and
**Northbridge Bank plc** in the UK, regulated by the PRA and the FCA. Between them they have five
short, realistic policies with numbered clauses and an owner. Each file is marked `synthetic: true`,
so nobody mistakes it for a real bank's document. The rules they're tested against are real.

The trick is that the policies were written **with gaps on purpose**, the way real policies lag
behind new rules. A few examples:

| What the new rule requires | What the policy says | Planted answer |
|---|---|---|
| Send rejected complaints to the Ombudsman **within 20 days** (RBI, 2026) | "within **25** days" | partly covered |
| **Don't** publish the Ombudsman's contact details (RBI, 2026) | "name, email and phone shall be displayed on the website" | not covered: it contradicts |
| Keep self-assessment records for **six years** (FCA) | "retained for **three** years" | partly covered |
| The Board approves the self-assessment (FCA) | "The Board shall approve … at least annually" | covered |

Across three target rules there are **41 hand-labelled obligations**: 20 covered, 13 partly covered and
8 not covered. Because we planted the gaps, the right answers are true *by construction*, and that
is what makes the gap judge measurable. It's like a driving examiner's route with hazards placed
deliberately: you know exactly which ones the candidate should spot.

## Step one: obligations

An **obligation** is one thing the firm must, or must not, do. RegLens writes each one in a fixed
shape: the plain sentence, who must act, what they must do, under what condition, by when, which
paragraph it came from, and how severe it is. For example: *"If the Ombudsman's post falls vacant
for reasons beyond the bank's control, the bank must inform the RBI within 10 working days and
appoint a new Ombudsman within three months."*

The LLM reads up to three paragraphs at a time (cheaper than one call each) and returns every
obligation it finds. Two guard rails keep it honest. The prompt excludes definitions and "the RBI
*may*" statements, which oblige the regulator, not the bank. And every obligation must cite one of
the paragraphs it was shown; one pointing anywhere else is dropped. If an older version of the rule
exists, only paragraphs that **changed in substance** are sent, so a moved comma doesn't create
work. It's like turning a dense legal letter into a to-do list, with each item pointing back to its
sentence.

## Step two: gap judgement

**Gap analysis** means comparing what the rules require with what the firm's own policies say, to
find what's missing. For each obligation, RegLens first finds the five most relevant clauses in
*that firm's* policies, using the same hybrid search and reranker from Part 7 on a separate
collection of policy clauses. Then the LLM gives a verdict:

- **covered**: the policy requires what the rule requires, numbers and deadlines included (stricter
  is fine);
- **partly covered**: the topic is there, but a piece is missing, or a number is weaker;
- **not covered**: nothing addresses it, or a clause contradicts it.

Each verdict comes with a one-line reason, the clause labels it relied on, and a confidence. Clause
labels the model invents are thrown away.

The middle verdict matters most. Real gaps are rarely missing topics; they are **weaker numbers**:
25 days instead of 20, three years instead of six. A yes-or-no checker would call those covered.

## Measuring the judge

Given each hand-labelled obligation, the judge told "covered" apart from "needs work" correctly for
**93%** of the 41 cases, and picked the exact three-way label for 78%. On extraction, RegLens found
**63%** of the obligations a human listed, and every one it found was judged genuine: careful, but
it misses some.

> **Try it:** run `uv run poe eval-impact`. It scores obligation extraction and gap judgement
> against the hand-labelled answers, replaying cached model replies.

*Want the details? See `walkthrough/09-change-impact/01-the-firms-and-their-policies.md` to
`03-gap-judgement.md`, `evals/impact_gold.yaml` and `src/reglens/impact/`.*

So far: RegLens turns a new rule into obligations and judges each against the bank's own policy.
But a draft isn't a decision. Next, the workflow that stops and waits for a human.

**Next →** [10.2 A workflow that waits for a human](02-a-workflow-that-waits-for-a-human.md)
