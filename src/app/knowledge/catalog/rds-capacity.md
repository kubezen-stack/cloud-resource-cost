# Database capacity and storage

Sizing Amazon RDS beyond choosing the engine.

## Storage sizing
Estimate the data size for the first year, then add headroom of at least 30 to 50 percent and enable storage autoscaling with a maximum limit. Remember indexes, temporary files and logs. General purpose gp3 storage is the default; provisioned IOPS storage is only needed for sustained high random I/O. Check current gp3 baseline IOPS and throughput in the AWS documentation before relying on a number.

## Instance class
Start from memory: the working set and indexes should mostly fit in RAM. A small shop or internal tool often runs well on a db.t4g or db.m6g class with 2 to 4 vCPU; busy transactional systems move to db.r6g memory optimised classes. Burstable classes are cheap but throttle under sustained CPU load.

## Connections
Each connection uses memory. With many application instances or serverless functions, put RDS Proxy or a connection pooler in front of the database, and size the application pool so that the total stays below the database limit.

## Availability and recovery
Multi-AZ keeps a synchronous standby in another zone and fails over automatically, which is the baseline for production. Read replicas scale reads and are not a substitute for Multi-AZ. Keep automated backups with a retention of 7 to 35 days, take snapshots before risky changes, and test a restore.

## Cost notes
Multi-AZ roughly doubles the instance cost. Stop or downsize non-production databases outside working hours, and review idle replicas.
