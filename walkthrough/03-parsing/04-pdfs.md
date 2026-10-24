# 04: PDFs: rebuilding paragraphs from lines

**File:** `src/reglens/parse/pdf.py`

## What
SEBI circulars and PRA supervisory statements are PDFs. A PDF knows where to *draw*
each line of text, but has no idea what a paragraph is. We rebuild the structure:

1. **Extract lines** per page with `pypdfium2` (Google's PDF engine, fast and free).
2. **Remove running headers and footers**: any line that repeats on at least 30% of the
   pages (and on two pages at minimum). Numbers are masked, so "Page 3 of 8" and "Page 4
   of 8" count as the same line.
3. **Glue wrapped lines**: a line that doesn't start a numbered paragraph, a list item
   or a new sentence continues the previous one.
4. **Spot headings**: short numbered titles ("2 Model tiering"), "Annexure"/"Part"
   lines, or a short title line immediately followed by a numbered paragraph.
5. **Drop footnotes**: in documents numbered `2.1, 2.2…`, a line starting with a bare
   number ("4 Model use is defined here…") is a footnote, not paragraph 4.
6. **Labelled numbers**: "Principle 1.2 Model inventory" becomes the citable ref
   `Principle 1.2`.

## Why not a heavy layout model (Docling)?
Docling uses neural layout models. They're excellent, but slow on a CPU (seconds per page)
and memory-hungry. Our PDFs are clean, born-digital text, where line rules get us most of
the way in under a second per document. The decision and its trade-off are recorded in
`docs/adr/0002-lightweight-parsing.md`.

## What we measured while tuning
| Document | Paragraphs | Unnumbered before → after tuning |
|---|---|---|
| PRA SS1/23 (model risk) | 67 | 18 → 1 |
| PRA SS2/21 (outsourcing, 2026 edition) | 157 | 38 → 8 |
| SEBI SCORES circular | 108 | 84 → 11 |

The remaining unnumbered text (annexure tables, forms) gets a readable ref like
`Annexure I ¶3`.

## Bugs the tests caught
- With a 3-page PDF, "repeats on 30% of pages" meant *one* page, so every line counted as
  a footer and the document came out empty. A header must now repeat on at least two pages.
- An unnumbered heading replaced the numbered section above it instead of nesting under it.

**Analogy:** a scanned book where you have to work out from indentation and numbering
where each paragraph starts, ignoring the page header on every page.

## How to run / what you should see
```bash
uv run pytest tests/unit/test_parse.py -q --no-cov -k pdf
```
The test builds a tiny 3-page PDF by hand (`tests/helpers.py`) with a running footer, a
wrapped line, a footnote and an unnumbered heading, and checks that each one is handled.
