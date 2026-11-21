[RegLens guide](../README.md) › Part 1: The idea

# 1.1 Rules that keep changing

Welcome to the [RegLens guide](../README.md). Before we install anything, we need to understand
the problem we are solving. Good projects start with a clear problem, not with a cool tool. So
let's meet the people who live with this problem every day.

## Four regulators, thousands of pages

Banks in India and the UK must follow rules written by four regulators:

- **RBI** (Reserve Bank of India) supervises Indian banks and NBFCs (non-bank lenders).
- **SEBI** (Securities and Exchange Board of India) supervises the stock markets and the firms
  that work in them.
- **FCA** (Financial Conduct Authority) sets the rules for how UK firms treat their customers.
- **PRA** (Prudential Regulation Authority) makes sure UK banks stay safe and sound.

Each one publishes its rules as web pages and PDFs, and together they run to thousands of pages.
The person who keeps a bank on the right side of all this is a **compliance analyst**. Every week
they face three questions:

1. **What exactly does the rule say, and where?** An auditor wants the paragraph number, not a
   vague memory.
2. **What did the rule say on a past date?** When auditors review a decision from last year, the
   rules of last year are the ones that count.
3. **A new rule has come out. What must we do now?** Which of our own internal policies already
   cover it, and which don't?

Today this is mostly done by hand: read the PDF, interpret it, search the bank's policies, raise
tasks. Large banks have whole teams for it. Smaller lenders and fintechs often don't.

## Rules change in two ways

Regulation is never finished. It changes in two ways. Sometimes a **new version** of the same
document appears: a rulebook is edited in place, or a guidance note gets a new edition. Other
times a **new document replaces an old one**, and the regulator says the old one is "repealed"
or "superseded". We'll call this **supersession**.

Think of a train timetable. When the new timetable starts, last year's isn't burned. You might
still need it to check a journey you took back then. But nobody should use it to plan tomorrow.
Regulation works the same way, which means the honest answer to "what does the rule say?" is
always another question: **as of when?**

## A well-read friend who sometimes bluffs

You've probably heard of a **large language model**, or **LLM**: the kind of AI behind chatbots
such as ChatGPT. An LLM has read an enormous amount of text and learned to predict the next word,
which lets it write fluent, confident answers. It's like a very well-read friend who answers from
memory.

For compliance work, that friend has four problems:

- **The memory is out of date.** The model learned from text collected months ago. It hasn't read
  last month's circular.
- **It bluffs.** When it doesn't know, it may invent a confident answer, even a paragraph number
  that doesn't exist. This is called **hallucination**, and it's like a student in a viva who
  would rather make something up than say "I don't know".
- **It has no sense of time.** It can't tell you which rule applied on 1 March 2024.
- **It can't show its sources.** An auditor will never accept "the chatbot said so".

Even the popular fix, a "chat with your PDFs" tool, falls short here. It usually cuts documents
into equal-sized pieces (so paragraph 38(b) gets split in half), searches only by meaning (so it
misses exact labels like "SS1/23"), ignores dates (so it quotes a rule repealed last year), and
always answers, even when it shouldn't.

## So what is RegLens?

**RegLens** is a regulatory **copilot**: an assistant that works next to a person, never in their
place. It does two jobs.

First, it **answers questions with citations**. Every sentence points to the exact paragraph it
came from, using only the rules that were in force on the date you choose. If the documents
don't answer the question, it says so.

Second, it handles **change impact**. When a regulator publishes a new version, RegLens works out
what the firm must now do, checks the bank's own policies for each point, drafts a list of gaps,
and then **stops and waits for a human** to approve them before anything becomes a task.

It is built on **37 real documents** (48 versions, about 4,800 paragraphs) from the four
regulators, including old ones that have been replaced. It runs on an ordinary laptop with no
graphics card, using free open models. It's a portfolio project, not a real compliance product,
and it isn't legal advice: every gap it finds is a draft for a human reviewer.

*Want the details? See `walkthrough/00-big-picture/README.md`.*

So far: we know the problem, why time matters, and why a chatbot on its own isn't enough. Next,
we follow one analyst's real question through the finished system.

**Next →** [1.2 Following one question](02-meeras-question.md)
