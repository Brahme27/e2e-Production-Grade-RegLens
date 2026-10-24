# Phase 03: Parsing ("reading the rulebooks properly")

Raw downloads are web pages and PDFs full of menus, page numbers, footers and layout
tables. This phase turns each one into a clean list of **numbered paragraphs**, the
way a lawyer would cite them ("para 93", "PRIN 2A.1.3G", "rule 2.1"). Each paragraph keeps
the headings it sits under and, where the regulator says so, the date its wording took effect.

| Chunk | What happens |
|---|---|
| [01-the-paragraph-model.md](01-the-paragraph-model.md) | Why the paragraph is our unit of meaning and citation |
| [02-rbi-pages.md](02-rbi-pages.md) | RBI HTML: headings, numbered paragraphs, tables, and amendment footnotes |
| [03-uk-rulebooks.md](03-uk-rulebooks.md) | FCA Handbook and PRA Rulebook: provision-level references and dates |
| [04-pdfs.md](04-pdfs.md) | SEBI and PRA PDFs: rebuilding paragraphs from lines of text |
| [05-the-parse-run.md](05-the-parse-run.md) | One command that parses everything, and what the corpus looks like |

## Reproduce this phase
```bash
uv run poe parse     # ~1 minute: 48 versions -> 4,838 paragraphs in data/processed/documents/
```
