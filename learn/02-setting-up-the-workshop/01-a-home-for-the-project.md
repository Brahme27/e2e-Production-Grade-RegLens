[RegLens guide](../README.md) › Part 2: Setting up the workshop

# 2.1 A home for the project

In [Part 1](../01-the-idea/03-the-toolbox.md) we understood the problem, followed Meera's question
and opened the toolbox. Now we start building, and we start where every real project starts: with
an empty folder. This part is like setting up a workshop before making furniture. It isn't
glamorous, but every later step stands on it. If you've read the CrediSure guide, this part will
feel familiar, because every project in this portfolio starts from the same workshop. We still
explain everything here, so this guide stands on its own.

## A folder and a time machine

We create a folder called `reglens` and turn it into a **Git repository**. Git is a time machine
for code. Each time you save a meaningful step, you make a **commit**: a snapshot with a short
message such as "add the polite fetcher". Later you can look at any snapshot, compare two of them,
or undo a change that went wrong.

Why bother on day one? Because in industry, nothing exists unless it is in Git. Code review,
automated checks and deployments are all built on it. We make one commit per small chunk of work,
so the history itself tells the story of how RegLens was built. **GitHub** is a website that hosts
Git repositories, so others can see them and automated checks can run on every change.

> **Try it:** inside the project folder, run `git log --oneline` to see the history, one line per
> commit, newest first. Then run `git status`: it lists files that changed since the last commit.

## Two small files that prevent big accidents

The first file is `.gitignore`, the list of things you never pack in a suitcase. Git pretends
these files don't exist:

- **Secrets**, like the `.env` file that holds API keys. A key pushed to GitHub by mistake can be
  found and abused by bots within minutes.
- **Downloaded documents.** The raw web pages and PDFs belong to the regulators, and a script can
  fetch them again on any machine.
- **Things a tool can rebuild**: search indexes, trained files, the Python environment, caches,
  and cloud state files (which can contain secrets about cloud resources).

Notice one folder that is deliberately *not* on the list: `cache/llm/`, where every answer the
language model ever gave us is stored. We'll see in chapter 2.3 why committing it is so useful.

The second file is `.gitattributes`, and it solves a strangely common problem. Windows ends each
line of text with two invisible characters, while Linux uses one. We write code on Windows, but
it runs on Linux inside Docker and on the build servers. Without this file, scripts can break
inside containers for no visible reason. One line tells Git to store every text file the Linux
way, and to leave images, models and PDFs alone.

## A tidy layout

Next, we decide where things go. At the top level, the project starts like this:

```
reglens/
├── src/reglens/   ← the application code, as an installable Python package
├── tests/         ← automated tests that check the code
├── configs/       ← the document list, model names, the test firms
├── evals/         ← test questions and their answer keys
├── pyproject.toml ← the project's ID card and tool settings
└── uv.lock        ← the exact version of every library
```

Later parts add more neighbours: `data/` for downloaded and parsed documents, `artifacts/` for
indexes and reports, `cache/` for saved model answers, `docs/` for results, `frontend/` for the web
console, `deploy/` for monitoring files and `infra/` for the cloud setup.

### The code lives inside `src/`

It looks like an extra folder for no reason, but it prevents a sneaky bug. If the code sat at the
top level, Python could import it straight from whatever folder you happen to be in, and your tests
could pass even if the *installed* package were broken. With the **src layout**, tests can only use
the code the way Docker and real users will: as an installed package.

### Organised by job, not by type

Inside `src/reglens/`, the code is grouped by what it does for the business: `corpus/` downloads
documents, `parse/` reads them, `temporal/` works out dates, `index/` makes them searchable,
`retrieve/` finds paragraphs, `generate/` writes answers, `evals/` measures quality, `impact/`
runs the change workflow, `guard/` holds the safety checks, and `api/` is the front door. There
is no folder called `utils` or `helpers`.

A restaurant kitchen works the same way. It is organised into stations (grill, pastry, salads),
not into "all the knives here, all the pans there". When the parsing of PDFs needs a fix, we open
`parse/`, and everything about parsing is in one place.

## Starting from a template

One honest note: we didn't invent this setup from scratch. Most companies keep a **project
template**, a starter folder with the layout, settings and safety checks already wired up.
RegLens started from the portfolio's own template, so the next three chapters show a setup you'll
see again and again.

*Want the details? See `walkthrough/01-environment-setup/01-project-folder-and-git.md` and
`03-project-layout.md`.*

So far: we have a folder, a time machine and a place for everything. Next, we install Python
itself, in a way that gives every machine exactly the same setup.

**Next →** [2.2 Python, uv and the lock file](02-python-uv-and-the-lock-file.md)
