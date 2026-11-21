[RegLens guide](../README.md) › Part 2: Setting up the workshop

# 2.3 Settings, secrets and logs

In the [last chapter](02-python-uv-and-the-lock-file.md) we gave every machine the same Python
and libraries. Now three quieter questions. How does the program know *where* it is running? How
does it get its one secret key, and can it work without it? And when something happens, how do
we find out later what it was?

## The same code, everywhere

RegLens runs in several places. On the laptop, the database is a single file and the search index
is a folder. Inside Docker, both are real servers with their own addresses. In the cloud, the
addresses change again. If those details were written into the code, we'd need a different copy of
the code for every place. Instead we follow a rule most modern services follow: **the code stays
the same, and only the settings change.**

Settings arrive from outside through **environment variables**: named values the operating
system hands a program when it starts, like a note slipped under the door saying "tonight, the
log level is DEBUG".

All of RegLens's settings live in one small class built with **pydantic-settings**: the
environment name, the log level, folder paths, the database and search addresses, the polite
delay between downloads, even the names of the search models. Each has a type and a safe default.
pydantic-settings reads the variables, converts them, and checks them. Set the log level to
`LOUD` and the program refuses to start and says why, instead of misbehaving an hour later. We
call that **failing fast**. Writing this by hand with Python's `os.environ` would mean fiddly
conversion code and no checks at all.

Every variable carries the prefix `REGLENS_`, for example `REGLENS_LOG_LEVEL=DEBUG`, so our
settings never clash with another program's `LOG_LEVEL`.

## Secrets never live in code

A **secret** is anything that grants access, such as a password or an **API key** (a password one
program shows when it calls another program's service). Secrets **never appear in the code and
never enter Git.** On a laptop they live in a file called `.env`, which `.gitignore` keeps out.
In the cloud they live in a proper secret store. A harmless copy called `.env.example` is
committed, showing the variable names with no real values. Keys are stored in a special type that
hides itself: print the settings and the key shows as `**********`, and a test checks it stays
that way.

## The one key, and a notebook that makes it optional

RegLens needs one secret to talk to an LLM: a free key from **Groq**, a service that runs open
models very fast. It goes after `REGLENS_GROQ_API_KEY=` in `.env`. The free tier is small: about
1,000 requests a day and 8,000 **tokens** a minute for each model (a token is a piece of a word,
the unit models read and write in).

So every LLM call in the project goes through one client that keeps a **notebook**. Before calling
Groq, it makes a fingerprint of the exact request (which model, which messages, which settings)
and looks in `cache/llm/`. If the answer is there, it returns it instantly. If not, it calls the
model and writes the answer down. A **cache** is exactly this: a store of results kept so you don't
pay for them twice.

The notebook matters for three reasons:

- **Cost.** Re-running an evaluation never spends the quota twice. Building and evaluating the
  whole project took 486 LLM calls on the free tier, and cost nothing.
- **Speed.** A saved answer comes back in milliseconds, not seconds.
- **Reproducible evaluation.** An LLM can word its answer differently each time. Replaying the
  saved answer gives the same result every run, so our quality numbers don't wobble.

Because `cache/llm/` is committed to Git, a fresh copy of the project, the automated checks and
the Docker demo all replay every answer the results were built from, **with no key at all**. A
usage log also records each real call's tokens and purpose, which is how the results page can say
exactly what each feature cost.

> **Try it:** copy `.env.example` to `.env` (`cp .env.example .env` on Mac or Linux, `copy` on
> Windows) and paste your free Groq key after `REGLENS_GROQ_API_KEY=`. Leave it empty if you like:
> cached answers replay without it.

## A diary you can search

A program's diary is its **log**. `print("answered")` is fine for a script and useless for a
service. When someone asks "why did yesterday's 3:14 pm answer cite that paragraph?", you need to
search logs by field. That only works if logs are **structured**: named fields, not sentences.

We use **structlog**, the most popular structured-logging library for Python. On the laptop it
prints friendly coloured lines. In Docker and the cloud, `REGLENS_LOG_JSON=true` switches it to
**JSON**, a simple text format of labelled fields (like a form with named boxes), one entry per
line, which log tools can index and search. Every line gets a timestamp and a
level such as `info` or `error`. (The file is called `log.py`, not `logging.py`, so it never gets
confused with Python's own `logging` module.)

*Want the details? See `walkthrough/01-environment-setup/04-configuration-and-secrets.md`,
`05-logging.md` and `walkthrough/04-time-and-supersession/04-cached-llm-client.md`.*

So far: the project reads its settings from outside, keeps its secret safe, replays model answers
from a notebook, and keeps a searchable diary. Next, the safety nets that catch our mistakes.

**Next →** [2.4 Safety nets](04-safety-nets.md)
