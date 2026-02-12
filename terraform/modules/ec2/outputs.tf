output "ec2_instance_ids" {
  description = "The IDs of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].id
}

output "ec2_arns" {
  description = "The ARNs of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].arn
}

output "ec2_instance_public_ips" {
  description = "The public IPs of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].public_ip
}

output "ec2_instance_private_ips" {
  description = "The private IPs of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].private_ip
}

output "ec2_dns_public" {
  description = "The public DNS names of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].public_dns
}

output "ec2_dns_private" {
  description = "The private DNS names of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].private_dns
}

output "ec2_availability_zones" {
  description = "The availability zones of the launched EC2 instances"
  value       = aws_instance.ec2_instance[*].availability_zone
}

output "ec2_eips" {
  description = "The Elastic IPs associated with the launched EC2 instances"
  value       = aws_eip.ec2_eip[*].public_ip
}

output "ssh_connection" {
  description = "SSH connection string for the first EC2 instance"
  value = [
    for i, instance in aws_instance.ec2_instance :
    "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${instance.public_ip}"
  ]
}

output "ssh_connection_information" {
  description = "SSH connection information for all EC2 instances"
  value = {
    for i, instance in aws_instance.ec2_instance :
    "node-${i + 1}" => {
      instance_id = "${instance.id}"
      public_ip  = "${instance.public_ip}"
      private_ip = "${instance.private_ip}"
      az         = "${instance.availability_zone}"
      ssh        = "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${instance.public_ip}"
    }
  }
}

output "ami_id_used" {
  description = "The AMI ID used for the EC2 instances"
  value       = local.ami_id
}

output "ami_name" {
  description = "The name of the AMI used for the EC2 instances"
  value       = data.aws_ami.ubuntu.name
}