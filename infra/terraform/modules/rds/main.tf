# Managed PostgreSQL for document versions, supersession edges, obligations and reviews.
variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security groups allowed to reach Postgres (the ECS tasks)"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro" # free-tier eligible
}

variable "multi_az" {
  type    = bool
  default = false # true in production
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "Postgres access from the ECS tasks only"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "from_tasks" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class
  db_name        = "reglens"
  username       = "reglens"
  # AWS generates and rotates the password in Secrets Manager - it never appears in Terraform state.
  manage_master_user_password = true

  allocated_storage            = 20
  max_allocated_storage        = 100
  storage_encrypted            = true
  multi_az                     = var.multi_az
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [aws_security_group.db.id]
  publicly_accessible          = false
  backup_retention_period      = 7
  deletion_protection          = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${var.name}-final"
  performance_insights_enabled = false # not available on the smallest (free-tier) classes
  tags                         = var.tags
}

output "endpoint" { value = aws_db_instance.this.address }
output "master_user_secret_arn" { value = aws_db_instance.this.master_user_secret[0].secret_arn }
