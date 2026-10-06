output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "ecr_registry" {
  description = "Registry host for docker login"
  value       = split("/", values(aws_ecr_repository.this)[0].repository_url)[0]
}

output "jenkins_user_arn" {
  value = aws_iam_user.jenkins.arn
}
