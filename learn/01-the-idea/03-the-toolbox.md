[RegLens guide](../README.md) › Part 1: The idea

# 1.3 The toolbox, and what RAG means

In the [last chapter](02-meeras-question.md) we followed Meera's question through the finished
system. Before we start building, let's give the big idea behind it a name, and then open the
toolbox. Don't try to memorise the tools. This chapter is a map you can come back to, and every
tool gets a proper introduction where we first pick it up.

## An open-book exam

Remember the well-read friend who answers from memory and sometimes bluffs? Now imagine giving
that friend an **open-book exam**. Before each question, someone finds the right pages and puts
them on the desk. The rule is: answer only from these pages, and write the page number after
every sentence.

That is **RAG**, short for **retrieval-augmented generation**:

- **Retrieval**: find the few paragraphs that are relevant to the question.
- **Augmented**: hand them to the model along with the question.
- **Generation**: the model writes the answer from those paragraphs, citing each one.

Everything we hand the model (the instructions, the paragraphs and the question) is called the
**prompt**. RAG fixes most of the chatbot's problems at once. The answers are up to date, because
we control the documents. They are checkable, because every sentence cites its source. And they
bluff less, because the model is told to answer only from the pages, or to say it can't.

RegLens adds one more rule that ordinary RAG doesn't have: **the pages on the desk must be the
ones that were in force on the date asked**. That single idea shapes half of this guide.

## Four rules for choosing tools

Four rules guided every choice:

1. **Industry-standard.** Tools you'd find in a real company's job description.
2. **Free and laptop-friendly.** Everything runs on a laptop with no graphics card and under 8 GB
   of memory. The only cloud services we call are free tiers: a language model and, optionally,
   Langfuse.
3. **Added only when needed.** Each library joins the project in the part that needs it.
4. **Measured, not assumed.** A technique stays only if the numbers say it helps.

## The foundation (Part 2)

| Tool | Its job, in one line |
|---|---|
| **Python 3.12** | The language everything is written in |
| **uv** | Installs Python and libraries, and locks their exact versions |
| **pydantic-settings** | Reads settings and secrets from the environment, and checks them |
| **structlog** | Writes logs as searchable fields |
| **ruff**, **mypy**, **pytest** | Catch mistakes before the code runs, and test it |
| **pre-commit**, **GitHub Actions** | Run every check automatically, locally and on a clean machine |
| **poe** | Gives every command a short name |

## Reading the rulebooks (Parts 3 to 5)

| Tool | Its job, in one line |
|---|---|
| **httpx** | Downloads web pages and PDFs, politely |
| **selectolax** | Reads the structure of web pages |
| **pypdfium2** | Pulls lines of text out of PDFs |
| **SQLAlchemy** with **SQLite** or **PostgreSQL** | A database of document versions and dates |

## Search and answers (Parts 6 to 9)

| Tool | Its job, in one line |
|---|---|
| **fastembed** | Runs small search models on an ordinary processor |
| **Qdrant** | A database built for searching by meaning |
| **scikit-learn** | Trains the tiny model that sorts questions by kind |
| **LiteLLM** and **Groq** | Call free open LLMs: gpt-oss for answers, Qwen as a judge |

## The workflow and the platform (Parts 10 to 13)

| Tool | Its job, in one line |
|---|---|
| **LangGraph** | Runs a multi-step workflow that can pause for a human |
| **Llama Prompt Guard 2** | A small model that spots attempts to trick the LLM |
| **Redis** | Remembers recent answers so repeat questions are instant |
| **Langfuse** | Records every step of every question for later inspection |
| **FastAPI** | The web API: the front door other programs knock on |
| **Next.js**, **Playwright** | The web console, and a robot that tests it by clicking |
| **Docker**, **docker compose** | Package everything so it runs the same everywhere |
| **Terraform** | Writes the AWS cloud setup down as code |

The whole project uses two languages: **Python** for everything on the server, and
**TypeScript** (JavaScript with types) for the web console, because that's what Next.js is built
on.

> **A bump on the road:** while we were building RegLens, Groq retired one of the models an
> earlier project relied on. Because our code never names a model directly (it asks LiteLLM for a
> role such as "reasoning-large", and a small config file maps each role to a real model), the fix
> was one line in that file. The lesson: free services change under you. Put a thin layer between
> your code and anything you don't control.

*Want the details? See `README.md` (tech stack) and `docs/adr/`, where each big tool decision is
written down.*

So far: we know the problem, the route, the big idea and the tools. Time to set up our workshop.
In Part 2 we create the project folder and the safety nets every later step relies on.

**Next →** [2.1 A home for the project](../02-setting-up-the-workshop/01-a-home-for-the-project.md)
