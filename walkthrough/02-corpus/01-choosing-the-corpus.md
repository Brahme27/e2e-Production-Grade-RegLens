# 01: Choosing the corpus

**Files:** `configs/sources.yaml`, `src/reglens/corpus/sources.py`

## What
A hand-picked list of **37 regulatory documents**:

| Regulator | Documents | Format | Old versions from |
|---|---|---|---|
| **RBI** (India, banks and NBFCs) | 14 master directions / directions | HTML pages (one PDF) | Old directions that were *replaced* by new ones in 2025–26; an archived first edition of the 2025 KYC Directions |
| **SEBI** (India, securities markets) | 8 circulars and master circulars | PDF inside an HTML page | A 2022 master circular replaced by a 2023 circular |
| **FCA** (UK, conduct) | 6 Handbook chapters (Consumer Duty, Principles, outsourcing, operational resilience, compliance, complaints) | One HTML page per section | Every provision shows the date it last changed |
| **PRA** (UK, prudential) | 6 Rulebook parts + 3 supervisory statements | HTML (point-in-time) + PDF editions | The Rulebook can be viewed *as at any date*; supervisory statements have dated editions |

All of them sit on **six themes every regulator covers**: KYC, outsourcing, cyber/IT and
operational resilience, complaints and grievance redressal, governance and compliance,
and model risk and AI.

## Why a curated list, not "crawl everything"?
- **Laptop budget.** Thousands of documents would take hours to embed on a CPU. ~40
  documents (~55 versions, several thousand paragraphs) index in minutes.
- **Shared themes make hard questions possible.** "How do RBI and the FCA differ on
  outsourcing?" needs both sides in the index.
- **Versions make time-travel testable.** We deliberately included rules that were
  *replaced*: the 2016 KYC Master Direction (repealed November 2025), the 2023 IT
  outsourcing direction, the 2023 Internal Ombudsman direction, and three editions of
  the PRA's outsourcing statement SS2/21 (2021, 2024, 2026).

## How it works
Each entry in `sources.yaml` is one document:
```yaml
- id: pra-ss2-21
  regulator: PRA
  kind: pdf                       # how to download it (html, pdf, sebi_circular, fca_chapter, pra_part)
  title: SS2/21 Outsourcing and third party risk management
  url: https://www.bankofengland.co.uk/...ss221-march-2026-update.pdf   # current edition
  topics: [outsourcing]
  applies_to: [uk_banks]
  snapshots:                      # older editions, each at its own URL
    - {label: 2021-03-29, url: https://...ss221-march-21.pdf, effective_from: 2022-03-31}
```
`sources.py` loads the file into typed objects (pydantic) and **refuses to start** if
an entry is broken: an id used twice, a PDF without a URL, or a PRA part without dates.

**Analogy:** it's the reading list a new compliance analyst gets on day one: not the
whole library, but the shelves that matter, including the old editions so they can
see what changed.

## A real-world snag we hit
RBI's PDF server (`rbidocs.rbi.org.in`) answers automated downloads with a JavaScript
"are you a robot?" page instead of the PDF. We don't try to defeat bot protection. For the
two RBI PDFs we need, we use the copies archived by the **Internet Archive's Wayback
Machine**, a public library of web snapshots. Everything else comes straight from the
regulators.

## How to run / what you should see
```bash
uv run python -c "from reglens.corpus.sources import load_sources; from pathlib import Path; print(len(load_sources(Path('configs/sources.yaml')).documents))"
```
`37`
