# 01: The firms and their policies

**Files:** `configs/entities.yaml`, `data/policies/**.md`, `evals/impact_gold.yaml`

## What
Real banks don't publish their internal policies, so we wrote our own for two fictional
firms:

| Firm | Regulated by | Policies |
|---|---|---|
| **Sahyadri Bank Ltd** (India, scheduled commercial bank) | RBI | Grievance Redressal & Internal Ombudsman Policy v3.2 (2024); KYC & AML Policy |
| **Northbridge Bank plc** (UK, retail + SME bank) | PRA + FCA | Outsourcing & Third-Party Risk Policy v4.0 (2024); Operational Resilience Policy v2.1 (2023); Complaints Handling Policy |

Each policy is a short, realistic markdown document with numbered clauses (`§5.3`) and a
header saying who owns it and when it was approved.

## The trick: gaps planted on purpose
The policies were written **before** the rules they are tested against, the way real
policies lag regulation, and with deliberate gaps, so we know the right answer:

| Obligation (from the rule) | What the policy says | Gold label |
|---|---|---|
| Auto-escalate rejected complaints to the IO **within 20 days** (RBI IO Directions 2026, ¶14) | "…within **25** days" | partially covered |
| Do **not** publish the IO's contact details (¶14(17)) | "the IO's name, email and phone shall be displayed on the website" | **not covered** (it contradicts!) |
| Sub-outsourcing only with **prior written consent** (PRA 2.1E) | provider must **inform** the bank | partially covered |
| Keep self-assessment records for **six years** (FCA SYSC 15A.6.2R) | "retained for **three** years" | partially covered |
| Board approves the self-assessment (SYSC 15A.7.1R) | "The Board shall approve … at least annually" | covered |

Across three target rules: **41 hand-labelled obligations: 20 covered, 13 partially, 8 not
covered.** Because the gaps were planted, the labels are true *by construction*, which is what
makes the gap judge measurable.

## Why fictional firms are fine
The rules are real (RBI, PRA and FCA text from our corpus); only the firm is invented. The
skill being demonstrated, reading real regulation against real-looking policy, is the same.
Every policy file says `synthetic: true` so nobody mistakes it for a real bank's document.

**Analogy:** a driving examiner's test route with deliberately placed hazards: you know
exactly which ones the candidate should spot.
