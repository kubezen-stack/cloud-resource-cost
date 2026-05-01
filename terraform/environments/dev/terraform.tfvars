aws_region          = "us-east-1"
vpc_cidr            = "12.0.0.0/16"
availability_zones  = ["us-east-1a", "us-east-1b"]
nat_gateway_enabled = false
nat_gateway_single  = false

instance_type      = "t3.medium"
instance_count     = 2
storage_size       = 30
storage_type       = "gp3"
ami_id             = ""
enable_monitoring  = false
enable_kubernetes  = false
kubernetes_version = "1.28"
ssh_access_cidr    = ["0.0.0.0/0"]
create_alb         = false

enable_rds              = false
db_instance_class       = "db.t3.micro"
allocated_storage       = 20
multi_az                = false
backup_retention_period = 3