[RegLens guide](../README.md) › Part 13: Shipping it

# 13.1 The whole stack in Docker

In [Part 12](../12-the-api-and-console/01-the-api-and-the-console.md) we built the API and the
console. On the laptop, each piece runs in its own way: the database is a file, the search index
is a folder, the cache lives inside the program. Production looks different. In this chapter we pack
every piece into containers and run the whole system the way a real deployment would.

## Boxes that run the same everywhere

A **container** is a sealed box holding an application plus everything it needs: the right Python,
the libraries, the model files, the data. It runs the same on any machine that can run containers.
The recipe for a box is an **image**, and a running copy of it is a container. **Docker** is the
standard tool for building and running them. Think of a food truck stocked at the depot: everything
for the day's menu is on board, so service starts the moment it parks.

The RegLens API image is built in two stages. The first installs only the **runtime** libraries
from the lock file. The second copies in what's needed to answer questions on day one:

- the parsed documents, validity dates and supersession arrows;
- the test firms' policies, the settings and the golden set;
- the trained router and the evaluation reports for the console;
- the saved vectors, so the search index loads in seconds instead of re-embedding for minutes;
- the LLM notebook, so the demo works even without a Groq key;
- the three small models (about 150 MB), so nothing downloads at start-up.

Left out: the large reranker we rejected in Part 7, the raw downloads, test tools and tests. The
container also runs as an ordinary user rather than the all-powerful "root", checks its own health,
and limits how many processor cores the models may grab. The same image runs three ways: as the
API, as a one-shot indexer, and as a scheduled worker that re-crawls.

## The whole kitchen with one command

**Docker compose** describes several containers and how they connect in one file, and starts them
all with one command:

```
postgres ─┐
qdrant ───┼─▶ indexer (runs once, then exits) ─▶ api ─▶ frontend
redis ────┘
optional: worker (daily re-crawl) · prometheus + grafana (monitoring)
```

PostgreSQL holds versions, arrows, obligations, reviews and feedback. Qdrant runs as a real server.
Redis holds the semantic cache. The **indexer** loads the dates into PostgreSQL and the search index
into Qdrant from the saved vectors, then exits. The API starts **only after the indexer has finished
successfully**, so it never serves an empty index. The console starts once the API is healthy.

It's like opening a restaurant: deliveries arrive, the kitchen is stocked, and only then do the
doors open. Each service also has a memory cap, so no single piece can starve the others. An
optional monitoring profile adds **Prometheus**, which collects live measurements such as answer
times and how often RegLens declines, and **Grafana**, which draws them as dashboards with alerts.

> **Try it:** run `uv run poe pipeline` once to build the corpus and indexes, then
> `docker compose up -d --build` (or `uv run poe up`). When it settles, the console is at
> `http://localhost:3000` and the API's documentation page at `http://localhost:8000/docs`. With the
> stack running, `uv run poe e2e` clicks through the console, and `uv run poe down` stops everything.

> **A bump on the road:** the first time the full stack ran in Docker, five problems appeared while
> all of our unit tests were green. One example: saving an impact run failed because a judgement
> was written before the obligation it points to. PostgreSQL enforces such links between tables;
> SQLite, which our tests used, quietly ignores them unless asked. One line made SQLite strict too,
> the tests failed the same way, and then the fix made them pass. Another: rebuilding "the API"
> rebuilt nothing, because only the indexer's entry said how to build the shared image, so the API
> kept running old code while we debugged a bug we'd already fixed. The lesson: unit tests use
> forgiving stand-ins. Run the real thing, like a dress rehearsal on the real stage, and after a
> rebuild, prove the container has the new code before debugging further.

*Want the details? See `walkthrough/12-docker/`, `Dockerfile` and `docker-compose.yml`.*

So far: the whole system, databases included, starts on one laptop with one command, the way
production would run it. Next, we write down how it would run in the cloud, and let CI guard it.

**Next →** [13.2 The cloud with Terraform, and CI](02-the-cloud-with-terraform-and-ci.md)
