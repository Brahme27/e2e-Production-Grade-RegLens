# 01: AWS architecture

**Folder:** `infra/terraform/envs/dev/`

```
Internet ─▶ ALB (HTTPS, TLS 1.3) ─┬─ "/"        ─▶ console  (ECS Fargate, 0.25 vCPU)
                                  └─ "/v1/*"    ─▶ api      (ECS Fargate, 1 vCPU / 2 GB)
private subnets:
  api ─▶ qdrant (ECS Fargate + EFS, Cloud Map: qdrant.reglens-dev.local)
      ─▶ RDS Postgres (encrypted, managed password)   ─▶ ElastiCache Redis
EventBridge Scheduler (06:30 IST daily) ─▶ worker task: crawl → parse → time model → re-index
Secrets Manager ─▶ injected into tasks at start      ECR · S3 (raw documents) · Budget alert
```

## Why ECS Fargate (and not Kubernetes this time)?
Project 02 (CrediSure) ran on EKS with Helm and Argo CD. RegLens is a handful of services
with no need for a cluster's operational overhead: Fargate runs containers without servers to
patch, and costs nothing when a task isn't running (the daily worker). Having one project on
each shows both skills.

## Choices worth defending
| Choice | Why |
|---|---|
| Qdrant on Fargate + EFS | Vector DB state survives task restarts; the alternative is Qdrant Cloud's free 1 GB tier (one variable) |
| Private API, reached by Cloud Map DNS | Only the ALB is public; the console's proxy talks to the API inside the VPC |
| EventBridge Scheduler → ECS RunTask | The crawler costs money only while it runs (~15 min/day) |
| Deployment circuit breaker | A release whose tasks never become healthy rolls itself back |
| One NAT gateway | Dev-grade; production would use one per AZ |
