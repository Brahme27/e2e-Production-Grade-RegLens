# One container on ECS Fargate: task definition, logs and (unless it is a scheduled job)
# a long-running service, optionally behind the load balancer and/or in Cloud Map DNS.
variable "name" { type = string }
variable "cluster_arn" { type = string }
variable "image" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }

variable "port" {
  type    = number
  default = null
}

variable "command" {
  type    = list(string)
  default = null
}

variable "environment" {
  type    = map(string)
  default = {}
}

variable "secrets" {
  type        = map(string)
  default     = {}
  description = "ENV_VAR_NAME => Secrets Manager ARN (injected at start, never in the task definition)"
}

variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }

variable "desired_count" {
  type    = number
  default = 1
}

variable "create_service" {
  type        = bool
  default     = true
  description = "false = task definition only (run on a schedule or by hand)"
}

variable "target_group_arn" {
  type    = string
  default = null
}

variable "service_discovery_namespace_id" {
  type    = string
  default = null
}

variable "efs" {
  type = object({
    file_system_id  = string
    access_point_id = string
    container_path  = string
  })
  default = null
}

variable "health_check_command" {
  type    = list(string)
  default = null
}

variable "user" {
  type        = string
  default     = "10001"
  description = "UID the container runs as (null = the image default, e.g. Qdrant)"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

locals {
  container = merge(
    {
      name        = var.name
      image       = var.image
      essential   = true
      environment = [for k, v in var.environment : { name = k, value = v }]
      secrets     = [for k, v in var.secrets : { name = k, valueFrom = v }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = var.name
        }
      }
      readonlyRootFilesystem = false
    },
    var.user == null ? {} : { user = var.user },
    var.port == null ? {} : { portMappings = [{ containerPort = var.port, protocol = "tcp" }] },
    var.command == null ? {} : { command = var.command },
    var.health_check_command == null ? {} : {
      healthCheck = { command = var.health_check_command, interval = 15, timeout = 5, retries = 3, startPeriod = 60 }
    },
    var.efs == null ? {} : { mountPoints = [{ sourceVolume = "data", containerPath = var.efs.container_path, readOnly = false }] },
  )
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions    = jsonencode([local.container])

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  dynamic "volume" {
    for_each = var.efs == null ? [] : [var.efs]
    content {
      name = "data"
      efs_volume_configuration {
        file_system_id     = volume.value.file_system_id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = volume.value.access_point_id
          iam             = "ENABLED"
        }
      }
    }
  }
  tags = var.tags
}

resource "aws_service_discovery_service" "this" {
  count = var.create_service && var.service_discovery_namespace_id != null ? 1 : 0
  name  = var.name

  dns_config {
    namespace_id   = var.service_discovery_namespace_id
    routing_policy = "MULTIVALUE"
    dns_records {
      type = "A"
      ttl  = 10
    }
  }
}

resource "aws_ecs_service" "this" {
  count                  = var.create_service ? 1 : 0
  name                   = var.name
  cluster                = var.cluster_arn
  task_definition        = aws_ecs_task_definition.this.arn
  desired_count          = var.desired_count
  launch_type            = "FARGATE"
  enable_execute_command = false
  propagate_tags         = "SERVICE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn == null ? [] : [var.target_group_arn]
    content {
      target_group_arn = load_balancer.value
      container_name   = var.name
      container_port   = var.port
    }
  }

  dynamic "service_registries" {
    for_each = aws_service_discovery_service.this
    content {
      registry_arn = service_registries.value.arn
    }
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true # a release that never becomes healthy rolls itself back
  }

  lifecycle {
    ignore_changes = [desired_count] # autoscaling owns it once enabled
  }
  tags = var.tags
}

output "task_definition_arn" { value = aws_ecs_task_definition.this.arn }
output "service_name" { value = var.create_service ? aws_ecs_service.this[0].name : null }
output "log_group" { value = aws_cloudwatch_log_group.this.name }
