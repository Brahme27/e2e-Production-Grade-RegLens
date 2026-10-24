# Phase 13: Cloud deployment files and CI

Everything needed to run RegLens on AWS is written as code and validated, but **not applied**
(the project deliberately stays at zero cloud spend).

| Chunk | What happens |
|---|---|
| [01-aws-architecture.md](01-aws-architecture.md) | ECS Fargate, ALB, RDS, ElastiCache, EFS-backed Qdrant, EventBridge Scheduler |
| [02-terraform.md](02-terraform.md) | Modules, secrets that never touch state, least-privilege IAM |
| [03-ci.md](03-ci.md) | Lint, types, tests, console build, Terraform validate, then a weekly full rebuild with a quality gate |
