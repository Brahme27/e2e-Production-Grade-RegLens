[RegLens guide](../README.md) › Part 2: Setting up the workshop

# 2.4 Safety nets

In the [last chapter](03-settings-secrets-and-logs.md) our workshop gained settings, a safe place
for the key, a notebook of model answers and a searchable diary. One thing is missing before we
build anything real: a way to catch mistakes *automatically*. People get tired and forget things.
Checks that run by themselves don't. In this chapter we put up five safety nets.

## Net 1: ruff, the spell-checker for code

**ruff** reads the code without running it and flags problems: an import nobody uses, a name that
was never defined, a pattern that often hides a bug, a password typed straight into the code. It
also formats the code the same way everywhere, which ends arguments about style. Older projects
needed four tools for this (flake8, black, isort and bandit). ruff replaces all four and runs
about a hundred times faster.

## Net 2: mypy, checking the types

Python lets you pass anything anywhere. **Type hints** are short labels in the code saying what
kind of value goes where: "this is a date", "this is text", "this might be missing". **mypy** reads
those labels and complains when something doesn't fit, before the code ever runs. We switch on
its *strict* mode, so every function must say what it takes and what it returns.

Why does this matter in a compliance tool? Imagine mixing up "the date a rule was issued" with
"the date it took effect", or passing nothing where a date is needed. Nothing crashes. RegLens
quietly cites the wrong version of a rule. mypy catches these mix-ups early.

## Net 3: tests, and the 80% rule

A **test** is a small program that checks a piece of our code does what it should. We use
**pytest**, the standard tool in Python. Each test reads in three steps: *arrange* the situation,
*act* by calling the code, and *assert* that the result is what we expected. It's like checking a
recipe: set out the ingredients, cook, taste.

RegLens's tests have one more rule: **no internet and no API keys**. A test can't depend on a
regulator's website being up or on Groq's free quota. So tests use stand-ins: a pretend website
that answers instantly, a fake language model, and an in-memory search index. Every chunk of work
ships with its own tests.

**Coverage** measures the percentage of code lines the tests actually ran. If it drops below 80%,
the test run fails. That stops the familiar promise "I'll write tests later", which usually means
never. By the end, RegLens has **162 tests and 91% coverage**.

## Net 4: pre-commit, checks before every save

Checks you have to remember get skipped. **pre-commit** runs them for you: every time you type
`git commit`, a list of checks runs first, and if one fails, the commit is blocked until you fix
it. Ours tidies whitespace, checks config files, refuses files over 1 MB (an accidental download
or model), spots private keys, and runs ruff and mypy using the exact versions in `uv.lock`, so
your editor, the hook and the build server always agree.

The most important hook is **gitleaks**, which recognises hundreds of kinds of keys, Groq's
included. Once a secret reaches GitHub it is effectively public, even if you delete it later.
gitleaks stops it before it enters Git history at all.

## Net 5: CI, the neutral referee

Hooks run on *your* laptop, and a hurried person can skip them. **Continuous integration (CI)**
can't be skipped. Whenever code lands on the project's main line on GitHub,
or a change is proposed for review there, **GitHub Actions** starts a fresh, clean Linux
machine, installs exactly what `uv.lock` says (and fails if the lock file is out of date), then
runs the lint, format check, type check and tests. A green tick or a red cross appears next to the
change. In most companies, nothing can be merged until CI is green.

Here the notebook from chapter 2.3 pays off again: CI has no Groq key, yet every test that involves
the model passes, because the answers replay from the committed cache. Later parts extend CI to
build the console, validate the cloud files, and once a week rebuild the whole system from the
regulators' websites.

## One name for every command: poe

All these tools have long commands. **poe** (short for poethepoet) gives each one a short name,
written once in `pyproject.toml`: `poe lint`, `poe typecheck`, `poe test`, and `poe check`, which
runs all three in the same order CI does. Why not `make`, the classic tool for this? Because
`make` is missing on Windows, while poe is a Python package uv installs like any other, so the same
command works on every laptop.

> **Try it:** run `uv run poe check`. You'll see ruff report that all checks passed, mypy report no
> issues, and pytest print the number of passing tests and the total coverage. Run `uv run poe` on
> its own to list every task the project offers.

*Want the details? See `walkthrough/01-environment-setup/06-code-quality-tools.md` to
`09-continuous-integration.md`.*

So far: our workshop is ready, with a time machine, a reproducible Python setup, safe settings, a
notebook of answers and five safety nets. Now the real work begins. In Part 3 we collect the
rulebooks.

**Next →** [3.1 Collecting the rulebooks, politely](../03-the-corpus/01-collecting-the-rulebooks.md)
