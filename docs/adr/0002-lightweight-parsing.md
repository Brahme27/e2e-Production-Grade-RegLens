# ADR 0002: Lightweight structure-aware parsing instead of Docling

**Status:** accepted · **Date:** 2026-10-24

## Context
The plan named Docling (neural layout analysis, table structure, reading order). Our
sources are: RBI/FCA/PRA **HTML** (already structured), and ~16 **born-digital PDFs**
(SEBI circulars, PRA supervisory statements). Docling needs PyTorch and layout models
(~1 GB) and runs at roughly 1–3 s per page on CPU.

## Decision
- HTML: site-specific parsers using the regulators' own markup (provision cards, rule
  rows, `p.head` headings, amendment footnote tooltips).
- PDF: `pypdfium2` text lines plus rules for running headers/footers, wrapped lines,
  numbered/labelled paragraphs, headings and footnotes.

## Consequences
- The whole corpus parses in about a minute, with no ML dependencies in the parser.
- Paragraph refs match how regulators cite (`93`, `PRIN 2A.1.3G`, `Principle 1.2`).
- Complex PDF tables (e.g. SEBI CSCRF annexures) come out as flattened text and some
  unnumbered blocks (`Annexure I ¶3`). Acceptable for retrieval; revisit with Docling if
  table questions show up as an error class in evaluation.
- The parser interface (`ParsedDocument`) is the seam: a Docling-backed parser can be
  added for PDFs without touching anything downstream.
