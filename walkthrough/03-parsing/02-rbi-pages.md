# 02: RBI pages

**Files:** `src/reglens/parse/rbi.py`, `src/reglens/parse/blocks.py`, `src/reglens/parse/html_text.py`

## What
RBI directions are long HTML pages. The parser:
1. finds the content area (`tr.tablecontent2`) and the title (with its "Updated as on" date);
2. reads the letterhead: document number (`RBI/DOR/2025-26/171`) and issue date;
3. walks every paragraph, heading and table **in reading order**;
4. groups them: a line starting with a number (`93.`) opens a new paragraph; sub-items
   `(i)`, provisos and tables join the paragraph they belong to;
5. keeps a **stack of headings** (*Chapter › Section › Sub-section*) for each paragraph.

## The hidden treasure: amendment footnotes
Older RBI master directions mark every change with a small superscript number. Its
tooltip says exactly what happened, for example *"Inserted vide circular
DOR.AML.BC.No.27/14.01.001/2019-20 dated January 9, 2020."* We strip the marker from
the text, because it would confuse search, but **keep the note**. The latest date in a
paragraph's notes becomes that paragraph's `effective_from`. The 2016 KYC direction has
54 paragraphs dated this way, which gives us paragraph-level history from a single page.

## Real-world mess we had to handle
| Problem | Fix |
|---|---|
| The whole page sits inside layout tables, so everything looked "nested in a table" | Tell layout tables (which contain other tables or headings) from data tables (rows and columns of values) |
| Inserting " \| " between table cells vanished | HTML parsers move stray text *out* of tables. We now rebuild each table as text ourselves: one line per row, cells joined by " \| " |
| "41. Accounts of PEPs" is bold, so it looked like a heading | A bold line that starts with a number opens paragraph 41 instead |
| Paragraph numbers restart in annexes (two "para 1"s) | Refs inside annexes are prefixed: `Annex II, 1` |
| "Previous Versions" links, letterhead lines, the footnote list at the end | Removed as boilerplate |

**Analogy:** reading a contract by its clause numbers instead of its line breaks, and
noting the "amended on" stamps in the margin.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_parse.py -q --no-cov -k rbi
```
A synthetic RBI page (letterhead, chapters, a footnoted amendment, a data table, a layout
table, a bold numbered title) is parsed into exactly paragraphs 1, 2 and 3. Paragraph
2's `effective_from` is the amendment date.
