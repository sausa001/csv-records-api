# DEV settings - edit these, then: terraform plan / terraform apply
# Account 866934333672, region us-west-1 (N. California).
# This account is the AWS CLI profile PC1. In every new terminal, first run:
#   export AWS_PROFILE=PC1 && aws sts get-caller-identity    # Account must be 866934333672

# REQUIRED: your public IP so only you can reach the Kubernetes API
#   curl -s https://checkip.amazonaws.com
eks_public_access_cidrs = ["223.181.24.148/32"]

kubernetes_version = "1.35" # confirm: aws eks describe-cluster-versions --default-only --region us-west-1
# us-west-1 offers 2 Availability Zones to most accounts: keep az_count at its default of 2
node_instance_types = ["t4g.medium"]
node_capacity_type  = "ON_DEMAND" # SPOT is cheaper for DEV, but nodes can be reclaimed
node_desired        = 2

db_instance_class      = "db.t4g.micro"
db_multi_az            = false
db_deletion_protection = false

# Optional HTTPS + DNS: a public hosted zone you own in Route 53
domain_name = "" # e.g. "example.com"
subdomain   = "peoplepulse-dev"
alb_ready   = false # set true after the first app deploy (creates DNS record + ALB alarm)

alarm_email = "" # e.g. "Saket.Saurabh@techconsulting.net" (also receives the budget emails)

# Cost tracking: every resource is tagged Owner=<owner>; the budget watches that tag
owner              = "Saket.Saurabh@techconsulting.net"
monthly_budget_usd = 100

# Optional: e-mail for every new employee (SNS, filtered to record.created). Empty = none.
new_employee_email = ""
