[RegLens guide](../README.md) › Part 5: Time

# 5.2 Valid from, valid to

In the [last chapter](01-who-replaced-whom.md) we drew a family tree of which document replaced
which. Arrows are useful, but a search engine needs something simpler: for any paragraph and any
date, a yes or no answer to "was this in force that day?". In this chapter we turn the arrows into
dates, and give those dates a proper home in a database.

## Three facts for every version

Every document version gets three facts:

- **valid from**: the first day the text applied;
- **valid to**: the first day it *no longer* applied (left empty while it's still in force);
- **status**, as of today: current, superseded, or future.

The window between the first two dates is the version's **validity interval**. A bus timetable
works the same way: "valid from 1 April, valid until 30 September". Last season's timetable isn't
thrown away, because you might need to check a journey you took then. But nobody reads it to plan
tomorrow.

Here are Meera's two documents, as the console shows them:

| Document | Valid from | Valid to | Status |
|---|---|---|---|
| RBI Internal Ombudsman Direction, 2023 | 29 Dec 2023 | 14 Jan 2026 | superseded |
| RBI Internal Ombudsman Directions, 2026 | 14 Jan 2026 | (empty) | current |

Her date, 5 January 2025, falls inside the first window and before the second one begins. So the
old direction is the right source, and the new one must stay out of the way.

## Working out the dates

The dates follow a few rules, applied in order.

**The start.** If the document says when it takes effect ("shall come into force from April 1,
2024"), that wins. Otherwise we use the edition date, and failing that, the issue date.

**The end of a version.** A version ends when the next version of the same document starts. The
2021 edition of the PRA's outsourcing statement ends the day the 2024 edition begins.

**The end of a document.** The last version ends when another document repeals it, using an arrow
from the supersession graph. If the repeal names a "with effect from" date, we use that; otherwise
we use the day the repealing document was issued.

**The future.** The PRA Rulebook already shows versions dated 1 January 2027. We keep them with
status *future*, so RegLens can even answer "what will apply next year?".

## Dates for single paragraphs

There's one subtle case. For the 2016 KYC Master Direction, we hold its text as amended in 2025.
If we said the whole document was "valid from 2025", it would vanish from every question about
2024, even though most of its paragraphs were in force for years.

So for the oldest version we hold of each document, every paragraph gets its **own** start date:
the RBI amendment footnote from Part 4, the FCA or PRA provision date, or else the original issue
date. Later versions don't need this, because the earlier wording sits in the earlier snapshot.

After all this, the corpus has **32 current versions, 14 superseded and 2 future**.

## "As of", in one line

Everything above boils down to one test we'll use in every search from now on. A piece of text is
in force on day D when **D is on or after "valid from", and before "valid to"** (an empty "valid
to" means it is still in force).

That's what "as of a date" means in RegLens. It isn't a hint to the model. It is a hard filter on
what the model is allowed to see.

## The card catalogue: a database

These facts need a home where they can be queried, joined and updated. We use a **relational
database**: a set of tables, like spreadsheets, that can be linked to each other. One table holds a
row per document version (title, number, dates, status, fingerprint); another holds the
supersession arrows; later ones will hold obligations, gap judgements and feedback. The paragraph
*text* doesn't live here; it lives in the parsed files and, soon, in the search index. Think of a
library's card catalogue: the books are on the shelves, and the cards tell you what exists, what
replaced what, and where to look.

We talk to the database through **SQLAlchemy**, a Python library that lets the same code run on
two databases. On the laptop and in tests we use **SQLite**, a database that is a single file
with no setup. In Docker and on AWS we use **PostgreSQL**, the open-source workhorse of real
services. Only one setting, the connection address, changes. Writing raw database commands by
hand for each one would mean two versions of everything.

Every write happens inside a **transaction**: either everything is saved, or, on any error,
nothing is. Reloading the dates replaces the old rows in one go, so running it twice gives the
same result.

> **Try it:** after `uv run poe temporal`, open `data/processed/validity.json`. You'll find every
> version with its valid-from date, valid-to date, status and, for replaced ones, what replaced it.

*Want the details? See `walkthrough/04-time-and-supersession/03-validity-intervals.md`,
`05-the-database.md` and `src/reglens/store/db.py`.*

So far: every version, and where needed every paragraph, has a validity window, stored in a
database. Next, we make all of this searchable.

**Next →** [6.1 Chunks with a label on top](../06-indexing/01-chunks-with-a-label-on-top.md)
