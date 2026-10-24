# 01: Project folder and Git

**Files:** `.gitignore`, `.gitattributes`

## What
We created the `reglens/` folder and turned it into a **Git repository** with
`git init -b main`.

## Why
Git is a time machine for code. Every saved step (a "commit") can be viewed, compared or
undone. In industry nothing exists unless it's in Git: code review, CI and deployments are
all built on it. We commit after every chunk, so the Git history itself tells the story of
this project.

## The two special files

### `.gitignore`: "never pack these"
Think of it as the list of things you never put in a suitcase. We ignore:

| Ignored | Why |
|---|---|
| `.env`, `kaggle.json`, `*.pem` | **Secrets.** Leaked API keys on GitHub get abused within minutes |
| `data/raw/`, `data/processed/` | Datasets are large, and their licences don't allow re-publishing. Scripts re-download them instead |
| `artifacts/`, `mlruns/` | Trained models and experiment logs can be regenerated |
| `.venv/`, caches, `node_modules/` | Machine-specific stuff that tools recreate |
| `*.tfstate` | Terraform state can contain secrets about cloud resources |

### `.gitattributes`: line endings
Windows ends text lines with two invisible characters (CRLF); Linux uses one (LF). Our code
will run in Linux (Docker, CI) but is written on Windows. `* text=auto eol=lf` makes every
file use LF in the repo, so scripts don't break mysteriously inside containers. Binary files
(images, models, PDFs) are marked `binary` so Git never tries to "fix" them.

## How to check
```bash
git status        # shows files Git sees; .env and data/ should never appear
```
