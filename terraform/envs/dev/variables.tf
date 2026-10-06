variable "project" {
  type    = string
  default = "peoplepulse"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "us-west-1"
}

variable "aws_account_id" {
  description = "The only AWS account this code may touch"
  type        = string
  default     = "866934333672"
}

variable "owner" {
  description = "Owner tag on every resource: lets Cost Explorer and Budgets show the cost you generated"
  type        = string
  default     = "Saket.Saurabh@techconsulting.net"
}

# ---------- network ----------
variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  description = "us-west-1 offers only 2 Availability Zones to most accounts"
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3 (EKS and RDS need at least 2; us-west-1 usually has only 2)."
  }
}

variable "single_nat_gateway" {
  type    = bool
  default = true
}

variable "enable_flow_logs" {
  type    = bool
  default = false
}

# ---------- EKS ----------
variable "kubernetes_version" {
  description = "Check: aws eks describe-cluster-versions --default-only"
  type        = string
  default     = "1.35"
}

variable "eks_public_access_cidrs" {
  description = "Your public IP as x.x.x.x/32 (curl -s https://checkip.amazonaws.com)"
  type        = list(string)
  validation {
    condition     = length(var.eks_public_access_cidrs) > 0 && alltrue([for c in var.eks_public_access_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0"])
    error_message = "Set eks_public_access_cidrs in terraform.tfvars to your public IP, e.g. [\"203.0.113.10/32\"] (curl -s https://checkip.amazonaws.com)."
  }
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t4g.medium"]
}

variable "node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "node_desired" {
  type    = number
  default = 2
}

variable "admin_principal_arns" {
  description = "Extra IAM principals with cluster-admin (the user running apply already has it)"
  type        = list(string)
  default     = []
}

# ---------- RDS ----------
variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "db_deletion_protection" {
  type    = bool
  default = false
}

# ---------- DNS / HTTPS (optional) ----------
variable "domain_name" {
  description = "A public Route 53 hosted zone you own, e.g. example.com. Empty = no DNS/HTTPS."
  type        = string
  default     = ""
}

variable "subdomain" {
  description = "App hostname becomes <subdomain>.<domain_name>"
  type        = string
  default     = "peoplepulse-dev"
}

variable "alb_ready" {
  description = "Set true AFTER the first app deploy created the ALB: adds the DNS record and ALB alarms"
  type        = bool
  default     = false
}

# ---------- monitoring ----------
variable "alarm_email" {
  description = "Email for CloudWatch alarm notifications (confirm the subscription email). Empty = none."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly AWS Budget on resources tagged Owner=<owner>; emails alarm_email at 80% actual and 100% forecast"
  type        = number
  default     = 100
}
