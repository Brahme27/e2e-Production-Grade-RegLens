# RegLens on AWS (dev). Review with `terraform plan`; apply only when you choose to pay.
#
#   Internet -> ALB (HTTPS) -> console (Next.js, ECS Fargate)  ── /v1/* ──> API (ECS Fargate)
#   API -> Qdrant (ECS Fargate + EFS, Cloud Map DNS) · RDS Postgres · ElastiCache Redis
#   Worker: EventBridge Scheduler runs the crawl/parse/re-index task daily (ECS RunTask)
#   Secrets Manager -> injected into tasks at start · ECR · S3 (raw documents) · GitHub OIDC · Budget

locals {
  name = "reglens-${var.environment}"
  tags = {
    project     = "reglens"
    environment = var.environment
    owner       = "Brahme27"
    managed_by  = "terraform"
  }
  api_image      = "${module.ecr.repository_urls["reglens-api"]}:${var.image_tag}"
  frontend_image = "${module.ecr.repository_urls["reglens-frontend"]}:${var.image_tag}"
  app_environment = {
    REGLENS_ENV          = var.environment
    REGLENS_LOG_JSON     = "true"
    REGLENS_QDRANT_URL   = "http://qdrant.${local.name}.local:6333"
    REGLENS_REDIS_URL    = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
    REGLENS_DB_HOST      = module.rds.endpoint
    REGLENS_CORS_ORIGINS = jsonencode(["https://${var.domain_name}"])
  }
  app_secrets = {
    REGLENS_API_KEY             = module.secrets.arn_by_name["api_key"]
    REGLENS_GROQ_API_KEY        = module.secrets.arn_by_name["groq_api_key"]
    REGLENS_LANGFUSE_PUBLIC_KEY = module.secrets.arn_by_name["langfuse_public_key"]
    REGLENS_LANGFUSE_SECRET_KEY = module.secrets.arn_by_name["langfuse_secret_key"]
    # RDS-managed secret (JSON); the entrypoint builds REGLENS_DATABASE_URL from it
    REGLENS_DB_CREDENTIALS = module.rds.master_user_secret_arn
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name            = local.name
  cidr            = "10.30.0.0/16"
  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = ["10.30.1.0/24", "10.30.2.0/24"]
  public_subnets  = ["10.30.101.0/24", "10.30.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true # one NAT keeps dev cheap; one per AZ in production
}

# ---------------------------------------------------------------- security groups
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "HTTPS from the internet to the load balancer"
  vpc_id      = module.vpc.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_out" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = module.vpc.vpc_cidr_block
  ip_protocol       = "-1"
}

resource "aws_security_group" "tasks" {
  name        = "${local.name}-tasks"
  description = "ECS tasks: reachable from the ALB and from each other"
  vpc_id      = module.vpc.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "tasks_from_alb" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "tasks_from_tasks" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "-1"
}

resource "aws_vpc_security_group_egress_rule" "tasks_out" {
  security_group_id = aws_security_group.tasks.id
  cidr_ipv4         = "0.0.0.0/0" # regulator websites + Groq API via the NAT gateway
  ip_protocol       = "-1"
}

# ---------------------------------------------------------------- data stores
module "rds" {
  source                     = "../../modules/rds"
  name                       = local.name
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnets
  allowed_security_group_ids = [aws_security_group.tasks.id]
  tags                       = local.tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name}-cache"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.tasks.id]
}

resource "aws_efs_file_system" "qdrant" {
  creation_token   = "${local.name}-qdrant"
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"
  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }
}

resource "aws_efs_mount_target" "qdrant" {
  count           = length(module.vpc.private_subnets)
  file_system_id  = aws_efs_file_system.qdrant.id
  subnet_id       = module.vpc.private_subnets[count.index]
  security_groups = [aws_security_group.tasks.id]
}

resource "aws_efs_access_point" "qdrant" {
  file_system_id = aws_efs_file_system.qdrant.id
  posix_user {
    uid = 1000
    gid = 1000
  }
  root_directory {
    path = "/qdrant"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "750"
    }
  }
}

# Archive of raw regulator downloads (versioned). Today the worker keeps its HTTP cache on
# local disk; syncing it here is on the roadmap so every crawl is reproducible from S3.
module "raw_documents" {
  source      = "../../modules/s3"
  bucket_name = "${local.name}-raw-documents-${data.aws_caller_identity.current.account_id}"
  tags        = local.tags
}

module "secrets" {
  source = "../../modules/secrets"
  prefix = local.name
  tags   = local.tags
}

module "ecr" {
  source = "../../modules/ecr"
  names  = ["reglens-api", "reglens-frontend"]
  tags   = local.tags
}

# ---------------------------------------------------------------- IAM for tasks
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "read_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = concat(module.secrets.secret_arns, [module.rds.master_user_secret_arn])
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-app-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.read_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "RawDocuments"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [module.raw_documents.bucket_arn, "${module.raw_documents.bucket_arn}/*"]
  }
  statement {
    sid       = "QdrantStorage"
    actions   = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
    resources = [aws_efs_file_system.qdrant.arn]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "reglens-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# ---------------------------------------------------------------- ECS
resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = "${local.name}.local"
  vpc  = module.vpc.vpc_id
}

module "qdrant" {
  source                         = "../../modules/ecs_service"
  name                           = "qdrant"
  cluster_arn                    = aws_ecs_cluster.this.arn
  image                          = "qdrant/qdrant:${var.qdrant_version}"
  cpu                            = 512
  memory                         = 1024
  port                           = 6333
  user                           = null # the image's own user, matching the EFS access point
  subnet_ids                     = module.vpc.private_subnets
  security_group_ids             = [aws_security_group.tasks.id]
  execution_role_arn             = aws_iam_role.execution.arn
  task_role_arn                  = aws_iam_role.task.arn
  service_discovery_namespace_id = aws_service_discovery_private_dns_namespace.internal.id
  efs = {
    file_system_id  = aws_efs_file_system.qdrant.id
    access_point_id = aws_efs_access_point.qdrant.id
    container_path  = "/qdrant/storage"
  }
  tags = local.tags
}

module "api" {
  source             = "../../modules/ecs_service"
  name               = "api"
  cluster_arn        = aws_ecs_cluster.this.arn
  image              = local.api_image
  cpu                = 1024
  memory             = 2048
  port               = 8000
  environment        = local.app_environment
  secrets            = local.app_secrets
  desired_count      = var.api_desired_count
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.tasks.id]
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn
  target_group_arn   = aws_lb_target_group.api.arn
  # Cloud Map name api.<name>.local: how the console reaches the API privately
  service_discovery_namespace_id = aws_service_discovery_private_dns_namespace.internal.id
  health_check_command           = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)\""]
  tags                           = local.tags
}

module "frontend" {
  source             = "../../modules/ecs_service"
  name               = "frontend"
  cluster_arn        = aws_ecs_cluster.this.arn
  image              = local.frontend_image
  cpu                = 256
  memory             = 512
  port               = 3000
  environment        = { API_URL = "http://api.${local.name}.local:8000" }
  secrets            = { API_KEY = module.secrets.arn_by_name["api_key"] }
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.tasks.id]
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn
  target_group_arn   = aws_lb_target_group.frontend.arn
  tags               = local.tags
}

# Task definitions only: run on demand (indexer) or on a schedule (worker)
module "indexer" {
  source             = "../../modules/ecs_service"
  name               = "indexer"
  create_service     = false
  cluster_arn        = aws_ecs_cluster.this.arn
  image              = local.api_image
  cpu                = 1024
  memory             = 2048
  command            = ["sh", "-c", "python -m reglens.temporal.run && python -m reglens.index.build --variants para_ctx --no-llm"]
  environment        = local.app_environment
  secrets            = local.app_secrets
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.tasks.id]
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn
  tags               = local.tags
}

module "worker" {
  source             = "../../modules/ecs_service"
  name               = "worker"
  create_service     = false
  cluster_arn        = aws_ecs_cluster.this.arn
  image              = local.api_image
  cpu                = 2048
  memory             = 4096
  command            = ["python", "-m", "reglens.worker", "--once"]
  environment        = local.app_environment
  secrets            = local.app_secrets
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.tasks.id]
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn
  tags               = local.tags
}

# ---------------------------------------------------------------- daily crawl schedule
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = [module.worker.task_definition_arn]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "run-worker"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "daily_crawl" {
  name                         = "${local.name}-daily-crawl"
  schedule_expression          = var.crawl_schedule
  schedule_expression_timezone = "Asia/Kolkata"
  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 30
  }
  target {
    arn      = aws_ecs_cluster.this.arn
    role_arn = aws_iam_role.scheduler.arn
    ecs_parameters {
      task_definition_arn = module.worker.task_definition_arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = module.vpc.private_subnets
        security_groups  = [aws_security_group.tasks.id]
        assign_public_ip = false
      }
    }
    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}

# ---------------------------------------------------------------- CI and cost guard-rails
module "github_oidc" {
  source              = "../../modules/github_oidc"
  github_repository   = var.github_repository
  ecr_repository_arns = module.ecr.repository_arns
  ecs_cluster_arn     = aws_ecs_cluster.this.arn
  pass_role_arns      = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
  tags                = local.tags
}

module "budget" {
  source = "../../modules/budget"
  email  = var.budget_email
}
