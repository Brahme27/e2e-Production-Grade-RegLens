[RegLens guide](../README.md) › Part 11: Safety and speed

# 11.2 Faster and visible

In the [last chapter](01-guardrails-and-prompt-injection.md) we put guards around the model. Two
production concerns remain. People ask the same things again and again, in different words, and
each answer costs search time and free quota. And when an answer goes wrong, we need to see
exactly what happened inside. This chapter gives RegLens a memory for answers and a flight recorder.

## Same question, different words

"How often must high-risk customers' KYC be refreshed?" and "What is the periodic updation
frequency for high-risk KYC?" are the same question. A **semantic cache** notices that. It stores
each finished answer together with the question's embedding (its meaning coordinates from chapter
6.2). When a new question arrives whose embedding is at least 95% similar to a stored one, RegLens
returns the stored answer in milliseconds: no search, no reranking, no LLM call.

This is a different notebook from the one in chapter 2.3. That one matches *exact requests to the
model*, byte for byte. This one matches the *meaning of users' questions*. Think of the FAQ sheet
at a help desk: if someone asks a question already answered today, in any wording, you hand them
the same sheet.

But time matters here too. A stored answer is reused only if the match also has:

- the **same "as of" date**, because an answer about 2025 is not an answer about today;
- the **same regulator filters**;
- the **same index and prompt version**, so re-indexing or a new prompt retires old answers.

If a colleague asks Meera's question in other words, for the same date, the answer is instant. If
they ask it without a date, it's a different question about different rules, and it's answered
fresh. Refusals and "I could not find this" replies are never stored, and every entry expires after
seven days.

In Docker and the cloud, the cache lives in **Redis**, a very fast in-memory store that every copy
of the API can share. It's capped at 64 MB and, when full, drops the entries used least recently.
On a laptop and in tests, a small store inside the program does the same job.

## A flight recorder for every question

**Observability** means being able to see inside a running system from what it records. For
RegLens the key tool is **tracing**: every question produces a **trace**, one record with a **span**
for each step, holding that step's input, output and duration.

```
ask "How often must high-risk KYC be updated?"          2,940 ms
 ├─ guard      verdict=allow                               180 ms
 ├─ cache      hit=false                                    55 ms
 ├─ retrieve   route=lookup, 8 hits                      1,620 ms
 └─ generate   model=reasoning-large, abstained=false    1,085 ms
```

Traces always go to a local file, one line per question. When keys are set, they also go to
**Langfuse**, an open-source platform built for watching LLM applications, where you can browse the
step tree and timings. The thumbs-up and thumbs-down buttons in the console attach a score to that
exact trace, so a thumbs-down can be opened next to what was retrieved and generated.

Three design choices keep it out of the way. We send traces with a few plain web requests rather
than a full software kit, which keeps the image lean. Sending happens in the background, so if
Langfuse is down, the user notices nothing. And we use Langfuse's free cloud tier, because hosting
it ourselves needs four extra services, too much for an 8 GB laptop already running RegLens.

## One path for users and for tests

All of these steps live in one service that runs them in order:

guard → semantic cache → search → context rail → answer (streamed) → verify → cache and trace.

The API uses it, and so does the evaluation in Part 9. That's deliberate. If the evaluation called
search and generation directly, it would skip the guards, the cache and the context rail, and
measure a system nobody uses. Here, the numbers in the README come from **exactly the code path a
user hits**.

The service also decides what happens when something fails. If the guard says no, nothing else
runs and no tokens are spent. If the LLM provider is down or out of quota, Meera still gets the
retrieved paragraphs, with a note that the answer service is unavailable, so she can read the
sources herself. If Langfuse is unreachable, the problem is logged and the user notices nothing.

*Want the details? See `walkthrough/10-safety-speed-observability/02-semantic-cache.md`,
`03-tracing.md`, `04-the-qa-service.md` and `src/reglens/qa.py`.*

So far: repeat questions are instant, every question leaves a step-by-step record, and users and
tests share one path. Next, the front door that other programs knock on, and the console Meera uses.

**Next →** [12.1 The API and the console](../12-the-api-and-console/01-the-api-and-the-console.md)
