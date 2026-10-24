variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai; eu-west-2 (London) works the same way
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "image_tag" {
  type        = string
  description = "Image tag to deploy (CI passes the git SHA; ECR tags are immutable)"
  default     = "latest"
}

variable "domain_name" {
  type        = string
  description = "Public hostname of the console, e.g. reglens.example.com"
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate for domain_name, in the same region"
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "qdrant_version" {
  type    = string
  default = "v1.16.2"
}

variable "crawl_schedule" {
  type        = string
  description = "When the worker re-crawls the regulators (EventBridge Scheduler expression)"
  default     = "cron(30 6 * * ? *)" # 06:30 IST daily, after regulators' overnight publishing
}

variable "github_repository" {
  type        = string
  description = "owner/repo allowed to deploy via GitHub Actions OIDC"
}

variable "budget_email" {
  type        = string
  description = "Where AWS Budgets sends cost alerts"
}
