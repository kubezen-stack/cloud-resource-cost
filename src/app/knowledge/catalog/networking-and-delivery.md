# Networking and content delivery

Load balancing, outbound traffic, DNS and caching at the edge.

## Load balancers
An Application Load Balancer (ALB) handles HTTP and HTTPS with path and host routing and works with containers and Lambda. A Network Load Balancer (NLB) handles TCP and UDP at very high throughput with static IPs. Use an ALB for web and API traffic unless there is a specific reason for layer 4.

## NAT gateways and data transfer
A NAT gateway lets private subnets reach the internet but charges per hour and per GB processed, so it is often a surprising part of the bill. Reduce it with VPC endpoints for S3 and DynamoDB (gateway endpoints are free), with interface endpoints for heavy AWS API traffic, and by keeping chatty services in the same Availability Zone. Cross-AZ and internet egress traffic is billed.

## CloudFront
CloudFront caches content at edge locations and lowers latency and origin load for static assets and cacheable APIs. Put it in front of S3 and ALB origins for public websites, and use it for TLS termination close to users.

## Route 53 and certificates
Route 53 provides DNS with health checks and failover routing. Certificates for AWS endpoints are free through AWS Certificate Manager.
