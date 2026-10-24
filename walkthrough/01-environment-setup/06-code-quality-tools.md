# 06: Code-quality tools: ruff, mypy and poe

**Settings live in:** `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`, `[tool.poe.tasks]`)

## ruff: the spell-checker for code
**What:** reads the code without running it and flags problems: unused imports, likely
bugs, insecure patterns (e.g. hard-coded passwords) and messy formatting. `ruff format`
also auto-formats the code.

**Why:** it catches whole categories of bugs in milliseconds, and it ends style arguments in
code review. The formatter decides.

**What we switched on:** `E/W` (style), `F` (real errors, such as undefined names), `I` (import
order), `B` (common bug patterns), `UP` (modern Python syntax), `S` (security, the bandit
rules), `N` (naming), `SIM` (simpler code), `RUF` and `PL` (pylint-style checks). Tests may
use `assert` and literal numbers, so those two rules are relaxed for `tests/`.

**Why ruff over flake8 + black + isort + bandit?** One tool replaces four, and it is about 100× faster.

## mypy: checking the types
**What:** Python lets you pass anything anywhere. mypy reads type hints (`def as_of_filter(day: date) -> Filter`)
and complains if, say, text is passed where a number is expected. `strict = true` means
every function must declare its types.

**Why:** in a compliance tool, mixing up "the date a rule was issued" and "the date it took
effect", or passing `None` where a date is needed, silently cites the wrong version of a rule. mypy catches
these before the code ever runs. The `pydantic.mypy` plugin teaches mypy about our
settings and data models.

## poe: one name for every command
**What:** short task names defined in `pyproject.toml`:

| Command | Runs |
|---|---|
| `uv run poe format` | auto-format code |
| `uv run poe lint` | ruff checks |
| `uv run poe typecheck` | mypy |
| `uv run poe test` | pytest with coverage |
| `uv run poe check` | lint → typecheck → test (exactly what CI runs) |

**Why poe and not `make`?** `make` is standard on Linux and Mac but missing on Windows.
poethepoet is a Python package installed by uv, so the same commands work on every OS with
nothing extra to install. Run `uv run poe` with no task name to list all tasks.

## What you should see
```
$ uv run poe check
Poe => ruff check src tests      All checks passed!
Poe => mypy src                  Success: no issues found
Poe => pytest                    5 passed ... Total coverage: 100.00%
```
