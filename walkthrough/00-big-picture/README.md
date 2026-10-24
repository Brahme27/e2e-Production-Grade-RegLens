# Phase 00: The big picture

## The problem in one paragraph
Banks in India and the UK must follow thousands of pages of rules from four regulators:
**RBI** (Reserve Bank of India), **SEBI** (Securities and Exchange Board of India), the
**FCA** (Financial Conduct Authority) and the **PRA** (Prudential Regulation Authority).
Rules keep changing. A new circular can *replace* an old one, and a rulebook can be
*edited in place*. A compliance officer constantly asks three questions:
1. *"What exactly does the rule say, and where?"* (with the paragraph number, for the auditor)
2. *"What did the rule say on 1 March 2024?"* (for audits of past decisions)
3. *"A new rule just came out. What must we do, and which of our internal policies don't
   cover it yet?"*

Today this is mostly done by hand: read the PDF, interpret it, find the affected
policies, raise tasks. Large banks have whole teams for it; smaller lenders and fintechs
don't.

## Why a plain "chat with PDFs" bot fails here
| Plain chatbot | What goes wrong | What RegLens does instead |
|---|---|---|
| Cuts documents into fixed 512-token pieces | Paragraph "38(b)" gets split in half, and citations become impossible | Chunks follow the regulator's own numbered paragraphs |
| Searches by meaning only | Misses exact terms like "SS1/23" or "PRIN 2A.4.1R" | Searches by meaning **and** exact words (hybrid search) |
| Ignores time | Quotes a rule that was repealed last year | Every paragraph has a *valid from / valid to* date, and every search is filtered "as of" a date |
| Always answers | Invents paragraph numbers | Must cite a real retrieved paragraph for every sentence, or say "not found" |
| Answers only questions | Doesn't help with the actual job | Extracts obligations from a new rule and checks them against the bank's own policies |

## What the finished system looks like
```
                ┌──────────────── Ingestion (runs on a schedule) ────────────────┐
 RBI, SEBI,  →  │ polite crawler → parser (paragraph numbers, dates) → versions & │
 FCA, PRA       │ supersession graph → chunks → embeddings → Qdrant search index  │
                └─────────────────────────────────────────────────────────────────┘
                ┌──────────────────────── Question answering ────────────────────────┐
 "What must     │ guardrails → cache → router → hybrid search (as-of date filter) →   │
  banks do…?" → │ reranker → LLM answer with [citations] → citation checker → answer │
                └─────────────────────────────────────────────────────────────────────┘
                ┌──────────────────────── Change impact ─────────────────────────────┐
 New circular → │ what changed → obligations (JSON) → matching internal policies →    │
                │ gap judgement (covered / partly / missing) → human review → tickets │
                └─────────────────────────────────────────────────────────────────────┘
```
Plus a web console (Next.js), tracing of every LLM call, an evaluation suite that
measures every improvement, Docker for local runs, and Terraform files for AWS.

## The rule we build by: measure first
Every retrieval upgrade must **earn its place** in an ablation table: we start with
the naive chatbot (pipeline A) and add one technique at a time (B, C, D…), measuring
retrieval recall, answer faithfulness, citation precision and latency at each step. If
a technique doesn't improve the numbers, it doesn't ship.

## Constraints that shaped the design
| Constraint | Consequence |
|---|---|
| Laptop: CPU only, 7.7 GB RAM | Small local models (bge-small embeddings, BM25, int8 reranker) running on ONNX; corpus of a few hundred documents, not tens of thousands |
| Free LLM tier: 1,000 requests/day, 8,000 tokens/minute per model | Every LLM call is cached on disk; retrieval metrics need no LLM; one LLM summary per *document* instead of one call per paragraph |
| Real public sources only | Crawlers for rbi.org.in, sebi.gov.in, handbook.fca.org.uk and prarulebook.co.uk, with polite delays and a local cache |
| Internal bank policies are confidential | We write synthetic policies for two fictional firms (*Northbridge Bank*, UK and *Sahyadri Finance*, India) with deliberately **planted gaps**, so gap analysis can be scored |

## Not legal advice
RegLens is an information tool. Every answer links to the official source, shows the
document's status (current / superseded) and says when it can't find support.
