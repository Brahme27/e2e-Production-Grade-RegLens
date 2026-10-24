# 04: The LangGraph workflow

**Files:** `src/reglens/impact/workflow.py`, `src/reglens/api/routes/impact.py`

## What
The steps are wired as a **state machine** with LangGraph:

```
load_target ─▶ applicability ─▶ extract_obligations ─▶ judge_gaps ─▶ human_review ─▶ create_tickets
                    │ (rule doesn't apply to this firm)                    ▲ pauses here
                    └─────────────▶ END
```
- **load_target** finds the previous version (if any) and keeps only substantively changed paragraphs.
- **applicability** compares the rule's `applies_to` tags with the firm's (an NBFC rule
  doesn't apply to a commercial bank) and stops early if they don't overlap.
- **human_review** calls `interrupt()`: the graph **stops**, its state is saved by the
  checkpointer, and the API returns the draft. Nothing more happens until a person acts.
- **create_tickets** runs only after approval: one ticket per gap still open after review, with
  priority from severity, a due date (30/60/90 days), the rationale and the policy clauses to
  change, as JSON and CSV.

## The review loop, from the console
1. `POST /v1/impact` starts a run → status `awaiting_review`; obligations and judgements are
   stored in Postgres.
2. The reviewer clicks **Agree**, or **Override** a verdict with a note (`PATCH /v1/gaps/{id}`).
3. `POST /v1/impact/{run}/approve` resumes the graph with the overrides → tickets.
4. `GET /v1/impact/{run}/tickets.csv` downloads them (Jira/ServiceNow can import CSV).

## Why LangGraph here, and nowhere else?
Question answering is a straight pipeline, and plain functions are clearer. This workflow is
different: it's **stateful, long-running and must pause for a human**. Pause-and-resume with
saved state is exactly what LangGraph's checkpointer and `interrupt()` provide. Using a
framework only where its main feature is needed is a deliberate choice.

## Limitation (stated honestly)
The checkpointer is in memory: a run paused when the API restarts must be started again (its
obligations and reviews survive in Postgres). The production fix is LangGraph's Postgres
checkpointer, one line in `ImpactWorkflow.__init__`.

**Analogy:** a document approval route in an office: drafted, checked, then sitting in
the manager's in-tray until signed. Only then does it go out.
