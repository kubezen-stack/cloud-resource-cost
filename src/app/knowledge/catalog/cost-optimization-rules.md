# Cost optimisation rules

Practical levers, roughly in order of impact for steady workloads.

## Commitments
Compute Savings Plans or Reserved Instances lower the price for steady, predictable usage in exchange for a one or three year commitment. Commit only to the baseline that always runs, and leave variable load on demand.

## Spot capacity
Spot instances are much cheaper than on-demand but can be interrupted. Use them for fault-tolerant, stateless or batch work (workers, CI runners, data processing), spread over several instance types, and never for single-instance stateful systems.

## Rightsizing
Compare real utilisation with the provisioned size. Instances whose 95th percentile CPU stays low can usually move one size down inside the family. Memory is not visible in default CloudWatch metrics, so check it with the CloudWatch agent before downsizing.

## Schedules and environments
Development and test environments rarely need to run at night or on weekends. Stop them on a schedule, use smaller classes than production and avoid Multi-AZ there.

## Storage and network
Move gp2 volumes to gp3, delete unattached volumes and old snapshots, apply S3 lifecycle rules, and review NAT gateway and cross-AZ data transfer charges.

## Visibility
Use cost allocation tags, budgets with alerts and anomaly detection so unexpected spend is noticed within a day.
