# 03: Abstention ("I could not find this")

**File:** `src/reglens/generate/answer.py`

## What
RegLens declines to answer in two places:

1. **Before the LLM (free):** if the best reranked passage scores below a threshold, the
   corpus almost certainly doesn't cover the question ("What leverage ratio does the PRA
   require?" when no leverage rules are indexed). We reply immediately, without spending an API call.
2. **By the LLM:** if the passages are related but don't contain the answer, the prompt
   makes the model reply `NOT_FOUND`, which we turn into the same polite message.

## How the threshold is chosen
Not by hand. `uv run poe eval-answers` first **calibrates** it: it runs retrieval on the
golden set's answerable and unanswerable questions, and picks the reranker score that best
separates them (maximum balanced accuracy). The value is saved in
`artifacts/reports/abstention.json` and loaded by the API.

## Why abstention matters more than cleverness
In compliance, a confident wrong answer is worse than no answer: someone may act on it.
The golden set includes 30 unanswerable questions, among them **traps** that sound
real ("What did the PRA's SS3/27 on AI governance require?"; SS3/27 does not exist), and
we report abstention accuracy alongside answer quality.

**Analogy:** a good librarian who says "we don't hold that; try the regulator's site"
instead of handing you the nearest book and hoping.
