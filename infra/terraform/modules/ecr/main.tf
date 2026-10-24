# Private container registries for the API and console images.
variable "names" {
  type        = list(string)
  description = "Repository names, e.g. [\"reglens-api\", \"reglens-frontend\"]"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(var.names)
  name                 = each.value
  image_tag_mutability = "IMMUTABLE" # a tag always means the same image (audit trail)
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true # vulnerability scan on every push
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 30 most recent images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 30 }
      action       = { type = "expire" }
    }]
  })
}

output "repository_urls" {
  value = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "repository_arns" {
  value = [for r in aws_ecr_repository.this : r.arn]
}
