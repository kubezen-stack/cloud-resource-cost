# Environments and availability

How the target environment changes the design.

## Development and test
Single Availability Zone, burstable instance classes, smallest viable databases, no Multi-AZ, and scheduled shutdown outside working hours. Cost matters more than resilience.

## Staging
Mirror the production topology at a smaller scale so deployments and integrations are tested realistically, but with fewer and smaller instances.

## Production
At least two Availability Zones, no single points of failure, Multi-AZ databases, automated backups and tested restores, autoscaling with a minimum of 2, monitoring and alerting. Availability targets drive the design: a 99.9 percent target allows roughly 8.7 hours of downtime per year, 99.99 percent roughly 52 minutes, and each extra nine needs more redundancy and cost.

## Disaster recovery
Define the recovery time objective (RTO) and recovery point objective (RPO). Backups in another region suit relaxed targets. A warm standby or active-active design in a second region suits strict targets and costs substantially more.
