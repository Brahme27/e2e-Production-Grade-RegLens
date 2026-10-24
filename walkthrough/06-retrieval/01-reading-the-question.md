# 01: Reading the question

**File:** `src/reglens/retrieve/query.py`

## What
Before searching, cheap rules (no AI) read three things out of the question:

| Signal | Example question | Extracted |
|---|---|---|
| **As-of date** | "What applied *as of 1 March 2024*?", "*in March 2023*", "*in 2022*" | 2024-03-01, 2023-03-15, 2022-07-01 |
| **Regulators** | "How do *RBI* and the *FCA* differ…" | RBI, FCA |
| **Firm type** | "…for *NBFCs*?" | nbfcs |

It also flags hints for the router: comparison words ("compare", "differ", "versus"),
overview words ("main themes", "summarise"), change words ("amended", "before").

## Why rules here, not an LLM?
Dates and regulator names are exact, well-formed things: a regular expression gets them
right every time, in microseconds, for free. Spending an API call (and a second of latency)
to learn that "as of 1 March 2024" means 2024-03-01 would be wasteful and *less* reliable.

## How "vague" dates are handled
"In March 2023" becomes the 15th (the middle of the month) and "in 2022" becomes 1 July,
the middle of the year. The middle is the safest guess: it's the day least likely to sit
on the boundary of a rule change.

**Analogy:** the receptionist who, before passing your call along, notes "it's about
2024, and it's about the FCA" on a sticky note.

## How to run / what you should see
```bash
uv run python -c "from reglens.retrieve.query import analyse; print(analyse('As of 1 March 2024, how did RBI and FCA rules on outsourcing differ?'))"
```
`as_of=datetime.date(2024, 3, 1), regulators=('RBI', 'FCA')`, `compare_words: True`.
