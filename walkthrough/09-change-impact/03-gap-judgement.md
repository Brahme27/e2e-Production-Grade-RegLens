# 03: Gap judgement

**Files:** `src/reglens/impact/policies.py`, `src/reglens/impact/obligations.py` (judge)

## What
For each obligation:
1. **Find the relevant policy clauses.** The firm's policies are split into clauses and indexed
   in their own Qdrant collection (`policies`). The same hybrid search + reranker finds the 5
   most relevant clauses, filtered to *that firm only*.
2. **Judge.** The LLM compares the obligation with those clauses and answers:

| Verdict | Meaning |
|---|---|
| `covered` | The policy requires what the rule requires, numbers and deadlines included (stricter is fine) |
| `partially_covered` | The topic is addressed, but part is missing or the number/frequency/deadline is weaker |
| `not_covered` | Nothing addresses it, or a clause **contradicts** it |

…plus a one-line rationale, the clause labels relied on (`SB-POL-CS-007 §5.3`) and a
confidence. Clause labels the judge invents are discarded: only clauses it was shown count.

## Why "partially covered" matters
Most real gaps are not missing topics but **weaker numbers**: 25 days instead of 20, three
years instead of six, "inform" instead of "consent". A yes/no checker would call these covered.
The prompt makes numbers and deadlines part of the definition of "covered".

## How it is measured
The judge is given each **gold** obligation (so extraction errors don't leak in) and its verdict
is compared with the planted label: accuracy, a 3×3 confusion matrix and **Cohen's κ**
(agreement beyond chance), plus "gap detection accuracy" (does it at least separate *covered*
from *needs work*?).

**Analogy:** an auditor with the rulebook in one hand and the firm's manual in the other,
ticking, half-ticking or crossing each requirement, and noting the page they looked at.
