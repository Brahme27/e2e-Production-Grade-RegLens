# 08: Pre-commit hooks

**File:** `.pre-commit-config.yaml`

## What
A list of checks that run **automatically every time you type `git commit`**. If any check
fails, the commit is blocked until you fix it.

| Hook | Catches |
|---|---|
| trailing-whitespace, end-of-file-fixer | Messy whitespace (auto-fixed) |
| check-yaml, check-toml | Broken config files |
| check-added-large-files (>1 MB) | Someone accidentally committing a dataset or model |
| detect-private-key | Private keys pasted into files |
| **gitleaks** | API keys, tokens and passwords (it knows hundreds of key formats, Groq and AWS included) |
| ruff format + ruff lint | Style and bug patterns (auto-fixed where possible) |
| mypy | Type errors |

## Why
Checks you have to remember to run eventually get skipped. Hooks make the right thing
automatic. Most importantly, **gitleaks stops secrets before they enter Git history**.
Once a secret is pushed it's effectively public, even if you delete it later.

## Design choice: "local" hooks for ruff and mypy
The ruff and mypy hooks run `uv run ruff …` / `uv run mypy …`, which use **the exact
versions locked in `uv.lock`**. So your editor, the commit hook and CI all agree, with no
"passes locally, fails in CI" surprises.

## How to run
```bash
uv run pre-commit install           # once per clone: wires the hooks into .git/
uv run pre-commit run --all-files   # run every hook on every file manually
```
## What you should see
Ten lines ending in `Passed`.
