variable "region" {
  type    = string
  default = "us-west-1"
}

variable "aws_account_id" {
  description = "The only AWS account this code may touch"
  type        = string
  default     = "866934333672"
}

variable "repositories" {
  description = "ECR repositories, one per container image"
  type        = list(string)
  default     = ["peoplepulse-api", "peoplepulse-ui"]
}

variable "images_to_keep" {
  description = "Most recent images kept per repository; older ones are deleted"
  type        = number
  default     = 30
}

variable "owner" {
  description = "Owner tag on every resource: lets Cost Explorer and Budgets show the cost you generated"
  type        = string
  default     = "Saket.Saurabh@techconsulting.net"
}
