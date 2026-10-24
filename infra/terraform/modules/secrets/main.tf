# Application secrets. Terraform creates the containers only; values are set out-of-band
# (console/CLI) so they never land in Terraform state or Git.
variable "prefix" { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  secrets = {
    api_key             = "X-API-Key required by the RegLens API (also given to the console's proxy)"
    groq_api_key        = "Groq key for the open-weight LLMs (answers, obligations, gap judge)"
    langfuse_public_key = "Langfuse public key (tracing); optional"
    langfuse_secret_key = "Langfuse secret key (tracing); optional"
  }
}

resource "aws_secretsmanager_secret" "this" {
  for_each    = local.secrets
  name        = "${var.prefix}/${replace(each.key, "_", "-")}"
  description = each.value
  tags        = var.tags
}

output "secret_arns" {
  value = [for s in aws_secretsmanager_secret.this : s.arn]
}

output "arn_by_name" {
  value = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}
