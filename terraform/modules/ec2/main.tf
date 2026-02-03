locals {
  ami_id = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu.id

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Module      = "EC2"
  }

  hostname-tag = "${var.project_name}-${var.environment}"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  owners = ["576771098395"]
}

resource "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_instance" "ec2_instance" {
  ami                         = local.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_ids[count.index % length(var.subnet_ids)]
  security_groups             = var.security_group_ids
  associate_public_ip_address = true
  key_name                    = var.key_name
  iam_instance_profile        = var.iam_instance_profile

  root_block_device {
    volume_size           = var.storage_size
    volume_type           = var.storage_type
    delete_on_termination = true
    encrypted             = true

    tags = merge(
      local.common_tags,
      {
        Name = "${local.hostname-tag}-node-${count.index + 1}-root"
      }
    )
  }

  metadata_options {
    metadata_accessible         = true
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  disable_api_termination = var.environment == "prod" ? true : false

  monitoring = var.enable_monitoring
  user_data  = var.enable_kubernetes ? template_file("${path.module}/userdata.sh", {
    enable_kubernetes  = var.enable_kubernetes
    kubernetes_version = var.kubernetes_version
    hostname-tag       = "${local.hostname-tag}-node"
  }) : null

  tags = merge(
    local.common_tags,
    var.tags,
    {
      Name  = "${local.hostname-tag}-node-${count.index + 1}"
      Role  = "Kubernetes-node"
      Index = "${count.index + 1}"
    }
  )
  volume_tags = merge(
    local.common_tags,
    {
      Name = "${local.hostname-tag}-node-${count.index + 1}-volume"
    }
  )

  lifecycle {
    ignore_changes = [
      user_data,
      ami
    ]
  }
}

resource "aws_eip" "ec2_eip" {
  count    = var.environment == "prod" ? var.instance_count : 0
  instance = aws_instance.ec2_instance[count.index].id
  domain   = "vpc"
  tags = merge(
    local.common_tags,
    var.tags,
    {
      Name = "${local.hostname-tag}-node-${count.index + 1}-eip"
    }
  )

  depends_on = [aws_instance.ec2_instance]
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count = var.environment == "prod" ? var.instance_count : 0

  alarm_name          = "${local.hostname-tag}-node-${count.index + 1}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 CPU utilization"

  dimensions = {
    InstanceId = aws_instance.ec2_instance[count.index].id
  }

  insufficient_data_actions = []

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "status_check_failed" {
  count = var.environment == "prod" ? var.instance_count : 0

  alarm_name          = "${local.hostname-tag}-node-${count.index + 1}-status-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors EC2 instance status checks"

  dimensions = {
    InstanceId = aws_instance.ec2_instance[count.index].id
  }

  insufficient_data_actions = []

  tags = local.common_tags
}