# Auto scaling

How to let compute capacity follow load instead of provisioning for the peak.

## Auto Scaling groups
An Auto Scaling group keeps a minimum number of instances running, adds instances when load rises and removes them when it falls. Spread the group over at least two Availability Zones and attach it to a load balancer target group so that unhealthy instances are replaced automatically. Stateless servers are required: sessions go to a cache, files go to S3.

## Scaling policies
Target tracking is the simplest policy: keep average CPU around 50 to 60 percent, or keep requests per target at a chosen value. Add a scheduled action when the peak is predictable, such as a known sale or business hours. Set the minimum to cover the baseline across two zones and the maximum to a value that also caps the bill.

## Warm-up and limits
New instances need time to boot and pass health checks, so keep headroom in the target and set a warm-up period. Scale out quickly and scale in slowly to avoid flapping. Check service quotas for the instance family in the chosen region before a large launch.

## Containers and serverless
On Kubernetes use the Horizontal Pod Autoscaler together with a cluster autoscaler or Karpenter. Lambda and Fargate scale per request or per task without managing a group, at a higher unit price for steady load.
