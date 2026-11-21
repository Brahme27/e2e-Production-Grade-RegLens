[RegLens guide](../README.md) › Part 2: Setting up the workshop

# 2.2 Python, uv and the lock file

In the [last chapter](01-a-home-for-the-project.md) we made a folder, started Git and chose a
layout. Now we need Python and the libraries RegLens depends on. This sounds like the easiest
step. In practice it is where many projects quietly go wrong, so it's worth understanding
properly.

## "It works on my machine"

This is the oldest complaint in software. You install a library today, a colleague installs it
next month, and you get different versions. The code behaves differently, and nobody knows why.
The same thing happens between your laptop, the automated build server and the Docker container
that runs in production. In an AI project the risk is higher still: a small change in a search
library can quietly change which paragraphs come back, and every quality number moves with it.

We solve it with two ideas: a separate environment for each project, and a lock file.

## A separate environment for each project

A **virtual environment** is a private copy of Python, with its own set of installed libraries,
that belongs to one project only. Think of a tiffin box with separate compartments: the dal
doesn't leak into the rice. Without it, every project on your laptop shares one pile of
libraries, and upgrading one for project A can quietly break project B.

Ours lives in a hidden folder called `.venv/` inside the project. Git ignores it, because any
machine can rebuild it in seconds.

## The ID card and the lock file

Two files describe what the project needs.

**`pyproject.toml`** is the project's ID card. It holds the name and version, the Python version
we accept, the libraries we depend on, and the settings for every tool. RegLens sorts its
libraries into three groups, and the split is worth noticing:

- **Runtime**: what the running service needs: the web framework, the database and search
  clients, the HTML and PDF readers, the small search models, the LLM caller and the workflow
  library. Notice what is *missing*: there is no heavy deep-learning framework at all, because
  our models are small enough to run without one.
- **ml**: what we need only for offline training. Here that is one library, scikit-learn, used
  to train the little question router in Part 7. It never ships inside the production image.
- **dev**: what we need to *build and check* the code: the test runner, the coverage tool, the
  linter, the type checker, the commit hooks and the task runner.

Why split them? A smaller production image starts faster, downloads faster, and has fewer
libraries that could contain a security hole. Training tools have no business in a service that
only needs to answer questions.

**`uv.lock`** is the lock file. It records the *exact* version of every library, and of every
library those libraries depend on. If `pyproject.toml` is a shopping list that says "rice", the
lock file says "this brand, this variety, this pack size". Everyone who installs from it, whether
a teammate, the build server or Docker, gets an identical setup.

## One tool instead of four: uv

**uv** is the tool that does all of this. Not long ago you needed several tools: one to install
Python versions, one to make virtual environments, one to install libraries, and another to lock
versions. uv does all four, and it is 10 to 100 times faster than the classic installer, pip. It
has quickly become the default choice for new Python projects. The alternatives (pip with venv,
conda, or Poetry) all work, but they either need several tools glued together or are noticeably
slower.

## Python 3.12, even though newer versions exist

Brand-new Python versions take months to be supported by heavy AI libraries. ONNX Runtime (which
runs our search models), LiteLLM, LangGraph and the Qdrant client all need to publish builds for
each new version. Python 3.12 is the mature choice that every library we need supports, and
`pyproject.toml` refuses any other version. The project also pins it in a tiny file called
`.python-version`, and uv downloads that exact Python automatically. We never touch the Python
installed on the laptop itself.

> **Try it:** run `uv sync`. The first time, uv downloads Python 3.12 (about 30 seconds) and then
> installs everything listed in `uv.lock`. Run it again and it finishes in under a second, because
> nothing has changed.

From now on you'll see `uv run` at the front of almost every command in this guide. It means "run
this inside the project's own environment", so you never have to activate anything by hand.

## Adding libraries as we go

We didn't list every library on day one. Each part of this guide adds only what it needs: the
PDF reader arrives with parsing, the vector database client with indexing, the workflow library
with change impact. It keeps every step small enough to understand, and when something breaks,
you know which change caused it.

*Want the details? See `walkthrough/01-environment-setup/02-python-and-uv.md`.*

So far: every machine can now build exactly the same Python setup. Next, we teach the project to
read its settings and secrets from outside the code, meet the one key it needs, and give it a
proper diary.

**Next →** [2.3 Settings, secrets and logs](03-settings-secrets-and-logs.md)
