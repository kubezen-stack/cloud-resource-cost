# Reference architecture: public e-commerce site

A typical starting point for an online shop with a web front end, an API, a relational database and media files.

## Layout
Route 53 for DNS, CloudFront in front for static files and images, an Application Load Balancer across two Availability Zones, web or API servers in an Auto Scaling group in private subnets, Amazon RDS for PostgreSQL or MySQL with Multi-AZ, ElastiCache for Redis for sessions and catalog caching, S3 for product images and exports, SQS for background work such as emails and order processing, CloudWatch for metrics and alarms, AWS Backup or automated RDS backups, and a NAT gateway for outbound traffic from private subnets.

## Capacity reasoning example
This calculation is illustrative and must be replaced by measured values. If the shop must serve 200 requests per second at peak and one request needs about 20 ms of CPU time, the load is about 200 times 0.02, which is 4 vCPU-seconds per second. Running at 50 to 60 percent target utilisation needs roughly 7 to 8 vCPU in total, for example four instances with 2 vCPU each spread over two zones, so that losing one zone still leaves capacity. Measure real CPU time per request with a load test before committing.

## Sale peaks
Traffic during campaigns can be many times the average. Use scheduled scaling before known events, cache product pages in CloudFront and Redis, and move slow work to a queue. The database is usually the limit, so add read replicas or a cache before adding web servers.

## Common mistakes
Putting sessions in server memory, serving images from the application servers, a single database instance without Multi-AZ, no backups tested by a restore, and no alarms on error rate or latency.
