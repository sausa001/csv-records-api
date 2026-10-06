variable "name" {
  description = "Prefix for resource names, e.g. peoplepulse-dev"
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name, used for subnet discovery tags"
  type        = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  description = "Availability zones to spread subnets across (2 minimum for EKS and RDS)"
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "true = one NAT gateway (cheaper, DEV); false = one per AZ (resilient, PROD)"
  type        = bool
  default     = true
}

variable "enable_flow_logs" {
  description = "Send VPC flow logs to CloudWatch (useful for security reviews; costs a little)"
  type        = bool
  default     = false
}
