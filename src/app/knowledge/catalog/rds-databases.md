# Amazon RDS databases

Managed relational databases: PostgreSQL, MySQL, MariaDB, Oracle and SQL Server.

## Instance classes
db.t3 and db.t4g are burstable and suit development, test and low-traffic systems. db.m5, db.m6g and db.m6i are general purpose and the default for production. db.r5, db.r6g and db.r6i add memory and suit large working sets, heavy joins and many connections. Choose the class by working-set size first: the hot data and indexes should fit in memory. The maximum number of connections grows with instance memory.

## High availability
Production databases should use Multi-AZ, which keeps a synchronous standby in another Availability Zone and fails over automatically. Development and test can stay single-AZ to save cost. Read replicas scale reads and are not a replacement for Multi-AZ.

## Storage
gp3 is the default general purpose SSD and lets IOPS and throughput be set independently of size. Use io1 or io2 only when a measured workload needs sustained high IOPS. Enable storage autoscaling with a sensible maximum.

## Backups and safety
Enable automated backups with a retention of at least 7 days for production, take a final snapshot on deletion, and turn on deletion protection. Keep the database in private subnets, encrypt it with KMS, and allow access only from the application security group.

## Aurora
Aurora (PostgreSQL or MySQL compatible) fits workloads that need faster failover, many read replicas or automatic storage growth. Aurora Serverless v2 suits spiky or unpredictable load. For small, steady systems standard RDS is usually cheaper and simpler.
