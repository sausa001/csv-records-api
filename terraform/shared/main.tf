# Resources shared by every environment (DEV / UAT / PROD use the same images).

# ---------- ECR: private image registry ----------
resource "aws_ecr_repository" "this" {
  for_each             = toset(var.repositories)
  name                 = each.value
  image_tag_mutability = "IMMUTABLE" # a tag can never be overwritten: jenkins-<build>-<sha> is unique
  force_delete         = false

  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the newest ${var.images_to_keep} images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = var.images_to_keep }
      action       = { type = "expire" }
    }]
  })
}

# ---------- IAM for Jenkins (runs on a laptop, so it needs access keys) ----------
# Permissions live on a GROUP; the user is a member. Each environment adds its own
# group policy (see envs/<env>/main.tf). Create the user's access key yourself in the
# console (IAM > Users > peoplepulse-jenkins > Security credentials) so the secret
# never lands in Terraform state.
resource "aws_iam_group" "jenkins" {
  name = "peoplepulse-jenkins"
}

resource "aws_iam_user" "jenkins" {
  name = "peoplepulse-jenkins"
}

resource "aws_iam_user_group_membership" "jenkins" {
  user   = aws_iam_user.jenkins.name
  groups = [aws_iam_group.jenkins.name]
}

data "aws_iam_policy_document" "jenkins_ecr" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
      "ecr:DescribeImages", "ecr:DescribeRepositories", "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart",
    ]
    resources = [for r in aws_ecr_repository.this : r.arn]
  }
}

resource "aws_iam_group_policy" "jenkins_ecr" {
  name   = "ecr-push"
  group  = aws_iam_group.jenkins.name
  policy = data.aws_iam_policy_document.jenkins_ecr.json
}
