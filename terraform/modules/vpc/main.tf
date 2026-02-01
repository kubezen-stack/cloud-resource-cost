locals {
  private_subnets = length(var.availability_zones)
  public_subnets  = length(var.availability_zones)

  common_tags = {
    Name = var.project_name
    Environment = var.environment
    ManagedBy = "Terraform"
  }
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = var.dns_hostnames_enabled
  enable_dns_support   = var.dns_support_enabled

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-vpc-${var.environment}" 
    }
  )
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-igw-${var.environment}" 
    }
  )
}

resource "aws_subnet" "public" {
  count                   = local.public_subnets
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 3, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-public-subnet-${var.availability_zones[count.index]}-${var.environment}"
      Type = "public" 
    }
  )
}

resource "aws_subnet" "private" {
  count                   = local.private_subnets
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 3, count.index + local.public_subnets)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-private-subnet-${var.availability_zones[count.index]}-${var.environment}" 
      Type = "private"
    }
  )
}

resource "aws_eip" "nat" {
  count = var.nat_gateway_enabled && var.nat_gateway_single ? 1 : local.public_subnets

  domain = "vpc"

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-nat-eip-${count.index + 1}-${var.environment}" 
    }
  )

  depends_on = [aws_internet_gateway.igw]
}

resource "aws_nat_gateway" "nat" {
  count = var.nat_gateway_enabled ? (var.nat_gateway_single ? 1 : local.public_subnets) : 0

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-nat-gateway-${count.index + 1}-${var.environment}" 
    }
  )

  depends_on = [aws_internet_gateway.igw]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-public-rt-${var.environment}" 
      Type = "public"
    }
  )
}

resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public_subnets" {
  count          = local.public_subnets
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  count  = var.nat_gateway_enabled ? 1 : local.private_subnets

  tags = merge(local.common_tags,
    var.tags, 
    { 
      Name = "${var.project_name}-private-rt-${count.index + 1}-${var.environment}"
      Type = "private" 
    }
  )
}

resource "aws_route" "private_nat" {
  count = var.nat_gateway_enabled ? (var.nat_gateway_single ? 1 : local.private_subnets) : 0
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat[count.index].id
}

resource "aws_route_table_association" "private" {
  count          = local.private_subnets
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = var.nat_gateway_single ? aws_route_table.private[0].id : aws_route_table.private[count.index].id
}