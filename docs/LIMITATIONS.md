# Known limitations

RegLens is a portfolio system built on free tiers and a laptop CPU. This page lists what it does
not do, where the numbers could mislead, and what would change before real use.

## Scope and data
- **Curated corpus, not full coverage.** 37 documents (48 versions) chosen around three themes
  (KYC/AML, outsourcing and operational resilience, governance and complaints). A question
  outside them should abstain, and usually does, but a "no answer" means "not in this corpus",
  not "no such rule exists".
- **Parsers are per-source heuristics.** Each regulator's HTML and PDF layout has its own parser.
  A layout change can silently degrade parsing; the CI quality gate (row F against
  `evals/baseline.json`) exists to catch this, but only for questions in the golden set.
- **Hindi text is skipped.** RBI bilingual PDFs are indexed in English only.
- **Synthetic policies.** The two banks' internal policies (`data/policies/`) are invented for
  the change-impact demo, with deliberately planted gaps. Gap-judgement accuracy on real,
  messier policies would be lower.

## Evaluation
- **The golden set was written with an LLM** and validated automatically, plus a smaller
  handwritten set. The builder wrote both, so it may favour the system's own phrasing. A human
  compliance reviewer's pass over a sample would make the numbers more trustworthy.
- **The answer judge is an LLM** (Qwen, a different family from the answering model, to limit
  self-preference). It has not been calibrated against human labels, and it runs on a stratified
  subset (60 questions) because of free-tier limits.
- **Comparison questions are the weakest category** (nDCG@10 0.58 on row F). Answers to
  "compare the FCA and the PRA on X" can miss one side.

## Engineering
- **No user accounts in the console.** The API is protected by an API key that only the console's
  server-side proxy holds, but anyone who can reach the console can use it. A deployment would put
  it behind single sign-on (for example ALB + Cognito/OIDC) and record who approved each gap.
- **Impact runs live in memory while paused.** The LangGraph checkpointer is `InMemorySaver`:
  a run awaiting human review is lost if the API restarts, and two API replicas would not share
  paused runs. Judgements already saved to the database survive. The fix is LangGraph's Postgres
  checkpointer; with `api_desired_count = 1` in Terraform this is a known, documented trade-off.
- **Rate limiting is per process.** Each API replica keeps its own token buckets. Behind several
  replicas the effective limit multiplies; a shared Redis limiter would fix that.
- **Free-tier LLM limits.** About 1,000 requests a day per model. When the limit is hit, the API
  degrades to "here are the relevant passages" instead of failing, but answers stop being
  generated until the quota resets.
- **CPU-sized models.** The reranker is MiniLM-L6 because the stronger bge-reranker-v2-m3 took
  ~16 s per question on this hardware (ADR 0004). With a GPU, that is the first upgrade.

## Not legal advice
RegLens finds and quotes regulatory text with citations. It does not interpret law, and every
gap judgement is a draft for a human reviewer, which is why the workflow pauses for one.
