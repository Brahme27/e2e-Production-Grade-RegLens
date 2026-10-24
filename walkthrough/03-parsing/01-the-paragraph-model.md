# 01: The paragraph model

**File:** `src/reglens/parse/model.py`

## What
Every parser, whatever the regulator or file format, produces the same two things:

```python
Paragraph(
    ref="93",                                   # how the regulator numbers it
    text="93. A bank shall have a robust grievance redressal mechanism ...",
    section_path=("Chapter III – Outsourcing of Financial Services",
                  "H. Redressal of Grievances related to Outsourced Services"),
    kind="paragraph",                           # FCA/PRA: rule, guidance, evidential ...
    effective_from=date(2026, 1, 9),            # when this wording took effect, if known
    notes=("Amended vide circular ... dated January 9, 2026.",),
)
ParsedDocument(doc_id="rbi-cb-outsourcing-2025", version="current", regulator="RBI",
               title=..., doc_number="RBI/DOR/2025-26/171", issue_date=..., version_date=...,
               effective_from=..., paragraphs=[...])
```
Each document version is saved as one JSON file in `data/processed/documents/`.

## Why paragraphs, not pages or fixed-size chunks?
- **That's how regulation is cited.** An auditor asks "which paragraph says that?". If
  our unit is a paragraph, every answer can point to one.
- **Paragraphs are self-contained thoughts.** A fixed 512-token window often starts
  halfway through one rule and ends halfway through the next, mixing two obligations.
  Phase 08 *measures* this (pipeline A vs B in the ablation table).
- **The headings travel with the text.** "The bank shall review it annually" means
  nothing on its own. With its section path (*Chapter IV › E. Outsourcing Process › E.6 Exit
  Strategy*) it's clear what "it" is.

**Analogy:** a recipe book cut into recipes, not into pages. A page can split a recipe
in half; a recipe is always complete.

## How to run / what you should see
```bash
uv run python -c "from reglens.parse.model import load_documents; from pathlib import Path; d=load_documents(Path('data/processed/documents')); print(len(d), sum(len(x.paragraphs) for x in d))"
```
`48 4838`
