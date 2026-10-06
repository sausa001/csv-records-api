variable "cluster_name" {
  type = string
}

variable "kubernetes_version" {
  description = "Pick a version in STANDARD support: aws eks describe-cluster-versions --default-only"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "Worker nodes and pods live here"
  type        = list(string)
}

variable "public_access_cidrs" {
  description = "Who may reach the Kubernetes API from the internet. Set to your own IP (x.x.x.x/32)."
  type        = list(string)
}

variable "node_instance_types" {
  description = "Graviton (arm64) instances: cheaper, and run the arm64 images built on Apple Silicon"
  type        = list(string)
  default     = ["t4g.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND, or SPOT for cheaper (interruptible) DEV nodes"
  type        = string
  default     = "ON_DEMAND"
}

variable "node_desired" {
  type    = number
  default = 2
}

variable "node_min" {
  type    = number
  default = 1
}

variable "node_max" {
  type    = number
  default = 3
}

variable "admin_principal_arns" {
  description = "IAM users/roles that get full cluster-admin (you)"
  type        = list(string)
  default     = []
}

variable "deployer_principal_arn" {
  description = "IAM principal used by Jenkins; gets edit rights in the app namespace only"
  type        = string
  default     = ""
}

variable "app_namespace" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 14
}
