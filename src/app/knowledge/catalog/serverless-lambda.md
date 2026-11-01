# Serverless: Lambda, API Gateway and DynamoDB

When to use serverless building blocks.

## Lambda
Lambda runs code per request with no servers and bills per invocation and per millisecond of execution. It fits spiky or low-traffic APIs, event processing, scheduled jobs and glue code. Memory (128 MB to 10 GB) also sets the CPU share, so raising memory can shorten runtime and lower total cost. A single invocation is limited to 15 minutes. Cold starts add latency for infrequently used functions. At constant high traffic, containers or instances are often cheaper.

## API Gateway
API Gateway fronts Lambda or other backends with authentication, throttling and caching. HTTP APIs are cheaper and simpler than REST APIs when advanced features are not required.

## DynamoDB
DynamoDB is a managed key-value and document database with single-digit millisecond latency at any scale. On-demand capacity suits unpredictable traffic, and provisioned capacity with autoscaling is cheaper for steady traffic. It requires modelling around access patterns and does not support arbitrary joins.
