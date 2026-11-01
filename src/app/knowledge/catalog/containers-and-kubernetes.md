# Containers: ECS, EKS and Fargate

Running containerised workloads.

## ECS
Amazon ECS is the simplest way to run containers on AWS, with tight IAM and load balancer integration and no control plane fee. Use it when the team does not need the Kubernetes ecosystem.

## EKS
Amazon EKS is managed Kubernetes and charges a flat fee per cluster plus the worker nodes. Choose it when the team already uses Kubernetes, needs its tooling (Helm, operators, service meshes) or wants portability across clouds. It needs more operational skill than ECS.

## Fargate versus EC2 nodes
Fargate removes node management and bills per vCPU and GB of memory used by tasks, which suits small or spiky workloads. EC2 nodes are cheaper at steady high utilisation and allow Spot, Graviton and custom instance types. For steady production load that fills nodes, EC2 with Savings Plans is usually cheaper.

## Sizing pods and nodes
Set resource requests from measured usage and limits somewhat above them, leave headroom for system pods (ingress, monitoring, DNS), and spread replicas across Availability Zones. A cluster for production should have at least 2 worker nodes in different zones.
