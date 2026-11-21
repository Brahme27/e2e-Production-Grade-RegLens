[RegLens guide](../README.md) › Part 9: Proving it with numbers

# 9.3 The LLM judge

In the [last chapter](02-the-ablation.md) the ablation proved which search techniques help. But
retrieval scores only tell us that the right paragraphs were *found*. They can't tell us whether
the *answer* says what those paragraphs say. A model handed perfect sources can still twist them.
To check the answers, we need an examiner.

## A second examiner

Checking hundreds of sentences by hand doesn't scale, so we use a technique called **LLM-as-judge**:
a second model reads each answer next to its numbered sources and labels every sentence. Think of
a second examiner marking an exam script. They don't write the answer; they check each claim
against the textbook page the student referenced.

For each sentence, the judge answers:

- **Supported?** Do the sources (any of them) state or directly imply it? The share of supported
  sentences is the answer's **faithfulness**.
- **Does the cited source support it?** A true sentence that cites the wrong paragraph still fails,
  because a compliance officer *will* click that citation. This gives **citation precision**.
- **Relevant?** A score from 1 to 5 for whether the answer addresses what was asked.

The answers come from gpt-oss. The judge is **Qwen**, from a different model family. Models tend to
rate text written in their own style more kindly, so a different family reduces that bias. It
doesn't remove it, and the judge hasn't been checked against human labels yet. We say so in the
project's limitations page.

## Some scores need no judge at all

Several of the most important checks are simple counts:

- **Abstention**: on unanswerable questions, did RegLens decline?
- **Refusal**: on adversarial prompts, did it refuse?
- **False abstention**: on answerable questions, did it wrongly give up?
- **Temporal correctness**: was every cited paragraph actually in force on the question's date?

## Two pipelines, same questions

The free tier can't afford to judge all 195 questions, so we used a **stratified** subset of 60:
a sample that keeps a fair mix of every question kind. Each question ran through two systems: the
final RegLens, and a naive version using row A's search with no guardrails and no abstention.

| Measure | Naive | RegLens |
|---|---|---|
| Faithfulness (sentences supported) | 0.72 | **0.87** |
| Citation precision | 0.68 | **0.84** |
| Every citation in force on the date | 0.86 | **1.00** |
| Declined unanswerable questions | not tested | **100%** |
| Refused adversarial prompts | not tested | **90%** |
| Wrongly declined answerable questions | 0.26 | 0.18 |

The story the table tells: **better retrieval makes the same model more honest**. Given the right,
in-force paragraphs, gpt-oss invents less and cites better. And the temporal row is the compliance
number: the naive system cited a repealed or not-yet-in-force paragraph in about one answer in
seven. RegLens never did.

A typical answer takes **1.4 seconds** from question to final word, and 95% of answers finish
within **2.2 seconds**, on a laptop processor plus the hosted model. One honest footnote: the naive
run hit Groq's daily token limit while being judged, so only 19 of its answers were scored. Its
numbers point clearly in one direction, but they are less precise than RegLens's.

> **A bump on the road:** the very first judged run showed a perfect faithfulness of 1.0. It looked
> wonderful, and it was wrong. Reading the per-question output, we found the judge had returned
> *nothing* for most answers: Qwen spent its whole token budget on hidden "thinking" and never wrote
> its verdict. The perfect score covered only 7 of about 30 answers. We switched Qwen's thinking
> off in the model config, and made sure blank replies are never saved in the notebook. The lesson:
> an average can hide a broken measurement. Always check *how many* items a score was computed on,
> and read some failures by hand.

> **Try it:** run `uv run poe eval-answers`. It first calibrates the abstention threshold from
> chapter 8.2, then runs both pipelines and the judge. Every LLM call is cached, so a second run
> costs nothing and prints the same numbers.

*Want the details? See `walkthrough/08-evaluation/04-the-llm-judge.md`, `05-what-we-learned.md`
and `docs/LIMITATIONS.md`.*

So far: we've proved that RegLens finds the right paragraphs, writes faithful answers, cites
correctly, never cites out-of-date rules, and declines when it should, and we know its weak spots.
Next, Meera's second problem: a new rule has arrived, so what must the bank change?

**Next →** [10.1 From a new rule to a to-do list](../10-change-impact/01-from-a-new-rule-to-a-to-do-list.md)
