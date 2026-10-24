# Phase 07: Answers ("say only what the sources say, and show where")

The retriever hands over 8 paragraphs. This phase turns them into an answer that a
compliance officer can trust: every statement cited, nothing invented, and an honest
"I could not find this" when the sources don't cover the question.

| Chunk | What happens |
|---|---|
| [01-the-answer-prompt.md](01-the-answer-prompt.md) | Numbered sources, strict rules, NOT_FOUND, and why the prompt is versioned |
| [02-citations-and-verification.md](02-citations-and-verification.md) | Every [n] marker checked: real source? supports the sentence? |
| [03-abstention.md](03-abstention.md) | Saying "not found" twice: before the LLM (free) and by the LLM |
| [04-streaming.md](04-streaming.md) | Words appear as they are written, and cached answers replay the same way |
