# Storage: S3, EBS and EFS

Choosing between object, block and shared file storage.

## S3 object storage
S3 stores objects of any size, with high durability and no capacity planning. Use it for user uploads, static assets, backups, logs and data lakes. Choose the storage class by access pattern: Standard for frequent access, Intelligent-Tiering when access is unknown, Standard-IA or One Zone-IA for infrequent access, and Glacier classes for archives. Add lifecycle rules to move or expire old data, and block public access unless the bucket is meant to be public.

## EBS block storage
EBS volumes attach to a single EC2 instance (multi-attach is limited to special cases). Use gp3 by default, since it is cheaper than gp2 and allows independent IOPS and throughput settings. io2 is for databases with sustained, measured high IOPS needs. Size volumes from data size plus growth, and snapshot them for backups.

## EFS shared file storage
EFS is an NFS file system that many instances or containers can mount at once and that grows automatically. Use it for shared content, CMS media or home directories. It costs more per GB than EBS or S3, so prefer S3 for large static data and EBS for single-instance disks.
