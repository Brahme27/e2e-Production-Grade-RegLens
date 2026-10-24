output "console_url" { value = "https://${var.domain_name}" }
output "alb_dns_name" {
  value       = aws_lb.this.dns_name
  description = "Point domain_name at this (CNAME / alias record)"
}
output "ecr_repositories" { value = module.ecr.repository_urls }
output "cluster_name" { value = aws_ecs_cluster.this.name }
output "indexer_task_definition" { value = module.indexer.task_definition_arn }
output "github_actions_role_arn" { value = module.github_oidc.role_arn }
output "rds_endpoint" { value = module.rds.endpoint }
