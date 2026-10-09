output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "app_namespace" {
  value = local.app_namespace
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "nat_public_ips" {
  value = module.network.nat_public_ips
}

output "db_host" {
  value = module.rds.address
}

output "db_secret_arn" {
  value = module.rds.master_secret_arn
}

output "alb_controller_role_arn" {
  value = module.eks.alb_controller_role_arn
}

output "app_url" {
  value = local.app_host == "" ? "ALB DNS name: kubectl -n ${local.app_namespace} get ingress" : "https://${local.app_host}"
}

output "settings_path" {
  description = "SSM Parameter Store path the pipeline reads"
  value       = local.ssm_prefix
}

output "events_topic_arn" {
  value = aws_sns_topic.events.arn
}

output "events_queue_url" {
  value = aws_sqs_queue.events.url
}
