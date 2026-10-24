# 02: Measuring the extractor

**Files:** `evals/supersession_gold.yaml`, `src/reglens/evals/supersession.py`,
`configs/supersession_overrides.yaml`

## What
A **gold set** of 57 edges, labelled by reading the source documents, not the extractor's
output (otherwise we'd just be grading our own homework). For each of 14 documents it lists
*every* edge: links inside our corpus, plus numbered circulars we don't hold
(`ext:CIR/MRD/DP/13/2015`). Four RBI directions are labelled with **no** in-corpus edges on
purpose, so an over-eager model gets caught.

## Results
| Extractor | Precision | Recall | F1 | Inside-corpus recall |
|---|---|---|---|---|
| Rules only | **1.000** | 0.895 | 0.944 | 0.375 (3 of 8) |
| Rules + LLM | 0.982 | **0.982** | **0.982** | **1.000** (8 of 8) |

- **Precision** = of the edges we claimed, how many are real.
- **Recall** = of the real edges, how many we found.
- Rules alone miss all five generic RBI repeals; the LLM finds every one.

## The two errors, in the open
1. **Missed:** one CSCRF circular number was split mid-word by the PDF ("…/P/CI / R/2022/73").
   Our repair handles digits, not letters. Known, accepted.
2. **False positive (LLM):** the model decided *"instructions relating to governance"*
   (RBI Governance Directions 2025) also repealed the *IT Governance* direction of 2023. In
   reality, IT governance was repealed eight months later by the 2026 cybersecurity
   directions. This mistake would have closed the IT Governance direction too early. We
   tried a clearer prompt ("match on subject matter, not shared words"); the model still
   said yes.

## What we did about error 2: human review
This is how real compliance teams work: **the model proposes, a person approves.** A
reviewer's decision lives in `configs/supersession_overrides.yaml`, with the reason, and is
applied before validity dates are computed. The table above shows the **raw** extractor
scores, before review, so the numbers stay honest.

## Why this matters for an interview
"Our LLM step lifted recall on in-corpus repeals from 3/8 to 8/8 at a cost of 9 API
calls. It made one confident wrong call, which we caught with a gold set and routed to
human review rather than overfitting the prompt to one example."
