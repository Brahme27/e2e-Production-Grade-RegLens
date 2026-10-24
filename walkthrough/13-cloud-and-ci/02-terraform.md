# 02: Terraform

**Folder:** `infra/terraform/`

## Layout
| Module | Creates |
|---|---|
| `ecs_service` (new) | Task definition, log group, optional service, ALB attachment, Cloud Map name and EFS volume. Used five times: api, console, qdrant, indexer, worker |
| `rds` | Postgres 16, encrypted, private, password managed by AWS |
| `secrets` | Containers for the API key, Groq key and Langfuse keys (values set out-of-band) |
| `ecr` | Image repositories: immutable tags, scan on push |
| `s3` | Versioned, encrypted, private bucket for raw documents |
| `github_oidc` | A role GitHub Actions can assume **without stored keys**: push images, roll out ECS services in this cluster only |
| `budget` | A monthly cost alarm by email |

## Secrets never touch Terraform state
Terraform creates the secret *containers*; their values are set in the console or CLI.
ECS injects them into the containers at start (`secrets = { REGLENS_GROQ_API_KEY = arn }`).
The database password is generated and rotated by RDS itself; the app builds its connection
string from that managed secret at start-up.

## How to use it (when you choose to pay)
```bash
cd infra/terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars   # domain, ACM certificate, repo, email
terraform init && terraform plan               # review every resource first
```
Validated in CI with `terraform fmt -check` and `terraform validate`; never applied here.
