# 05: The database

**File:** `src/reglens/store/db.py`

## What
A relational database for the facts we query, join and update:

| Table | Holds | Used by |
|---|---|---|
| `document_versions` | One row per version: title, number, dates, validity, status, content fingerprint | Document pages, "as of" filters, the change feed |
| `supersession_edges` | Who repealed or amended whom, how we know, from when | The supersession timeline in the UI |
| `obligations`, `gap_judgements` | Change-impact results (phase 10) | The impact board |
| `feedback` | Thumbs up/down on answers | Quality monitoring |

Paragraph *text* doesn't live here; it lives in the processed JSON files and the search
index (phase 05).

## Why SQLAlchemy?
The same code runs on **SQLite** (a single file, zero setup, used locally and in tests) and
on **PostgreSQL** (in Docker Compose and AWS RDS). Only the connection string changes:
```
REGLENS_DATABASE_URL=postgresql+psycopg://reglens:…@postgres:5432/reglens
```
`session_scope()` wraps every write in a transaction: everything is saved, or (on any
error) nothing is. Reloading the temporal data is idempotent: old rows are deleted and
new ones inserted in one transaction.

**Analogy:** the index cards in a library's card catalogue. The books (the text) are on
the shelves; the cards tell you what exists, what replaced what, and where to look.

## How to run / what you should see
```bash
uv run poe temporal
uv run python -c "import sqlite3; c=sqlite3.connect('artifacts/reglens.db'); print(c.execute('select status, count(*) from document_versions group by status').fetchall())"
```
`[('current', 32), ('future', 2), ('superseded', 14)]`
