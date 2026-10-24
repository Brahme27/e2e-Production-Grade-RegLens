# 05: What we learned (including what didn't work)

Measuring everything means some ideas lose, and some bugs only show up in the numbers. Here are
four ideas that lost and one evaluation run that exposed three bugs.

## 1. LLM document summaries made retrieval *worse* (ablation row E2)
**Idea:** add a 2-sentence LLM summary of each document to every chunk's context (contextual
retrieval, layer 2). **Result:** recall@10 fell from 0.889 to 0.839 and MRR from 0.841 to 0.733.
**Why (our reading):** every chunk of a document received the *same* summary, which pulled the
chunks of one document closer together and towards generic questions; the summary also took up
part of the ~220 words the reranker reads, pushing out the paragraph's own words.
**Decision:** not shipped. Serving uses structural headers only (row E1). The summaries are
still used where they help: as document overviews for broad "main themes" questions.

## 2. The plan's reranker was too slow for this hardware
`bge-reranker-v2-m3` scored nDCG@10 0.804 vs MiniLM's 0.779 on the same 30 questions, at
**15.8 s median (44 s p95) vs 1.7 s** per question on a laptop CPU. A small gain at 9× the
latency breaks the answer-time budget. **Decision:** MiniLM in production; bge-m3 documented as
the upgrade if a GPU is available (ADR 0004).

## 3. A learned "off-topic" detector was wrong in the costly direction
The first router also learned an `out_of_scope` class. On the golden set it gave real compliance
questions *higher* off-topic scores (0.33–0.63) than "What's the weather in Mumbai?" (0.13), so
it would have **refused 27 legitimate questions**. **Decision:** removed; off-topic and harmful
requests are handled by guardrails and abstention. Router accuracy rose from 0.744 to 0.903.

## 4. The LLM confidently invented one repeal
Asked which older documents a generic RBI repeal clause covered, the model linked the 2025
*Governance* directions to the 2023 *IT Governance* direction, fooled by a shared word. A clearer
prompt didn't change its mind. **Decision:** LLM-proposed edges go through human review
(`configs/supersession_overrides.yaml`, ADR 0003); we reported the raw error instead of tuning
the prompt on one example.

## 5. The first answer evaluation found three bugs the unit tests didn't
Reading the per-question output of the first full run (not just the averages) showed:
- **The judge returned nothing for most answers.** Qwen spent its whole 900-token budget on
  hidden "thinking" and never wrote the JSON verdict; only 7 of ~30 answers were judged. The
  "1.0 faithfulness" average looked perfect only because it covered 7 answers. **Fix:** the
  reasoning setting is now per model in `configs/litellm.yaml` (off for Qwen), and blank
  replies are never cached.
- **The safety rail refused a core compliance question.** "Who must be given overall
  responsibility for anti-money laundering systems?" was refused as harmful, because the rule
  matched the word *laundering*. For a tool whose corpus is a third AML/KYC, that is a serious
  false positive. **Fix:** the rule now needs a *request to do* the act ("how can I…", "help me…")
  rather than the topic, with regression tests for legitimate AML, mule-account and phishing
  questions.
- **5 of 60 answers cited sources as `【1】` instead of `[1]`,** gpt-oss's native style, so the
  verifier marked them uncited. **Fix:** markers are normalised before verification.

The lesson: an average can hide a broken measurement. Always check *how many* items a metric
was computed on, and read some failures by hand.

## The common thread
Each failure was caught by a number, not by intuition, and each time the fix was a **design
decision** (don't ship / use the smaller model / remove the class / add a human), not more prompt
tweaking.
