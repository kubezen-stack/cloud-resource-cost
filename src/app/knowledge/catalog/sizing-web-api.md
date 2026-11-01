# Sizing web and API services

Rules of thumb for stateless web and API backends. These are starting points; load test before committing.

## Starting size
A small production API (up to a few hundred requests per second, modest per-request work) usually starts at 2 instances of 2 vCPU and 4 to 8 GiB (for example m6i.large or t3.large for low steady load) in different Availability Zones behind an Application Load Balancer. Add instances horizontally with Auto Scaling instead of making one instance bigger.

## Capacity estimation
Estimate peak requests per second, multiply by the CPU time per request, and divide by the vCPUs you intend to use at around 50 to 60 percent utilisation. If the per-request cost is unknown, ask for it or run a load test, and state the assumption in the recommendation. Keep headroom for traffic bursts and for losing one instance or one Availability Zone.

## Autoscaling
Scale on average CPU (target tracking around 50 to 60 percent) or on requests per target. Set a minimum of 2 for production so one failure does not cause an outage, and a maximum that protects the budget.

## Memory and runtime
Application runtimes with large heaps (Java, .NET) need memory sized to the heap plus overhead, so pick a family by memory first. Node.js and Python services are usually CPU or I/O bound, and per-process memory is small, so general purpose instances are enough.
