# EC2 instance families

How to pick an EC2 instance family and size. Verify current generations and prices in the AWS documentation before ordering.

## Choosing a family by workload
General purpose (m5, m6i, m7g) has about 4 GiB of memory per vCPU and fits most web, API and application servers. Compute optimized (c5, c6i, c7g) has about 2 GiB per vCPU and fits CPU-bound work such as encoding, batch processing and high-traffic gateways. Memory optimized (r5, r6i, r7g) has about 8 GiB per vCPU and fits in-memory databases, caches and large JVM heaps. Storage optimized (i3, i4i) fits workloads that need very fast local disks. Accelerated (g and p families) carry GPUs for ML training or inference and video work.

## Burstable instances (t3, t3a, t4g)
Burstable instances earn CPU credits while idle and spend them under load. They are cheap and suit development, test, small internal tools and services with low average CPU and short spikes. They are a poor fit for steady high CPU, because once credits run out the instance is throttled (unless unlimited mode is on, which costs extra). For steady production load prefer the m or c families.

## Graviton (arm64) instances
Instances with a g in the family name (m7g, c7g, r7g, t4g) run on AWS Graviton ARM processors. AWS positions them as lower cost for similar performance. The software must support arm64: most modern languages and containers do, but check native dependencies and build multi-arch images.

## Sizing steps
Inside one family the price and capacity roughly double with every size step (large, xlarge, 2xlarge, 4xlarge). Start with the smallest size that keeps expected peak CPU around 50 to 60 percent, then adjust from real CloudWatch data. Prefer several smaller instances behind a load balancer over one very large instance, for availability and for finer scaling.
