# Caching and messaging

ElastiCache, SQS, SNS and EventBridge.

## ElastiCache
ElastiCache for Redis or Valkey provides in-memory caching, sessions, rate limiting and leaderboards. Size the node from the dataset size plus around 25 to 30 percent headroom for overhead and fragmentation, and use a replica in another Availability Zone for production. cache.t3 and cache.t4g are for development and small caches, while cache.m and cache.r families suit production.

## SQS
SQS is a managed queue that decouples producers and consumers and absorbs bursts. Standard queues give at-least-once delivery with high throughput, and FIFO queues give ordering and deduplication at lower throughput. Use a dead-letter queue for messages that keep failing.

## SNS and EventBridge
SNS fans out a message to many subscribers (queues, Lambda, email, HTTP). EventBridge routes events between AWS services and applications with filtering rules and schedules. Combine SNS with SQS when each subscriber needs its own buffered queue.
