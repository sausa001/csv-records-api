locals {
  name          = "${var.project}-${var.environment}" # peoplepulse-dev
  cluster_name  = local.name
  app_namespace = local.name
  ssm_prefix    = "/${var.project}/${var.environment}"
  app_host      = var.domain_name == "" ? "" : "${var.subdomain}.${var.domain_name}"
}

data "aws_caller_identity" "current" {}

# Created in ../../shared
data "aws_iam_user" "jenkins" {
  user_name = "peoplepulse-jenkins"
}

data "aws_ecr_repository" "api" {
  name = "peoplepulse-api"
}

data "aws_ecr_repository" "ui" {
  name = "peoplepulse-ui"
}

# =====================================================================
# 1. Networking
# =====================================================================
module "network" {
  source             = "../../modules/network"
  name               = local.name
  cluster_name       = local.cluster_name
  vpc_cidr           = var.vpc_cidr
  az_count           = var.az_count
  single_nat_gateway = var.single_nat_gateway
  enable_flow_logs   = var.enable_flow_logs
}

# =====================================================================
# 2. EKS
# =====================================================================
module "eks" {
  source                 = "../../modules/eks"
  cluster_name           = local.cluster_name
  kubernetes_version     = var.kubernetes_version
  vpc_id                 = module.network.vpc_id
  private_subnet_ids     = module.network.private_subnet_ids
  public_access_cidrs    = var.eks_public_access_cidrs
  node_instance_types    = var.node_instance_types
  node_capacity_type     = var.node_capacity_type
  node_desired           = var.node_desired
  admin_principal_arns   = var.admin_principal_arns
  deployer_principal_arn = data.aws_iam_user.jenkins.arn
  app_namespace          = local.app_namespace
}

# =====================================================================
# 3. RDS PostgreSQL
# =====================================================================
module "rds" {
  source                     = "../../modules/rds"
  name                       = local.name
  vpc_id                     = module.network.vpc_id
  database_subnet_ids        = module.network.database_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_security_group_id]
  instance_class             = var.db_instance_class
  multi_az                   = var.db_multi_az
  deletion_protection        = var.db_deletion_protection
}

# =====================================================================
# 4. HTTPS certificate (only when a domain is configured)
# =====================================================================
data "aws_route53_zone" "this" {
  count        = var.domain_name == "" ? 0 : 1
  name         = var.domain_name
  private_zone = false
}

resource "aws_acm_certificate" "app" {
  count             = var.domain_name == "" ? 0 : 1
  domain_name       = local.app_host
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "cert_validation" {
  for_each = var.domain_name == "" ? {} : {
    for o in aws_acm_certificate.app[0].domain_validation_options : o.domain_name => o
  }
  zone_id         = data.aws_route53_zone.this[0].zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "app" {
  count                   = var.domain_name == "" ? 0 : 1
  certificate_arn         = aws_acm_certificate.app[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# =====================================================================
# 5. After the first deploy: DNS name -> ALB (the ALB is created by Kubernetes)
# =====================================================================
data "aws_lb" "app" {
  count = var.alb_ready ? 1 : 0
  tags = {
    "elbv2.k8s.aws/cluster" = local.cluster_name
    Environment             = var.environment
  }
}

resource "aws_route53_record" "app" {
  count   = var.alb_ready && var.domain_name != "" ? 1 : 0
  zone_id = data.aws_route53_zone.this[0].zone_id
  name    = local.app_host
  type    = "A"
  alias {
    name                   = data.aws_lb.app[0].dns_name
    zone_id                = data.aws_lb.app[0].zone_id
    evaluate_target_health = true
  }
}

# =====================================================================
# 6. Settings for the pipeline (Jenkins reads these; nothing is hard-coded)
# =====================================================================
resource "aws_ssm_parameter" "settings" {
  for_each = {
    cluster_name    = module.eks.cluster_name
    namespace       = local.app_namespace
    db_host         = module.rds.address
    db_name         = module.rds.db_name
    db_user         = module.rds.username
    db_secret_arn   = module.rds.master_secret_arn
    ecr_api         = data.aws_ecr_repository.api.repository_url
    ecr_ui          = data.aws_ecr_repository.ui.repository_url
    app_host        = local.app_host == "" ? "none" : local.app_host
    certificate_arn = var.domain_name == "" ? "none" : aws_acm_certificate_validation.app[0].certificate_arn
  }
  name  = "${local.ssm_prefix}/${each.key}"
  type  = "String"
  value = each.value
}

# =====================================================================
# 7. What Jenkins may do in THIS environment (ECR push is granted in shared/)
# =====================================================================
data "aws_iam_policy_document" "jenkins_env" {
  statement {
    sid       = "DescribeCluster"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${local.cluster_name}"]
  }
  statement {
    sid       = "ReadSettings"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}*"]
  }
  statement {
    sid       = "ReadDbPassword"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [module.rds.master_secret_arn]
  }
}

resource "aws_iam_group_policy" "jenkins_env" {
  name   = "deploy-${var.environment}"
  group  = "peoplepulse-jenkins" # created in ../../shared
  policy = data.aws_iam_policy_document.jenkins_env.json
}

# =====================================================================
# 8. Monitoring: alarms -> SNS -> email
# =====================================================================
# Cost budget for everything tagged Owner=<owner> (needs the Owner cost allocation tag activated in Billing)
resource "aws_budgets_budget" "owner_monthly" {
  count        = var.alarm_email == "" ? 0 : 1
  name         = "${local.name}-owner-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:Owner$%s", var.owner)]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alarm_email]
  }
}

resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "db_cpu" {
  alarm_name          = "${local.name}-rds-cpu-high"
  alarm_description   = "RDS CPU above 80% for 10 minutes"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = { DBInstanceIdentifier = module.rds.identifier }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "db_storage" {
  alarm_name          = "${local.name}-rds-storage-low"
  alarm_description   = "RDS free storage below 2 GB"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = module.rds.identifier }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 2147483648
  comparison_operator = "LessThanThreshold"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "node_cpu" {
  alarm_name          = "${local.name}-eks-node-cpu-high"
  alarm_description   = "Average EKS node CPU above 80% for 10 minutes (Container Insights)"
  namespace           = "ContainerInsights"
  metric_name         = "node_cpu_utilization"
  dimensions          = { ClusterName = module.eks.cluster_name }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  count               = var.alb_ready ? 1 : 0
  alarm_name          = "${local.name}-alb-5xx"
  alarm_description   = "More than 10 server errors (5xx) from the app in 5 minutes"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = data.aws_lb.app[0].arn_suffix }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
