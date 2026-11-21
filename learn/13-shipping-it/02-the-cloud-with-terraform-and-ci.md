[RegLens guide](../README.md) › Part 13: Shipping it

# 13.2 The cloud with Terraform, and CI

In the [last chapter](01-the-whole-stack-in-docker.md) the whole system started on one laptop with
one command. A real bank wouldn't run it on a laptop. In this chapter we write down, as code, how
RegLens would run on AWS, and we let CI guard both the code and the quality numbers. One honest
note up front: the cloud files are **checked but never applied**. The project deliberately stays
at zero cloud spend.

## Writing the cloud down as code

You could set up cloud servers by clicking through the AWS website. It works once, but nobody can
review it, repeat it exactly, or see what changed. **Infrastructure as code** means describing the
cloud setup in text files instead, kept in Git like any other code. Think of an architect's
drawings: the building can be built again from them, and every change to the plan is visible.

We use **Terraform**, the most widely used tool for this. You describe what you want; `terraform
plan` shows exactly what it would create or change; and only an explicit apply step creates it.
AWS's own tool, CloudFormation, works only on AWS, while Terraform skills carry over to other
clouds.

## The design on AWS

```
Internet ─▶ load balancer (HTTPS) ─┬─ "/"     ─▶ console (container)
                                   └─ "/v1/*" ─▶ API     (container)
private network:  API ─▶ Qdrant (container + network disk)
                      ─▶ PostgreSQL (managed)  ─▶ Redis (managed)
daily schedule (06:30 IST) ─▶ worker: crawl → parse → dates → re-index
```

The containers run on **ECS Fargate**, an AWS service that runs containers without you managing any
servers, and charges only while they run. A **load balancer** is the front door that receives
traffic and passes it to the right container. Qdrant keeps its data on a network disk so it
survives restarts. PostgreSQL and Redis are managed by AWS, so backups and patching aren't our job.
Only the load balancer is public; the API sits on a private network that only the console can reach.
Each morning a scheduler starts the worker, which re-crawls the regulators, re-parses, recomputes
dates and re-indexes: about 15 minutes of paid time a day. If a new release never becomes healthy,
it rolls itself back.

Why Fargate and not Kubernetes? The CrediSure project already runs on Kubernetes. RegLens is a
handful of services with no need for a cluster to look after, and showing both is part of the
point of the portfolio.

The Terraform code is split into small reusable **modules**: one for a container service (used five
times: API, console, Qdrant, indexer, worker), and others for the database, secret containers,
image storage, document storage, a monthly budget alarm, and a role that lets GitHub deploy
**without any stored keys**. Secrets are injected into containers when they start, and their values
are never written into Terraform's own records, which can leak.

## CI, now with a quality gate

The referee from chapter 2.4 grew up with the project. On **every change**, three jobs run in
minutes: the Python checks and tests (no internet, no keys, models faked, LLM answers replayed),
the console's lint and production build, and Terraform's format check and validation.

On the main branch, **once a week**, and on demand, a heavier job of about an hour runs:

1. **Rebuild everything from the regulators' websites**: crawl (politely, with a cache), parse,
   dates, the serving index and the router. LLM steps replay the notebook, so it's free and gives
   the same result every time.
2. **The quality gate** from chapter 9.2: re-score the production row against the saved baseline,
   and fail if quality drops by more than 0.03 or any out-of-date paragraph reaches the top 5.
3. **Build both images** and scan the API image for known security holes with **Trivy**.
4. **Start the stack and run a smoke test**: health, the API key, the corpus loaded, a cited
   answer, the stream, an injection refused, a repealed rule marked superseded, and the console's
   proxy.

Why weekly? Regulators edit their websites. A weekly fresh crawl catches a broken parser before a
user does, and turns "the numbers in the README" into a promise the code must keep.

> **Try it:** run `uv run poe worker`. It does one cycle of what the daily cloud task does: crawl
> (politely, reusing saved copies), parse, recompute dates and re-index. At the end it logs which
> document versions are new or changed, judged by their fingerprints from chapter 3.1.

*Want the details? See `walkthrough/13-cloud-and-ci/`, `infra/terraform/` and
`.github/workflows/ci.yml`.*

So far: RegLens is written down for AWS as code, validated on every change, and rebuilt from the
real websites every week behind a quality gate. Next, we step back and ask how good it really is.

**Next →** [14.1 Results and weak spots](../14-the-finish-line/01-results-and-weak-spots.md)
