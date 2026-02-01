output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "The CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_cidr_blocks" {
  description = "List of public subnet CIDR blocks"
  value       = aws_subnet.public[*].cidr_block
}

output "private_cidr_blocks" {
  description = "List of private subnet CIDR blocks"
  value       = aws_subnet.private[*].cidr_block
}

output "public_az_zones" {
  description = "List of availability zones for public subnets"
  value       =  { for idx, az in var.availability_zones : az => aws_subnet.public[idx].id }
}

output "private_az_zones" {
  description = "List of availability zones for private subnets"
  value       = { for idx, az in var.availability_zones : az => aws_subnet.private[idx].id }
}

output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  value       = aws_nat_gateway.nat[*].id
}

output "internet_gateway_id" {
  description = "The ID of the Internet Gateway"
  value       = aws_internet_gateway.igw.id
}

output "nat_gateway_ips" {
  description = "List of NAT Gateway Elastic IPs"
  value       = aws_eip.nat[*].public_ip
}

output "route_table_public_id" {
  description = "The ID of the public route table"
  value       = aws_route_table.public.id
}

output "route_table_private_ids" {
  description = "List of private route table IDs"
  value       = aws_route_table.private[*].id
}