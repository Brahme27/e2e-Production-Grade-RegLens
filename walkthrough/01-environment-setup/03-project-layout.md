# 03: Project layout

## What
```
reglens/
├── src/reglens/      ← the actual application code (an installable Python package)
├── tests/unit/         ← tests that check the code
├── walkthrough/        ← this story
├── pyproject.toml      ← project ID card + tool settings
└── uv.lock             ← exact versions
```
Later phases add `data/`, `artifacts/`, `frontend/`, `deploy/` and `infra/`.

## Why a `src/` folder?
If code sits at the top level, Python can import it *by accident* from the current folder,
so tests might pass on your machine but the installed package is broken. With the **src
layout**, tests can only import the package the way users and Docker will: as an installed
package. It's a small rule that prevents a whole class of "works locally, fails in
production" bugs.

## Why organise by *domain*, not by type?
As we build, `src/reglens/` will grow like this:
```
data/  features/  models/  fairness/  causal/  ecl/  pricing/  decision/  letters/  api/
```
Each folder is a **business capability**, not a technical category like "utils" or
"classes". When the fairness rules change you open `fairness/`, and everything about it is
in one place. This is how large codebases stay navigable.

## Analogy
A restaurant kitchen has stations (grill, pastry, salad), not "all knives here, all pans
there". Each station has what it needs for its job.
