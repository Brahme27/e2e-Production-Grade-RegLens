# Phase 01: Environment setup ("building the workshop")

Before a carpenter builds furniture, they set up the workshop: a workbench, tools on the
wall, a measuring tape, and safety rules. This phase is our workshop. No regulation logic
yet. We're making sure every later step is **repeatable, checked and safe**.

By the end of this phase:
- anyone can clone the repo and get the *exact* same Python and libraries with one command;
- settings and secrets are handled properly;
- code is automatically checked for bugs, style and types;
- tests run with a coverage gate;
- every commit and every push is checked automatically.

| Chunk | What happens |
|---|---|
| [01-project-folder-and-git.md](01-project-folder-and-git.md) | Create the folder, start version control, decide what never gets committed |
| [02-python-and-uv.md](02-python-and-uv.md) | Pin Python 3.12 and manage libraries with uv |
| [03-project-layout.md](03-project-layout.md) | Why code lives in `src/reglens/` and tests in `tests/` |
| [04-configuration-and-secrets.md](04-configuration-and-secrets.md) | One typed settings object; secrets kept out of code |
| [05-logging.md](05-logging.md) | Logs that machines can search |
| [06-code-quality-tools.md](06-code-quality-tools.md) | ruff, mypy, and the `poe` task runner |
| [07-tests-and-coverage.md](07-tests-and-coverage.md) | Our first tests and the 80% coverage rule |
| [08-pre-commit-hooks.md](08-pre-commit-hooks.md) | Automatic checks before every commit |
| [09-continuous-integration.md](09-continuous-integration.md) | The same checks on GitHub for every push |

## Reproduce this whole phase yourself
```bash
git clone <this repo> && cd reglens
uv sync                        # installs Python 3.12 + everything, exactly as locked
uv run pre-commit install      # turn on the commit-time checks
uv run poe check               # lint + types + tests → should all pass
```
