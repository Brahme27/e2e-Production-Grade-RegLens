[RegLens guide](README.md) › Glossary

# Glossary

Every term in the guide, in plain words. The link takes you to the chapter where it is first
explained.

**Ablation**: an experiment that starts from the simplest system and adds one technique at a time,
measuring each step on the same questions. [9.2](09-evaluation/02-the-ablation.md)

**Abstention**: the system deliberately declining to answer, because the sources don't support an
answer. [8.2](08-answers/02-checking-receipts-and-saying-i-dont-know.md)

**ADR (architecture decision record)**: a one-page note of a decision, its reasons and its
trade-offs. [3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**Alias**: a nickname for a search collection, so a new index can be swapped in at once.
[6.3](06-indexing/03-qdrant-the-searchable-shelf.md)

**API (application programming interface)**: the front door other programs call, a set of
addresses that each do one job. [1.3](01-the-idea/03-the-toolbox.md)

**API key**: a password one program shows when it calls another program's service.
[2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**"As of"**: answering with only the text that was in force on a chosen date. In RegLens it is a
hard filter, not a hint. [5.2](05-time/02-valid-from-valid-to.md)

**Backend-for-frontend**: a small server beside the console that passes requests to the API and
holds the API key, so the browser never sees it. [12.1](12-the-api-and-console/01-the-api-and-the-console.md)

**BM25**: a classic keyword-scoring method that rewards chunks containing the question's words,
especially rare ones. [6.2](06-indexing/02-meaning-and-exact-words.md)

**Cache**: a store of results kept so you don't pay for them twice. RegLens keeps every LLM answer
in one. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Checkpointer**: the part of LangGraph that saves a paused workflow's state, like a bookmark.
[10.2](10-change-impact/02-a-workflow-that-waits-for-a-human.md)

**Chunk**: the piece of text a search returns. Chunking is deciding where to cut.
[6.1](06-indexing/01-chunks-with-a-label-on-top.md)

**CI (continuous integration)**: automated checks that run on a clean machine every time code is
pushed. Ours runs on GitHub Actions. [2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Citation precision**: the share of answer sentences whose cited source really supports them.
[9.3](09-evaluation/03-the-llm-judge.md)

**Citation verification**: checking that each citation is real and backs up its sentence,
numbers included. [8.2](08-answers/02-checking-receipts-and-saying-i-dont-know.md)

**Commit**: a saved snapshot of the code in Git, with a short message describing the change.
[2.1](02-setting-up-the-workshop/01-a-home-for-the-project.md)

**Compliance analyst**: the person who keeps a firm on the right side of the regulators' rules.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Container**: a sealed box holding an application and everything it needs, so it runs the same
anywhere. [13.1](13-shipping-it/01-the-whole-stack-in-docker.md)

**Context header**: a short label written on top of a chunk (regulator, document, headings,
paragraph) so it makes sense on its own. [6.1](06-indexing/01-chunks-with-a-label-on-top.md)

**Contextual retrieval**: the technique of adding context to every chunk before indexing it.
[6.1](06-indexing/01-chunks-with-a-label-on-top.md)

**Copilot**: an assistant that works next to a person, never in their place.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Corpus**: the collection of documents a system reads from. Ours has 37 documents and 48 versions.
[3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**CORS**: browser rules that limit which websites may call which; a proxy on the same site avoids
them. [12.1](12-the-api-and-console/01-the-api-and-the-console.md)

**Coverage**: the percentage of code lines the tests actually ran. Ours must stay at or above 80%.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Crawler**: a program that downloads web pages automatically. Ours is polite.
[3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**Cross-encoder**: a model that reads the question and a paragraph together and scores how well
they match. [7.3](07-retrieval/03-a-second-closer-reading.md)

**Dense vector**: a list of numbers capturing a text's meaning, where every position holds a value.
[6.2](06-indexing/02-meaning-and-exact-words.md)

**Docker**: the standard tool for building images and running containers.
[13.1](13-shipping-it/01-the-whole-stack-in-docker.md)

**Docker compose**: a file that describes several containers and how they connect, started with
one command. [13.1](13-shipping-it/01-the-whole-stack-in-docker.md)

**ECS Fargate**: an AWS service that runs containers without you managing servers.
[13.2](13-shipping-it/02-the-cloud-with-terraform-and-ci.md)

**Embedding**: a list of numbers that places a text in a "space of meaning", so similar meanings
sit close together. [6.2](06-indexing/02-meaning-and-exact-words.md)

**Environment variable**: a named value the operating system hands a program when it starts, used
for settings and secrets. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**F1**: one score that balances precision and recall, high only when both are.
[5.1](05-time/01-who-replaced-whom.md)

**Failing fast**: refusing to start, with a clear error, when something is wrong, instead of
misbehaving later. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Faithfulness**: the share of answer sentences supported by the sources.
[9.3](09-evaluation/03-the-llm-judge.md)

**FastAPI**: the Python web framework behind RegLens's API, with built-in input checks and
documentation. [12.1](12-the-api-and-console/01-the-api-and-the-console.md)

**FCA (Financial Conduct Authority)**: the UK regulator for how firms treat their customers.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Fingerprint**: a short code computed from a file's exact bytes; change one character and it
changes. [3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**Frontend**: the part of a system people see and click; ours is the Next.js console.
[12.1](12-the-api-and-console/01-the-api-and-the-console.md)

**Gap analysis**: comparing what the rules require with what a firm's policies say, to find what's
missing. [10.1](10-change-impact/01-from-a-new-rule-to-a-to-do-list.md)

**Git**: a time machine for code that records every saved step so it can be viewed, compared or
undone. [2.1](02-setting-up-the-workshop/01-a-home-for-the-project.md)

**gitleaks**: a check that recognises API keys and passwords and stops them being committed.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Golden set**: a fixed list of test questions with known right answers. Ours has 195.
[9.1](09-evaluation/01-the-golden-set.md)

**Graph**: dots joined by arrows. RegLens uses one for "who replaced whom", and another for its
change workflow. [5.1](05-time/01-who-replaced-whom.md)

**Groq**: a service that runs open LLMs very fast, with a free tier.
[2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Guardrails**: checks around a model that block, clean or drop unsafe text.
[11.1](11-safety-and-speed/01-guardrails-and-prompt-injection.md)

**Hallucination**: an LLM inventing a confident answer, or a source, that isn't true.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**HTTP**: the language browsers and servers use to send requests and responses.
[8.3](08-answers/03-words-as-they-are-written.md)

**Human-in-the-loop**: the machine reads and drafts, and a person makes the decision.
[10.2](10-change-impact/02-a-workflow-that-waits-for-a-human.md)

**Hybrid search**: searching by meaning and by exact words at once, then merging the results.
[7.2](07-retrieval/02-two-searches-and-a-fair-vote.md)

**Image**: the frozen recipe a container is started from.
[13.1](13-shipping-it/01-the-whole-stack-in-docker.md)

**Infrastructure as code**: describing cloud setup in text files kept in Git, instead of clicking
in a website. [13.2](13-shipping-it/02-the-cloud-with-terraform-and-ci.md)

**Internal Ombudsman**: an independent senior person inside a bank who reviews complaints the bank
has rejected. [1.2](01-the-idea/02-meeras-question.md)

**interrupt()**: the LangGraph call that stops a workflow and waits for a person.
[10.2](10-change-impact/02-a-workflow-that-waits-for-a-human.md)

**JSON**: a simple text format of labelled fields that programs read easily.
[2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**LangGraph**: a library for multi-step workflows with saved state that can pause for a human.
[10.2](10-change-impact/02-a-workflow-that-waits-for-a-human.md)

**LiteLLM**: a library that lets our code ask for a model role, such as "reasoning-large", instead
of a specific model. [1.3](01-the-idea/03-the-toolbox.md)

**LLM (large language model)**: an AI trained on huge amounts of text that writes fluent answers by
predicting the next word. [1.1](01-the-idea/01-rules-that-keep-changing.md)

**LLM-as-judge**: using a second model to label each sentence of an answer against its sources.
[9.3](09-evaluation/03-the-llm-judge.md)

**Load balancer**: the cloud front door that receives traffic and passes it to the right container.
[13.2](13-shipping-it/02-the-cloud-with-terraform-and-ci.md)

**Lock file**: a file (`uv.lock`) that records the exact version of every library, so every machine
installs the same thing. [2.2](02-setting-up-the-workshop/02-python-uv-and-the-lock-file.md)

**Log (structured)**: the program's diary, written as named fields rather than sentences so it can
be searched. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Logistic regression**: the simplest classifier: it weighs evidence and gives each option a
probability. [7.1](07-retrieval/01-reading-the-question.md)

**Manifest**: the record of every download: where it came from and its fingerprint.
[3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**Metadata**: data about the data, such as a chunk's document, dates and status, like the label on
a jar. [6.1](06-indexing/01-chunks-with-a-label-on-top.md)

**MRR (mean reciprocal rank)**: one divided by the position of the first right paragraph, averaged
over questions. [9.1](09-evaluation/01-the-golden-set.md)

**mypy**: a type checker that reads type hints and reports mismatches before the code runs.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**nDCG@10**: a score from 0 to 1 for how well the right paragraphs are placed near the top of the
first 10 results. [9.1](09-evaluation/01-the-golden-set.md)

**NOT_FOUND**: the exact word the model must reply with when the sources don't answer the
question. [8.1](08-answers/01-answers-with-receipts.md)

**Obligation**: one thing a firm must, or must not, do, written in a fixed shape with its source
paragraph. [10.1](10-change-impact/01-from-a-new-rule-to-a-to-do-list.md)

**Observability**: being able to see inside a running system from what it records.
[11.2](11-safety-and-speed/02-faster-and-visible.md)

**ONNX**: a portable format for trained models that runs fast on an ordinary processor.
[6.2](06-indexing/02-meaning-and-exact-words.md)

**Open-weight model**: a model whose trained numbers anyone may download and run, such as gpt-oss.
[8.1](08-answers/01-answers-with-receipts.md)

**OWASP**: a security community whose list of top LLM risks ranks prompt injection first.
[11.1](11-safety-and-speed/01-guardrails-and-prompt-injection.md)

**Parameters**: the adjustable numbers inside a model; roughly, its size.
[6.2](06-indexing/02-meaning-and-exact-words.md)

**Parsing**: turning a raw file into labelled parts: headings, numbered paragraphs, footers to
throw away. [4.1](04-parsing/01-from-pages-to-citable-paragraphs.md)

**poe (poethepoet)**: a task runner that gives every long command a short name, such as
`uv run poe check`. [2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Point and payload**: in Qdrant, a point is one stored chunk; its payload is the text and metadata
it carries. [6.3](06-indexing/03-qdrant-the-searchable-shelf.md)

**PRA (Prudential Regulation Authority)**: the UK regulator that keeps banks safe and sound.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**pre-commit**: a tool that runs checks every time you commit, and blocks the commit if one fails.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Precision**: of the things we found, the share that are real. [5.1](05-time/01-who-replaced-whom.md)

**Prometheus and Grafana**: a tool that collects live measurements, and a tool that draws them as
dashboards. [13.1](13-shipping-it/01-the-whole-stack-in-docker.md)

**Prompt**: everything handed to an LLM: instructions, source paragraphs and the question.
[1.3](01-the-idea/03-the-toolbox.md)

**Prompt injection**: hiding instructions in text a model reads so it obeys an attacker.
[11.1](11-safety-and-speed/01-guardrails-and-prompt-injection.md)

**pydantic-settings**: a library that reads settings from environment variables, converts them and
checks them. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**pyproject.toml**: the project's ID card: name, Python version, libraries and tool settings.
[2.2](02-setting-up-the-workshop/02-python-uv-and-the-lock-file.md)

**pytest**: the standard Python tool for writing and running tests.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Qdrant**: the open-source vector database RegLens uses, with dense and sparse search and filters.
[6.3](06-indexing/03-qdrant-the-searchable-shelf.md)

**RAG (retrieval-augmented generation)**: an open-book exam for an LLM: find the relevant
paragraphs, hand them over, and answer from them with citations. [1.3](01-the-idea/03-the-toolbox.md)

**Rate limit**: a cap on how often requests may be made, such as one per 1.5 seconds per website.
[3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**RBI (Reserve Bank of India)**: India's central bank, which supervises banks and NBFCs.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Recall**: of the things that exist, the share we found. [5.1](05-time/01-who-replaced-whom.md)

**Recall@10**: of the paragraphs a question needs, the share that appear in the top 10 results.
[9.1](09-evaluation/01-the-golden-set.md)

**Redis**: a very fast in-memory store, used for the semantic cache.
[11.2](11-safety-and-speed/02-faster-and-visible.md)

**Regular expression**: a pattern that matches the shape of text, such as "a day, a month name, a
year". [7.1](07-retrieval/01-reading-the-question.md)

**Relational database**: a set of linked tables, like spreadsheets. Ours is SQLite or PostgreSQL.
[5.2](05-time/02-valid-from-valid-to.md)

**Repository (repo)**: a project folder tracked by Git, with its full history.
[2.1](02-setting-up-the-workshop/01-a-home-for-the-project.md)

**Reranker**: a slower, more careful model that re-reads a shortlist and puts the best items on
top. [7.3](07-retrieval/03-a-second-closer-reading.md)

**robots.txt**: a small file a website publishes saying which pages bots may visit.
[3.1](03-the-corpus/01-collecting-the-rulebooks.md)

**Router**: a tiny model that decides what kind of question arrived: lookup, temporal, comparison
or overview. [7.1](07-retrieval/01-reading-the-question.md)

**RRF (Reciprocal Rank Fusion)**: merging ranked lists by position, so an item ranked high in both
wins. [7.2](07-retrieval/02-two-searches-and-a-fair-vote.md)

**ruff**: a very fast tool that finds likely bugs and style problems, and formats code.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**SEBI (Securities and Exchange Board of India)**: the regulator of India's securities markets.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Secret**: anything that grants access, such as an API key. Secrets never go in code or Git.
[2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Semantic cache**: a store of finished answers matched by the *meaning* of the question, plus its
date and filters. [11.2](11-safety-and-speed/02-faster-and-visible.md)

**Server-Sent Events (SSE)**: a simple standard for a server to push a series of small messages
down one open response. [8.3](08-answers/03-words-as-they-are-written.md)

**Sparse vector**: a keyword vector where most positions are zero, such as BM25's.
[6.2](06-indexing/02-meaning-and-exact-words.md)

**SQLAlchemy**: a Python library that lets the same code talk to SQLite and PostgreSQL.
[5.2](05-time/02-valid-from-valid-to.md)

**src layout**: keeping the code inside a `src/` folder so tests use it exactly as an installed
package. [2.1](02-setting-up-the-workshop/01-a-home-for-the-project.md)

**Stale in top 5**: the share of questions where a paragraph not in force on the asked date appears
in the top 5. [9.1](09-evaluation/01-the-golden-set.md)

**State**: the shared folder of facts that travels through a workflow, step to step.
[10.2](10-change-impact/02-a-workflow-that-waits-for-a-human.md)

**Streaming**: showing an answer word by word as it's written, instead of all at once.
[8.3](08-answers/03-words-as-they-are-written.md)

**Supersession**: a newer document replacing (repealing) an older one.
[1.1](01-the-idea/01-rules-that-keep-changing.md)

**Supersession graph**: dots for documents and arrows for "this one replaced that one", each with
evidence. [5.1](05-time/01-who-replaced-whom.md)

**Terraform**: a tool for writing cloud setup as code and showing what would change before it does.
[13.2](13-shipping-it/02-the-cloud-with-terraform-and-ci.md)

**Test**: a small program that checks a piece of code does what it should.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**Token**: a piece of a word, the unit LLMs read and write in, and the unit free tiers are measured
in. [2.3](02-setting-up-the-workshop/03-settings-secrets-and-logs.md)

**Trace and span**: a trace is the record of one request; a span is one step inside it, with its
input, output and duration. [11.2](11-safety-and-speed/02-faster-and-visible.md)

**Transaction**: a group of database writes that are all saved, or, on any error, none are.
[5.2](05-time/02-valid-from-valid-to.md)

**Type hint**: a short label in the code saying what kind of value goes where.
[2.4](02-setting-up-the-workshop/04-safety-nets.md)

**uv**: one fast tool that installs Python, creates virtual environments, installs libraries and
locks versions. [2.2](02-setting-up-the-workshop/02-python-uv-and-the-lock-file.md)

**Validity interval**: the window between a version's "valid from" and "valid to" dates.
[5.2](05-time/02-valid-from-valid-to.md)

**Vector**: a list of numbers. Search compares the question's vector with each chunk's.
[6.2](06-indexing/02-meaning-and-exact-words.md)

**Vector database**: a database built to find the vectors closest to a question quickly, among
those matching a filter. [6.3](06-indexing/03-qdrant-the-searchable-shelf.md)

**Virtual environment**: a private copy of Python and its libraries for one project, kept in
`.venv/`. [2.2](02-setting-up-the-workshop/02-python-uv-and-the-lock-file.md)
