# 09: Continuous integration (GitHub Actions)

**File:** `.github/workflows/ci.yml`

## What
When the repo is on GitHub, every push and every pull request starts a fresh Linux machine
that:
1. checks out the code,
2. installs uv,
3. runs `uv sync --locked` (it **fails** if `uv.lock` is out of date with `pyproject.toml`),
4. runs lint → format check → type check → tests with the 80% coverage gate.

A green tick ✅ or red cross ❌ then appears next to the commit.

## Why
Pre-commit hooks run on *your* laptop and can be skipped (`git commit --no-verify`). CI runs
on a **clean, neutral machine** and can't be skipped. It's the final referee. In companies,
a pull request can't be merged until CI is green.

It also proves the project works from scratch on Linux, which is the same OS as our
Docker images and the cloud.

## Details worth knowing
- `concurrency: cancel-in-progress` means that if you push twice quickly, the older run is
  cancelled. This saves CI minutes.
- `enable-cache: true` caches downloaded libraries between runs, so CI takes seconds, not minutes.
- Later phases extend this file to build Docker images, scan them for vulnerabilities, lint
  Helm charts and run `terraform validate`.

## How to see it working
Push the repo to GitHub and open the **Actions** tab.
