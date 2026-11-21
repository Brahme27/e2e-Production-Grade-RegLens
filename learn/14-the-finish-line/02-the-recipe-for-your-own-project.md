[RegLens guide](../README.md) › Part 14: The finish line

# 14.2 The recipe for your own project

In the [last chapter](01-results-and-weak-spots.md) we looked honestly at what RegLens achieves and
where it falls short. To finish, here is the recipe we followed, written so it fits any RAG or LLM
system you might build, such as a policy assistant or a research tool over your own documents. Adapt
it, and skip what you don't need.

## 1. Start with the problem and one example

- Write down the questions real users ask, in their words.
- Pick **one running example** and keep it in front of you, the way Meera's question guided us.
- Decide what a wrong answer costs. In compliance, a confident wrong answer is worse than none.

## 2. Set up the workshop before anything clever

- Git from day one, a `src/` layout, code organised by job.
- uv and a lock file, so every machine installs the same thing.
- Settings from environment variables, secrets in `.env`, structured logs.
- ruff, mypy, pytest with a coverage floor, pre-commit with a secret scanner, CI on every change, and
  short task names.
- **Put every LLM call behind one client with a cache** from the start: it saves quota, makes
  results reproducible, and lets CI run without a key.

## 3. Collect a small, honest corpus

- Start curated: dozens of the right documents beat thousands of random ones.
- If your facts change over time, **include the old versions on purpose**.
- Keep the source list in a config file, crawl politely (robots.txt, delays, retries, saved copies),
  and record a fingerprint of every download.

## 4. Parse into the unit people cite

- Find your documents' natural unit (paragraph, clause, FAQ entry) and make every parser produce
  it, with its headings and dates.
- Prefer light, rule-based parsers for clean documents; test them on tiny, awkward examples.

## 5. Model time if your facts change

- Give every version a valid-from and valid-to date. Find replacements with rules first, an LLM for
  the vague cases, and a human to approve.

## 6. Index for meaning and exact words

- Chunks that follow your document's structure, each with a context header and full metadata.
- A dense vector for meaning and a sparse one for exact words, from models sized for your hardware.
- A vector database that filters inside the search, behind an alias so re-indexing never shows a
  half-built index.

## 7. Retrieve carefully

- Read the exact parts of a question (dates, names) with rules, not an LLM.
- Route questions by kind if kinds need different handling.
- Hybrid search merged with RRF, filters inside the search, then a reranker on the shortlist.
- Put all of it behind one configurable object, so experiments run the production code.

## 8. Answer with receipts

- Numbered sources in the prompt; short markers in the answer; real citations built by your code.
- A "not found" contract with the model, a verification check on every answer, and an abstention
  threshold calibrated on data.
- Stream the answer, and give the prompt a version number.

## 9. Prove it with numbers

- Build a golden set with answer keys, including questions that **should** be declined or refused.
- Score retrieval without an LLM (recall, nDCG, MRR, plus a metric for your own worst failure).
- Run an **ablation**: add one technique at a time, keep only what helps, and report what didn't.
- Judge answers with a model from a different family, and read the failures by hand.
- Save the production numbers as a baseline and let CI fail the build if they drop.

## 10. Add a workflow only where it earns its place

- Use a graph framework such as LangGraph only where you need saved state or a pause, and let a
  human decide wherever a mistake is costly.

## 11. Guard it, speed it up, and watch it

- Input rails, an injection classifier and a rail on retrieved text. Test for false alarms too.
- A semantic cache keyed by meaning **and** by date, filters and versions.
- A trace for every request, and one service path shared by users and evaluation.

## 12. Serve it, containerise it, write the cloud down

- An API with keys, rate limits and validation; a console behind a server-side proxy; browser tests.
- Lean images, compose with a safe start order, a smoke test. Run the real stack early: it finds
  what unit tests can't.
- Terraform for the cloud, secrets kept out of its records, validation in CI, and a budget alarm.

## 13. Write the results honestly

- Generate the results page from code, never by hand.
- Publish the limitations next to the results, and record big decisions as short ADRs.

It looks long written out, but you've seen every step working, one small chapter at a time. Start
with step 1, and let the numbers tell you what to keep.

*Want the details? See the full build log in `walkthrough/README.md`.*

So far: you have followed one question from an empty folder to a measured, cloud-ready system, and
you hold the recipe to build your own. Thank you for reading.

**Next →** [Back to the guide's front page](../README.md)
