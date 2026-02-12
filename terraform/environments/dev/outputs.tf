output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  value       = module.vpc.nat_gateway_ids
}

output "ec2_instance_ids" {
  description = "The IDs of the launched EC2 instances"
  value       = module.ec2.ec2_instance_ids
}

output "ec2_instance_public_ips" {
  description = "The public IPs of the launched EC2 instances"
  value       = module.ec2.ec2_instance_public_ips
}

output "ec2_instance_private_ips" {
  description = "The private IPs of the launched EC2 instances"
  value       = module.ec2.ec2_instance_private_ips
}

output "ssh_connection_information" {
  description = "SSH connection information for all EC2 instances"
  value       = module.ec2.ssh_connection_information
}

output "ami_id_used" {
  description = "The AMI ID used for the EC2 instances"
  value       = module.ec2.ami_id_used
}