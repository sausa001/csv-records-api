# =====================================================================
# 9. Domain events: API -> SNS topic -> SQS queue (+ DLQ) -> worker
#    record.created / record.updated / record.deleted
# =====================================================================
locals {
  events_name = "${local.name}-employee-events"
}

# ---------- SNS topic ----------
resource "aws_sns_topic" "events" {
  name              = local.events_name
  kms_master_key_id = "alias/aws/sns" # encrypted at rest with the AWS-managed key
}

# Optional: an e-mail for every new employee (only record.created, thanks to the filter)
resource "aws_sns_topic_subscription" "new_employee_email" {
  count         = var.new_employee_email == "" ? 0 : 1
  topic_arn     = aws_sns_topic.events.arn
  protocol      = "email"
  endpoint      = var.new_employee_email
  filter_policy = jsonencode({ event = ["record.created"] })
}

# ---------- SQS queue + dead-letter queue ----------
resource "aws_sqs_queue" "events_dlq" {
  name                      = "${local.events_name}-dlq"
  message_retention_seconds = 1209600 # 14 days to investigate
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "events" {
  name                       = local.events_name
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # long polling
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.events_dlq.arn
    maxReceiveCount     = 5
  })
}

# Only this SNS topic may send to the queue
data "aws_iam_policy_document" "events_queue" {
  statement {
    sid       = "AllowEventsTopic"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.events.arn]
    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.events.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "events" {
  queue_url = aws_sqs_queue.events.id
  policy    = data.aws_iam_policy_document.events_queue.json
}

resource "aws_sns_topic_subscription" "events_queue" {
  topic_arn            = aws_sns_topic.events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.events.arn
  raw_message_delivery = true # the worker receives the event JSON itself
  depends_on           = [aws_sqs_queue_policy.events]
}

# ---------- IAM for the pods (EKS Pod Identity) ----------
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# API pods: publish to the topic only
data "aws_iam_policy_document" "api_events" {
  statement {
    sid       = "PublishEvents"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.events.arn]
  }
  statement {
    sid       = "UseSnsKey"
    actions   = ["kms:GenerateDataKey*", "kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["sns.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

resource "aws_iam_role_policy" "api_events" {
  name   = "publish-events"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_events.json
}

resource "aws_eks_pod_identity_association" "api" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.app_namespace
  service_account = "peoplepulse-api" # created by the Helm chart (release "peoplepulse")
  role_arn        = aws_iam_role.api.arn
}

# Worker pods: read and delete from the queue only
data "aws_iam_policy_document" "worker_events" {
  statement {
    sid = "ConsumeEvents"
    actions = [
      "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes", "sqs:GetQueueUrl",
    ]
    resources = [aws_sqs_queue.events.arn]
  }
}

resource "aws_iam_role" "worker" {
  name               = "${local.name}-worker"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

resource "aws_iam_role_policy" "worker_events" {
  name   = "consume-events"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker_events.json
}

resource "aws_eks_pod_identity_association" "worker" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.app_namespace
  service_account = "peoplepulse-worker"
  role_arn        = aws_iam_role.worker.arn
}

# ---------- alarm: anything in the dead-letter queue needs a look ----------
resource "aws_cloudwatch_metric_alarm" "events_dlq" {
  alarm_name          = "${local.name}-events-dlq-not-empty"
  alarm_description   = "Employee events failed 5 times and landed in the dead-letter queue"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.events_dlq.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
