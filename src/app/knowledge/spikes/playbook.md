# Cost spike playbook

Typical causes of a sudden increase by kind of usage, how to check each one and what usually fixes it.
These are starting points: the reason for a particular spike is only known to the people running the system.

## Data processed by a NAT Gateway
Typical causes: servers in private subnets send or receive a lot of data through the gateway, for example downloads from S3 or DynamoDB, container image pulls, package installs, backups, or logs shipped to an outside service. Every gigabyte through a NAT Gateway is charged per GB, whichever service it goes to.
How to check: look at the NAT Gateway CloudWatch metrics (BytesOutToDestination, BytesInFromSource) for the day; enable VPC Flow Logs on the NAT Gateway network interface and find the biggest source addresses and destinations.
What to do: add a gateway VPC endpoint for S3 and for DynamoDB (they have no hourly or per-GB charge) so that traffic to them stops using the NAT Gateway; consider interface endpoints for other heavy AWS services such as ECR; cache images and packages; keep chatty services in the same Availability Zone as their NAT Gateway.

## NAT Gateway hours
Typical causes: a new NAT Gateway was created, often one per Availability Zone for a new environment or VPC.
How to check: list the NAT Gateways in the region and their creation dates (VPC console or CloudTrail event history for CreateNatGateway).
What to do: keep one NAT Gateway per zone only in production; in development and test use a single one or none; delete gateways of environments that no longer exist.

## Instance hours
Typical causes: more instances are running (an Auto Scaling group scaled out, a test environment was left on, instances were launched by hand) or the instances were moved to a larger type.
How to check: the Auto Scaling activity history shows why and when it scaled; the EC2 console lists running instances with launch times; CloudTrail event history shows RunInstances calls; Cost Explorer grouped by instance type shows which type grew.
What to do: stop or terminate instances nobody uses; set a sensible maximum on the Auto Scaling group and review its scaling policy; rightsize instances whose CPU stays low; cover the steady baseline with Savings Plans or Reserved Instances.

## Spot instance hours
Typical causes: a batch job or a group of workers ran for longer or on more instances than usual.
How to check: the Auto Scaling or fleet activity history and the job scheduler logs for that day.
What to do: limit the number of workers, set a timeout on jobs and use several instance types so that capacity stays cheap.

## Database instance hours
Typical causes: a new database instance or a read replica was created, a database was converted to Multi-AZ, or its class was increased.
How to check: the RDS console events list creation, modification and failover events with dates; CloudTrail event history shows CreateDBInstance, ModifyDBInstance and CreateDBInstanceReadReplica.
What to do: remove replicas and instances of environments no longer used; keep Multi-AZ for production only; match the class to measured CPU and memory.

## Load balancer hours
Typical causes: a new load balancer was created, often one per service or per environment.
How to check: list the load balancers with creation dates (EC2 console or CloudTrail event history for CreateLoadBalancer).
What to do: delete load balancers without targets; serve several services behind one Application Load Balancer with host or path rules.

## Load balancer capacity units
Typical causes: more traffic, more new connections, more bytes processed or more rule evaluations, for example from a bot, a crawler or a load test.
How to check: the load balancer CloudWatch metrics (RequestCount, NewConnectionCount, ProcessedBytes) for the day, and the access logs for the top clients.
What to do: block or rate limit abusive clients with AWS WAF; cache responses; reduce the number of rules evaluated per request.

## Data transfer
Typical causes: more data sent to the internet, between Availability Zones or between regions. The usage type tells which: names with Out-Bytes are data sent out, Regional-Bytes is traffic between zones inside a region.
How to check: Cost Explorer grouped by usage type shows which kind of transfer grew; VPC Flow Logs show the biggest flows; for S3 and CloudFront check the request and byte metrics.
What to do: serve public content through CloudFront, whose transfer to the internet is usually cheaper than sending it directly from EC2 or a load balancer; keep services that talk a lot in the same Availability Zone; compress responses; use VPC endpoints for AWS services.

## Volume snapshots
Typical causes: backups are taken more often or kept longer, or snapshots of deleted volumes and old images pile up.
How to check: list snapshots by creation date and size in the EC2 console; check which lifecycle or backup policies create them.
What to do: set a retention period in Data Lifecycle Manager or AWS Backup; delete snapshots of volumes that no longer exist and of images that are no longer used.

## EBS volumes
Typical causes: new or larger volumes, volumes left behind after instances were terminated, or a switch to a more expensive volume type or provisioned IOPS.
How to check: filter the EC2 console volumes by state "available" (unattached); compare volume types and sizes; CloudTrail event history shows CreateVolume and ModifyVolume.
What to do: delete unattached volumes after taking a snapshot if needed; move gp2 volumes to gp3; reduce provisioned IOPS and throughput to what the workload uses.

## Storage
Typical causes: data written in larger amounts than before (logs, backups, uploads) or kept without an expiry.
How to check: S3 storage metrics in CloudWatch per bucket and the S3 Storage Lens dashboard show which bucket grew; for databases check the storage metrics and automated backup size.
What to do: add S3 lifecycle rules that expire or archive old objects; cap log retention in CloudWatch Logs; clean up old database snapshots.

## Requests
Typical causes: a loop, a retry storm, a crawler or a bot sending far more requests to S3, an API or a function than usual.
How to check: the request metrics of the service in CloudWatch for the day, the access logs, and CloudTrail data events if they are enabled; check recent deployments for a changed retry or polling setting.
What to do: fix the loop or the retry policy; add caching; rate limit with WAF or API Gateway usage plans; set alarms on request counts.

## Function compute time
Typical causes: functions run longer or are invoked more often than before, for example after a code change, a retry loop, or a larger memory setting.
How to check: the function CloudWatch metrics (Invocations, Duration, Errors, Throttles) for the day and the recent deployments.
What to do: fix retries and recursive invocations; set a timeout and a concurrency limit; tune the memory size using measured duration.

## Public IPv4 addresses
Typical causes: more public IPv4 addresses in use, each charged per hour, including addresses attached to instances, load balancers, NAT Gateways, and unused Elastic IPs.
How to check: list Elastic IPs and public addresses by region (EC2 console, VPC IP Address Manager public IP insights).
What to do: release unused Elastic IPs; avoid public addresses for instances behind a load balancer; use IPv6 where possible.

## A usage type that is new
Typical causes: something was launched that did not exist before in this service.
How to check: CloudTrail event history for create and launch calls on the service around that day shows who did what.
What to do: confirm that the new resource is intended, tag it with an owner and an environment, and decide whether it should keep running.

## Unknown usage type
Typical causes: the usage type is not one the playbook covers.
How to check: in Cost Explorer filter by this service and group by usage type, then by tag or linked account; read the AWS pricing page of the service for what the usage type bills; CloudTrail event history shows recent changes to the service.
What to do: find the resource behind it and its owner before changing anything.
