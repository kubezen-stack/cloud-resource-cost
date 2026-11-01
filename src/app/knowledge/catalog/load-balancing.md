# Load balancing

Choosing and configuring AWS load balancers.

## Application Load Balancer
The Application Load Balancer (ALB) is the default for HTTP and HTTPS web traffic. It is a managed regional service: it spans the Availability Zones you attach it to and scales by itself, so it has no instance count or size to choose. Configure it in at least two public subnets in different zones, terminate TLS with a certificate from AWS Certificate Manager, and use health checks on each target group. Cost has an hourly part plus a charge for load balancer capacity units based on connections, bytes and rules.

## Network Load Balancer
Use the Network Load Balancer (NLB) for non-HTTP protocols, very high connection rates, static IP addresses or PrivateLink. It forwards TCP, UDP and TLS with very low latency.

## Placement and security
Place the load balancer in public subnets and the application servers in private subnets that accept traffic only from the load balancer security group. Add AWS WAF to the ALB when the site is public and handles logins or payments.

## Routing features
Path and host based rules let one ALB serve several services. Sticky sessions are possible but a shared session store is the better design because it keeps servers interchangeable.
