terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

# REFERENCE ONLY: no apply, plan with credentials, or paid resource calls performed.
provider "aws" { region = var.region }
variable "region" { default = "us-east-1" }
variable "project" { default = "urbanflow-portfolio" }
variable "github_repo" { description = "Exact owner/repository for OIDC trust" }
variable "oidc_provider_arn" { description = "Existing GitHub OIDC provider ARN; never create a duplicate blindly" }
variable "private_subnets" { type = list(string) }
variable "security_groups" { type = list(string) }
variable "image_digest" { description = "Reviewed ECR image URI pinned by sha256, built for cloud runner" }

resource "aws_s3_bucket" "lake" {
  for_each      = toset(["bronze", "silver", "gold", "artifacts"])
  bucket_prefix = "${var.project}-${each.key}-"
  force_destroy = false
}
resource "aws_s3_bucket_public_access_block" "lake" {
  for_each                = aws_s3_bucket.lake
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "lake" {
  for_each = aws_s3_bucket.lake
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  for_each = aws_s3_bucket.lake
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  for_each = aws_s3_bucket.lake
  bucket   = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Deny", Principal = "*", Action = "s3:*", Resource = [each.value.arn, "${each.value.arn}/*"],
    Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}
resource "aws_glue_catalog_database" "lake" { name = replace(var.project, "-", "_") }
resource "aws_athena_workgroup" "analytics" {
  name = var.project
  configuration {
    enforce_workgroup_configuration    = true
    bytes_scanned_cutoff_per_query     = 1073741824
    publish_cloudwatch_metrics_enabled = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.lake["artifacts"].id}/athena/"
      encryption_configuration { encryption_option = "SSE_S3" }
    }
  }
}
resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/urbanflow/pipeline"
  retention_in_days = 14
}
resource "aws_sns_topic" "alerts" { name = "${var.project}-failures" }
resource "aws_ecr_repository" "pipeline" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}
resource "aws_ecs_cluster" "pipeline" { name = var.project }

locals {
  trust_ecs = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role" "execution" {
  name               = "${var.project}-execution"
  assume_role_policy = local.trust_ecs
}
resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"], Resource = aws_ecr_repository.pipeline.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.pipeline.arn}:*" }
  ] })
}
resource "aws_iam_role" "task" {
  name               = "${var.project}-task"
  assume_role_policy = local.trust_ecs
}
resource "aws_iam_role_policy" "task" {
  role = aws_iam_role.task.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [for b in aws_s3_bucket.lake : b.arn] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = [for b in aws_s3_bucket.lake : "${b.arn}/*"] },
    { Effect = "Allow", Action = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution"], Resource = aws_athena_workgroup.analytics.arn },
    { Effect = "Allow", Action = ["glue:GetDatabase", "glue:GetTable", "glue:GetTables", "glue:GetPartitions", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:BatchCreatePartition"], Resource = [aws_glue_catalog_database.lake.arn, replace(aws_glue_catalog_database.lake.arn, "database/${aws_glue_catalog_database.lake.name}", "catalog"), "${replace(aws_glue_catalog_database.lake.arn, "database/", "table/")}/*"] }
  ] })
}
resource "aws_ecs_task_definition" "pipeline" {
  family                   = var.project
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{ name = "pipeline", image = var.image_digest, essential = true,
    readonlyRootFilesystem = true,
  logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.pipeline.name, awslogs-region = var.region, awslogs-stream-prefix = "pipeline" } } }])
}
resource "aws_iam_role" "glue" {
  name               = "${var.project}-glue"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "glue.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "glue" {
  role = aws_iam_role.glue.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [for b in aws_s3_bucket.lake : b.arn] },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.lake["bronze"].arn}/*", "${aws_s3_bucket.lake["artifacts"].arn}/scripts/*"] },
    { Effect = "Allow", Action = ["s3:PutObject", "s3:DeleteObject"], Resource = ["${aws_s3_bucket.lake["silver"].arn}/*", "${aws_s3_bucket.lake["artifacts"].arn}/glue-temp/*"] },
    { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:${var.region}:*:log-group:/aws-glue/*" }
  ] })
}
resource "aws_glue_job" "silver" {
  name              = "${var.project}-silver"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  max_retries       = 0
  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.lake["artifacts"].id}/scripts/glue_etl.py"
    python_version  = "3"
  }
}
resource "aws_iam_role" "workflow" {
  name               = "${var.project}-workflow"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "states.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "workflow" {
  role = aws_iam_role.workflow.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecs:RunTask"], Resource = aws_ecs_task_definition.pipeline.arn },
    { Effect = "Allow", Action = ["ecs:StopTask", "ecs:DescribeTasks"], Resource = "arn:aws:ecs:${var.region}:*:task/${aws_ecs_cluster.pipeline.name}/*" },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.task.arn, aws_iam_role.execution.arn], Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } } },
    { Effect = "Allow", Action = ["events:PutTargets", "events:PutRule", "events:DescribeRule"], Resource = "arn:aws:events:${var.region}:*:rule/StepFunctionsGetEventsForECSTaskRule" },
    { Effect = "Allow", Action = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"], Resource = aws_glue_job.silver.arn },
    { Effect = "Allow", Action = ["sns:Publish"], Resource = aws_sns_topic.alerts.arn }
  ] })
}
locals {
  ecs_parameters = {
    LaunchType           = "FARGATE", Cluster = aws_ecs_cluster.pipeline.arn, TaskDefinition = aws_ecs_task_definition.pipeline.arn,
    NetworkConfiguration = { AwsvpcConfiguration = { Subnets = var.private_subnets, SecurityGroups = var.security_groups, AssignPublicIp = "DISABLED" } }
  }
}
resource "aws_sfn_state_machine" "pipeline" {
  name     = var.project
  role_arn = aws_iam_role.workflow.arn
  definition = jsonencode({ Comment = "Reference only: adapters and image must pass cloud-specific review before any deployment", StartAt = "Ingest", TimeoutSeconds = 7200, States = {
    Ingest = { Type = "Task", Resource = "arn:aws:states:::ecs:runTask.sync", Parameters = merge(local.ecs_parameters, { Overrides = { ContainerOverrides = [{ Name = "pipeline", Command = ["python", "-m", "cloud.runner", "ingest"] }] } }), ResultPath = "$.ingest", Next = "Silver", Catch = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Alert" }] },
    Silver = { Type = "Task", Resource = "arn:aws:states:::glue:startJobRun.sync", Parameters = { JobName = aws_glue_job.silver.name, "Arguments.$" = "$.glueArguments" }, ResultPath = "$.silver", Next = "ELT", Catch = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Alert" }] },
    ELT    = { Type = "Task", Resource = "arn:aws:states:::ecs:runTask.sync", Parameters = merge(local.ecs_parameters, { Overrides = { ContainerOverrides = [{ Name = "pipeline", Command = ["python", "-m", "cloud.runner", "dbt"] }] } }), ResultPath = "$.gold", Next = "ML", Catch = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Alert" }] },
    ML     = { Type = "Task", Resource = "arn:aws:states:::ecs:runTask.sync", Parameters = merge(local.ecs_parameters, { Overrides = { ContainerOverrides = [{ Name = "pipeline", Command = ["python", "-m", "cloud.runner", "ml"] }] } }), End = true, Catch = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Alert" }] },
    Alert  = { Type = "Task", Resource = "arn:aws:states:::sns:publish", Parameters = { TopicArn = aws_sns_topic.alerts.arn, "Message.$" = "States.JsonToString($.error)" }, Next = "Failed" },
    Failed = { Type = "Fail", Error = "PipelineFailed" }
  } })
}
resource "aws_iam_role" "schedule" {
  name               = "${var.project}-schedule"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "schedule" {
  role   = aws_iam_role.schedule.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "states:StartExecution", Resource = aws_sfn_state_machine.pipeline.arn }] })
}
resource "aws_cloudwatch_event_rule" "monthly" {
  name                = "${var.project}-monthly"
  schedule_expression = "cron(0 9 15 * ? *)"
  state               = "DISABLED"
}
resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.monthly.name
  arn      = aws_sfn_state_machine.pipeline.arn
  role_arn = aws_iam_role.schedule.arn
  input    = jsonencode({ glueArguments = { "--MONTH" = "REVIEW_REQUIRED", "--BRONZE_URI" = "REVIEW_REQUIRED", "--SILVER_URI" = "REVIEW_REQUIRED" } })
}
resource "aws_iam_role" "github" {
  name               = "${var.project}-github-validation"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRoleWithWebIdentity", Principal = { Federated = var.oidc_provider_arn }, Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com", "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:environment:reviewed-cloud" } } }] })
  # Intentionally no deployment permissions until a separate authorized cloud review.
}
