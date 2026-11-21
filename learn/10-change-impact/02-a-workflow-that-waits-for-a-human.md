[RegLens guide](../README.md) › Part 10: Change impact

# 10.2 A workflow that waits for a human

In the [last chapter](01-from-a-new-rule-to-a-to-do-list.md) RegLens turned the RBI's 2026
Directions into obligations and judged each one against Sahyadri Bank's policy. But those verdicts
are drafts written by a model. Before any of them becomes real work for real people, a human must
look at them. This chapter is about a workflow that knows how to **stop and wait**.

## A workflow as a graph with a memory

So far, everything in RegLens has been a straight line: a question goes in, an answer comes out, a
second or two later. Change impact is different. It has several steps, some steps can end the run
early, and in the middle it must pause, possibly for days, until a reviewer acts.

We describe it as a **graph**: each step is a box, and arrows say what comes next. All the steps
share a **state**, a single folder of facts that travels from step to step; each step reads what
it needs and adds what it produced. We build it with **LangGraph**, a library for exactly this
kind of multi-step workflow with saved state.

```
load_target ─▶ applicability ─▶ extract_obligations ─▶ judge_gaps ─▶ human_review ─▶ create_tickets
                    │ (the rule doesn't apply to this firm)               ▲ pauses here
                    └──────────────▶ END
```

- **load_target** finds the previous version of the rule, if there is one, and keeps only the
  paragraphs that changed in substance.
- **applicability** compares who the rule applies to with who the firm is. A rule for NBFCs doesn't
  apply to a commercial bank, so the run ends early instead of inventing work.
- **extract_obligations** and **judge_gaps** are the two steps from the last chapter.
- **human_review** is the pause.
- **create_tickets** turns the approved gaps into work items.

## The pause

When the workflow reaches `human_review`, it calls LangGraph's `interrupt()`. The graph **stops**,
its whole state is saved by a **checkpointer** (think of a bookmark that remembers exactly where
you were and what you'd written), and the API hands the draft back to the console. Nothing else
happens until a person acts. This is called **human-in-the-loop**: the machine does the reading
and drafting, and a human makes the decision.

It works like a document approval route in an office. The draft is written, checked, and then sits
in the manager's in-tray until signed. Only then does it go out.

For Meera, the impact board in the console lists every obligation from the 2026 Directions, the
verdict, the reason and the policy clauses relied on. For each row she clicks **Agree**, or
**Override** with a note, for example when she knows a clause elsewhere already covers the point.
When she's done, she approves. The workflow picks up from its bookmark with her decisions, and
`create_tickets` writes one ticket per gap still open: a priority from the obligation's severity, a
due date 30, 60 or 90 days out, the reasoning, and the clauses to change. The tickets download as a
spreadsheet file that tools such as Jira or ServiceNow can import.

## LangGraph here, and nowhere else

Why not use LangGraph for question answering too? Because a straight pipeline is clearer as plain
functions, and adding a framework there would only add moving parts. Change impact is the one place
that is **stateful, long-running, and must pause for a person**, and pause-and-resume with saved
state is exactly what LangGraph's checkpointer and `interrupt()` provide. We could have built the
pause by hand with database flags, but that means writing and testing our own resume logic. Using a
framework only where its main feature is needed is a deliberate choice.

## An honest limitation

The checkpointer currently keeps its bookmarks **in memory**. If the API restarts while a run is
waiting for review, that run must be started again. (The obligations and judgements already saved to
the database survive.) The production fix is LangGraph's PostgreSQL checkpointer, and the cloud
setup runs a single API copy until then. It's written down in the limitations page, not hidden.

> **A bump on the road:** the console first promised that an impact run takes "about a minute".
> When we ran the real thing in Docker, a cold run of a large rule rewrite made one model call per
> changed obligation, each taking around 15 seconds under the free tier's per-minute token limit:
> several minutes in all. Our end-to-end test timed out at four. We changed the console's wording to
> "a few minutes on the free tier; repeat runs are instant", gave the test a realistic time budget,
> and saved the replies in the notebook so later builds replay them. The lesson: test with cold
> caches and real limits, and tell users the truth about waiting times.

*Want the details? See `walkthrough/09-change-impact/04-the-langgraph-workflow.md`,
`docs/adr/0003-llm-proposes-human-approves.md` and `src/reglens/impact/workflow.py`.*

So far: a new rule becomes obligations, verdicts, a pause for human review, and tickets only after
approval. Next, we protect the whole system from people who try to trick it.

**Next →** [11.1 Guardrails and prompt injection](../11-safety-and-speed/01-guardrails-and-prompt-injection.md)
