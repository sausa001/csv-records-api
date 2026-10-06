variable "name" {
  description = "Identifier prefix, e.g. peoplepulse-dev"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "database_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups allowed to connect on 5432 (the EKS cluster security group)"
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL major version; RDS picks the current default minor"
  type        = string
  default     = "16"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling (GB)"
  type        = number
  default     = 50
}

variable "db_name" {
  type    = string
  default = "records"
}

variable "username" {
  type    = string
  default = "app"
}

variable "multi_az" {
  description = "Standby copy in a second AZ (PROD); roughly doubles the cost"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  description = "true for PROD; false lets DEV be destroyed"
  type        = bool
  default     = false
}
