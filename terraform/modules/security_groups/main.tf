locals {
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "security_groups"
    }
  )
  
  hostname-tag = "${var.project_name}-${var.environment}"
}

resource "aws_security_group" "ec2_sg_id" {
  name        = "${local.hostname-tag}-sg"
  description = "Security group for ${var.project_name} in ${var.environment} environment"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, 
    { 
        Name = "${local.hostname-tag}-ec2-sg",
        Role = "kubernetes-nodes" 
    }
  )
}

resource "aws_security_group_rule" "ec2_ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description = "Allow SSH access"
}

resource "aws_security_group_rule" "ec2_k8s_api" {
  type              = "ingress"
  from_port         = 6443
  to_port           = 6443
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description = "Kubernetes API server"
}

resource "aws_security_group_rule" "ec2_kubelet" {
  type              = "ingress"
  from_port         = 10250
  to_port           = 10250
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description = "Kubelet API"
}

resource "aws_security_group_rule" "ec2_node_exporter" {
  type              = "ingress"
  from_port         = 30000
  to_port           = 32767
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description = "Node Exporter for Prometheus"
}

resource "aws_security_group_rule" "etcd" {
  type              = "ingress"
  from_port         = 2379
  to_port           = 2380
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description = "etcd server client API"
}

resource "aws_security_group_rule" "http" {
    type              = "ingress"
    from_port         = 80
    to_port           = 80
    protocol          = "tcp"
    security_group_id = aws_security_group.ec2_sg_id.id
    cidr_blocks       = ["0.0.0.0/0"]
    
    description = "Allow HTTP access"
}

resource "aws_security_group_rule" "https" {
    type              = "ingress"
    from_port         = 443
    to_port           = 443
    protocol          = "tcp"
    security_group_id = aws_security_group.ec2_sg_id.id
    cidr_blocks       = ["0.0.0.0/0"]
    
    description = "Allow HTTPS access"
}

resource "aws_security_group_rule" "ec2_internal" {
  type              = "ingress"
  from_port         = 0
  to_port           = 65535
  protocol          = "-1"
  security_group_id = aws_security_group.ec2_sg_id.id
  source_security_group_id = aws_security_group.ec2_sg_id.id

  description       = "Allow all internal traffic within the security group"
}

resource "aws_security_group_rule" "all_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.ec2_sg_id.id
  cidr_blocks       = var.ssh_access_cidr

  description       = "Allow all outbound traffic"
}

resource "aws_security_group" "rds" {
  name        = "${local.hostname-tag}-rds-sg"
  description = "Security group for RDS instances in ${var.environment} environment"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, 
    { 
        Name = "${local.hostname-tag}-rds-sg",
        Role = "database-access" 
    }
   )
}

resource "aws_security_group_rule" "rds_access_pgsql" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  source_security_group_id = aws_security_group.ec2_sg_id.id
  security_group_id = aws_security_group.rds.id
  description       = "Allow access to RDS PostgreSQL instances"
}

resource "aws_security_group_rule" "rds_from_allowed_ips" {
    count            = var.environment != "prod" ? 1 : 0
    type             = "ingress"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    security_group_id = aws_security_group.rds.id
    cidr_blocks      = var.ssh_access_cidr
    description      = "Allow access from allowed IP addresses"
}

resource "aws_security_group_rule" "rds_all_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.rds.id
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "Allow all outbound traffic"
}

resource "aws_security_group" "redis" {
  count       = var.environment == "prod" ? 1 : 0
  name        = "${local.hostname-tag}-redis-sg"
  description = "Security group for Redis instances in ${var.environment} environment"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, 
    { 
        Name = "${local.hostname-tag}-redis-sg",
        Role = "cache-access" 
    }
   )
}

resource "aws_security_group_rule" "redis_access" {
  count             = var.environment == "prod" ? 1 : 0
  type              = "ingress"
  from_port         = 6379
  to_port           = 6379
  protocol          = "tcp"
  source_security_group_id = aws_security_group.ec2_sg_id.id
  security_group_id = aws_security_group.redis[0].id
  cidr_blocks       = var.ssh_access_cidr
  description       = "Allow access to Redis instances"
}

resource "aws_security_group" "alb" {
  count       = var.environment == "prod" ? 1 : 0
  name        = "${local.hostname-tag}-alb-sg"
  description = "Security group for Application Load Balancer in ${var.environment} environment"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, 
    { 
        Name = "${local.hostname-tag}-alb-sg",
        Role = "application-load-balancer" 
    }
   )
}

resource "aws_security_group_rule" "alb_http" {
    count             = var.environment == "prod" ? 1 : 0
    type              = "ingress"
    from_port         = 80
    to_port           = 80
    protocol          = "tcp"
    security_group_id = aws_security_group.alb[0].id
    cidr_blocks       = var.ssh_access_cidr
    
    description = "Allow HTTP access to ALB"
}

resource "aws_security_group_rule" "alb_https" {
    count             = var.environment == "prod" ? 1 : 0
    type              = "ingress"
    from_port         = 443
    to_port           = 443
    protocol          = "tcp"
    security_group_id = aws_security_group.alb[0].id
    cidr_blocks       = var.ssh_access_cidr
    
    description = "Allow HTTPS access to ALB"
}

resource "aws_security_group_rule" "alb_all_egress" {
  count                    = var.environment == "prod" ? 1 : 0
  type                     = "egress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.alb[0].id
  cidr_blocks              = var.ssh_access_cidr
  description              = "Allow all outbound traffic"
}

resource "aws_security_group_rule" "alb_to_ec2" {
    count                    = var.environment == "prod" ? 1 : 0
    type                     = "egress"
    from_port                = 30080
    to_port                  = 30080
    protocol                 = "tcp"
    source_security_group_id = aws_security_group.ec2_sg_id.id
    security_group_id        = aws_security_group.alb[0].id
    description              = "Traffic to EC2 instances"
}

resource "aws_security_group_rule" "ec2_to_alb" {
    count                    = var.environment == "prod" ? 1 : 0
    type                     = "ingress"
    from_port                = 30080
    to_port                  = 30080
    protocol                 = "tcp"
    source_security_group_id = aws_security_group.alb[0].id
    security_group_id        = aws_security_group.ec2_sg_id.id
    description              = "Traffic from ALB to EC2 instances"
}