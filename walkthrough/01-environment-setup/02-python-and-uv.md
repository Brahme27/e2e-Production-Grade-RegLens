# 02: Python 3.12 and uv

**Files:** `.python-version`, `pyproject.toml`, `uv.lock`

## What
- `.python-version` says **3.12**.
- `pyproject.toml` is the project's ID card: name, version, which libraries it needs, and
  settings for every tool.
- `uv.lock` records the **exact** version of every library (and of their libraries too).

## Why
"It works on my machine" is the oldest problem in software. If you install `qdrant-client` today and
your colleague installs it next month, you may get different versions and different results.
A **lock file** means everyone, including CI and Docker, gets *identical* installs.

**Why Python 3.12 when the laptop has 3.14?** Brand-new Python versions take months to be
supported by heavy AI libraries (ONNX Runtime, LiteLLM, LangGraph, Qdrant client). 3.12 is the mature,
fully supported choice in 2026. uv downloads it automatically, so we never touch the
system Python.

## Why uv (and not pip / conda / poetry)?
| Need | Old way | uv |
|---|---|---|
| Install a Python version | pyenv | built in |
| Make an isolated environment | venv | built in (`.venv/`) |
| Install libraries | pip | built in, 10–100× faster |
| Lock exact versions | pip-tools / poetry | built in (`uv.lock`) |

One tool, very fast, and now the industry default for new Python projects.

## What's inside `pyproject.toml`
```toml
[project]
requires-python = ">=3.12,<3.13"     # refuse to run on other versions
dependencies = ["pydantic>=2.8", "pydantic-settings>=2.4", "structlog>=24.4"]

[dependency-groups]
dev = ["pytest", "pytest-cov", "hypothesis", "ruff", "mypy", "pre-commit", "poethepoet"]
```
- **dependencies** are what the app needs to *run*.
- **dev** dependencies are only for *building and checking* (tests, linters). They never ship
  in the production Docker image, which keeps it smaller and safer.
- We add libraries **phase by phase**, as they become needed, instead of all upfront. That
  keeps every step understandable.

The rest of the file holds settings for ruff, mypy, pytest, coverage and poe. Those are
explained in chunks 06–07.

## How to run
```bash
uv sync              # creates .venv/ with Python 3.12 and installs everything from uv.lock
uv run python --version
```
## What you should see
`Python 3.12.x`. The first `uv sync` downloads Python (about 30 s); later runs take under a second.
