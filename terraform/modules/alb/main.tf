locals {

  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "Terraform"
    Module      = "ALB"
  }

  hostname-tag = "${var.project_name}-${var.environment}"
}

resource "aws_lb" "alb" {
    count = var.create_alb ? 1 : 0
    name               = var.name_alb
    internal           = var.internal
    load_balancer_type = var.load_balancer_type
    security_groups    = [var.alb_security_group_id]
    subnets           = var.public_subnet_ids

    enable_deletion_protection = var.enable_deletion_protection
    enable_cross_zone_load_balancing = true
    enable_http2 = true

    access_logs {
        bucket = var.access_logs_bucket
        prefix = "${var.project_name}/${var.environment}/alb-logs"
        enabled = true
    }

    
    tags = merge(
    local.common_tags, 
        { 
            Name = "${local.hostname-tag}-alb"
        }
    )
}

resource "aws_lb_target_group" "alb_target_group" {
    count = var.create_alb ? 1 : 0
    name     = "${var.project_name}-${var.environment}-tg"
    port     = var.target_group_port
    protocol = "HTTP"
    vpc_id   = var.vpc_id

    health_check {
        enabled            = true
        path                = var.health_check_path
        protocol            = "HTTP"
        matcher             = "200-399"
        interval            = 30
        timeout             = 5
        healthy_threshold   = 3
        unhealthy_threshold = 3
    }

    deregistration_delay = 30

    tags = merge(
    local.common_tags, 
        { 
            Name = "${local.hostname-tag}-tg"
        }
    )
}

resource "aws_lb_target_group_attachment" "alb_target_group_attachment" {
    count = var.create_alb ? length(var.ec2_instance_ids) : 0
    target_group_arn = aws_lb_target_group.alb_target_group[0].arn
    target_id        = var.ec2_instance_ids[count.index]
    port             = var.target_group_port
}

resource "aws_lb_listener" "http" {
    count = var.create_alb ? 1 : 0
    load_balancer_arn = aws_lb.alb[0].arn
    port              = var.listener_port
    protocol          = "HTTP"

    default_action {
        type             = var.certificate_arn != "" ? "redirect" : "forward"

        dynamic "redirect" {
            for_each = var.certificate_arn != "" ? [1] : []
            content {
                protocol = "HTTPS"
                port     = "443"
                status_code = "HTTP_301"
            }
        }

        target_group_arn = var.certificate_arn == "" ? aws_lb_target_group.alb_target_group[0].arn : null
    }

    tags = merge(
    local.common_tags, 
        { 
            Name = "${local.hostname-tag}-http-listener"
        }
    )
}

resource "aws_lb_listener" "https" {
    count = var.create_alb && var.certificate_arn != "" ? 1 : 0
    load_balancer_arn = aws_lb.alb[0].arn
    port              = "443"
    protocol          = "HTTPS"
    ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
    certificate_arn   = var.certificate_arn

    default_action {
        type             = "forward"
        target_group_arn = aws_lb_target_group.alb_target_group[0].arn
    }

    tags = merge(
    local.common_tags, 
        { 
            Name = "${local.hostname-tag}-https-listener"
        }
    )
}