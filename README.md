# Cloud Resource Cost Optimizer

A full-stack solution for monitoring, analyzing, and optimizing AWS cloud costs. Built with a FastAPI backend and PostgreSQL, deployed on a self-managed Kubernetes cluster provisioned entirely with Infrastructure as Code.

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Local Development](#local-development)
- [Infrastructure](#infrastructure)
- [Kubernetes & Helm](#kubernetes--helm)
- [CI/CD Pipeline](#cicd-pipeline)
- [Monitoring](#monitoring)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          AWS EC2                            │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Kubernetes Cluster                    │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │cost-optimizer│  │  monitoring │  │   argocd    │  │ │
│  │  │  namespace   │  │  namespace  │  │  namespace  │  │ │
│  │  │              │  │             │  │             │  │ │
│  │  │  FastAPI app │  │  Victoria   │  │   ArgoCD    │  │ │
│  │  │  PostgreSQL  │  │  Metrics    │  │             │  │ │
│  │  │              │  │  Grafana    │  │             │  │ │
│  │  │              │  │  Loki       │  │             │  │ │
│  │  │              │  │  Promtail   │  │             │  │ │
│  │  │              │  │  Alertmgr   │  │             │  │ │
│  │  └──────────────┘  └─────────────┘  └─────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐  │
│  │   ECR    │  │    S3    │  │  Secrets   │  │   IAM   │  │
│  │  Docker  │  │ reports  │  │  Manager   │  │  roles  │  │
│  │  images  │  │ backups  │  │  kubeconf  │  │         │  │
│  │          │  │ tf state │  │  ssh keys  │  │         │  │
│  └──────────┘  └──────────┘  └────────────┘  └─────────┘  │
└─────────────────────────────────────────────────────────────┘
```

The application interacts with the **AWS Cost Explorer API** by assuming IAM roles in connected customer accounts, fetching cost data without storing long-term credentials.

---

## Features

- **User Authentication** — Secure registration and login with JWT tokens
- **Multi-Account AWS Integration** — Connect multiple AWS accounts via IAM Role + External ID
- **Cost & Usage Analysis** — Flexible queries by date range, granularity (daily/monthly), and dimension
- **Cost Forecasting** — Monthly cost predictions up to 90 days ahead
- **Service Cost Breakdown** — Cost distribution across AWS services sorted by spend
- **Database Migrations** — Automated schema management via Alembic run as a Helm post-install hook
- **Automated Infrastructure** — Full IaC with Terraform and Ansible
- **GitOps Deployment** — ArgoCD for Kubernetes-native continuous delivery
- **Comprehensive Monitoring** — Metrics, logs, and alerts out of the box
- **Security Scanning** — Trivy image scanning + SonarCloud static analysis on every build
- **Telegram Notifications** — CI/CD pipeline results sent directly to Telegram

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy (async), Pydantic v2 |
| Database | PostgreSQL, asyncpg, Alembic |
| Auth | JWT, python-jose, passlib/bcrypt |
| Infrastructure | Terraform, AWS (EC2, ECR, S3, IAM, Secrets Manager, DynamoDB) |
| Kubernetes | kubeadm 1.28, Calico CNI, Helm 3 |
| CI/CD | GitHub Actions, ArgoCD, SonarCloud, Trivy |
| Monitoring | VictoriaMetrics, Grafana, Loki, Promtail, Alertmanager, Node Exporter |
| Provisioning | Ansible, amazon.aws collection |
| Container | Docker (multi-stage build) |

---

## Repository Structure

```
.
├── .github/workflows/
│   ├── ansible.yml          # Cluster provisioning workflow
│   ├── deploy.yml           # Build, test, and deploy workflow
│   └── terraform.yml        # Infrastructure lifecycle workflow
├── ansible/
│   ├── inventory/dev/       # AWS EC2 dynamic inventory
│   ├── playbooks/           # site, master, worker, calico, helm, runner
│   └── roles/               # common, kubernetes, master, worker, helm, github-runner, calico
├── docker/
│   └── Dockerfile           # Multi-stage Python build
├── helm/
│   ├── argocd/              # ArgoCD Helm chart (values, values-dev)
│   ├── cost-optimizer/      # Application Helm chart
│   └── monitoring/          # Full monitoring stack Helm chart
├── src/
│   ├── alembic/             # Database migrations
│   ├── app/
│   │   ├── api/v1/          # Routers: auth, users, aws_accounts, costs, health
│   │   ├── core/            # Config, database, security, deps
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── services/        # AWS Cost Explorer service
│   ├── dev/                 # docker-compose and local .env
│   └── tests/               # unit, integration, smoke
└── terraform/
    ├── bootstrap/           # S3 + DynamoDB for Terraform state
    ├── environments/dev/    # Dev environment entrypoint
    └── modules/             # vpc, ec2, ecr, iam, rds, s3, alb, security_groups
```

---

## Getting Started

### Prerequisites

- AWS Account with administrative permissions
- Terraform CLI `>= 1.6.0`
- Ansible
- Docker
- kubectl and Helm 3
- GitHub PAT with `repo` scope (for self-hosted runner registration)

### Required GitHub Secrets

Configure these in **Settings → Secrets and variables → Actions** before running any workflow:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key |
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `DEV_SECRET_KEY` | Application JWT secret key |
| `DEV_DB_PASSWORD` | PostgreSQL password for dev |
| `SONAR_TOKEN` | SonarCloud authentication token |
| `TOKEN` | GitHub token for SonarCloud |
| `GH_RUNNER_PAT` | GitHub PAT for runner registration |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications |

---

## Local Development

```bash
# Clone the repository
git clone https://github.com/kubezen-stack/cloud-resource-cost.git
cd cloud-resource-cost

# Configure local environment
cp src/dev/.env.example src/dev/.env
# Edit src/dev/.env with your values

# Start the full stack with Docker Compose
cd src/dev
docker-compose up -d

# Or run manually
pip install -r src/requirements.txt
cd src && alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/api/v1/openapi.json`.

---

## Infrastructure

### Step 1 — Bootstrap Terraform Backend

Creates S3 bucket and DynamoDB table for remote Terraform state. Run **once**:

```bash
cd terraform/bootstrap
terraform init
terraform apply
```

This creates `cost-optimizer-terraform-state` (S3) and `cost-optimizer-terraform-locks` (DynamoDB).

### Step 2 — Provision AWS Infrastructure

Via GitHub Actions → **Terraform** workflow → `apply` action.

Or locally:

```bash
cd terraform/environments/dev
terraform init
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

**Resources created:** VPC, subnets, Security Groups, EC2 instances, ECR repository, S3 buckets (reports + backups), IAM roles and policies, Secrets Manager secrets (SSH key).

### Step 3 — Configure Kubernetes Cluster

Via GitHub Actions → **Ansible** workflow → `site.yml` playbook.

The playbook runs in sequence:

```
common setup → kubernetes install → master init → calico CNI → worker join → helm install → github runner
```

After completion, kubeconfig is automatically saved to AWS Secrets Manager as `cost-optimizer-dev-kubeconfig`.

---

## Kubernetes & Helm

### Namespaces

| Namespace | Components |
|-----------|-----------|
| `cost-optimizer` | FastAPI application, PostgreSQL |
| `monitoring` | VictoriaMetrics, Grafana, Loki, Promtail, Node Exporter, Alertmanager |
| `argocd` | ArgoCD server |

### Deploy Commands

**Application:**
```bash
helm dependency build ./helm/cost-optimizer
helm upgrade --install cost-optimizer ./helm/cost-optimizer \
  -f ./helm/cost-optimizer/values-dev.yaml \
  --set image.repository=<ECR_URL> \
  --set image.tag=<TAG> \
  --set app.secretKey=<SECRET_KEY> \
  --set database.password=<DB_PASSWORD> \
  --set postgresql.auth.password=<DB_PASSWORD> \
  --namespace cost-optimizer \
  --create-namespace \
  --timeout 600s --wait
```

**Monitoring:**
```bash
helm dependency build ./helm/monitoring
helm upgrade --install monitoring ./helm/monitoring \
  -f ./helm/monitoring/values-dev.yaml \
  --namespace monitoring --create-namespace \
  --timeout 600s --wait
```

**ArgoCD:**
```bash
helm dependency build ./helm/argocd
helm upgrade --install argocd ./helm/argocd \
  -f ./helm/argocd/values-dev.yaml \
  --namespace argocd --create-namespace \
  --timeout 300s --wait
```

### Access Services in Dev

| Service | NodePort | URL |
|---------|----------|-----|
| Application | 30080 | `http://<EC2_IP>:30080` |
| Grafana | 30300 | `http://<EC2_IP>:30300` (admin / admin) |
| ArgoCD | 30808 | `http://<EC2_IP>:30808` (admin / see below) |
| VictoriaMetrics | 8428 | port-forward required |

**Get ArgoCD admin password:**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

**Access VictoriaMetrics:**
```bash
kubectl port-forward svc/monitoring-victoria-metrics-single-server \
  8428:8428 -n monitoring --address 0.0.0.0
```

---

## CI/CD Pipeline

### `deploy.yml` — Main Pipeline

Triggered automatically on push to `main` (paths: `src/**`, `helm/**`, `docker/**`) or manually.

```
sonarcloud ──────────────────────────────────────────────────────────────────┐
                                                                              ▼
build-and-push ──► helm-deploy-dev ──────────────► run-tests ──────────► notify
               ├──► helm-deploy-monitoring-dev ──────────────────────────────┤
               └──► argo-cd-dev ─────────────────────────────────────────────┘
```

| Job | Runner | Description |
|-----|--------|-------------|
| `sonarcloud` | ubuntu-latest | Static code analysis |
| `build-and-push` | ubuntu-latest | Build Docker image, Trivy security scan, push to ECR |
| `helm-deploy-dev` | self-hosted | Deploy application via Helm |
| `helm-deploy-monitoring-dev` | self-hosted | Deploy monitoring stack via Helm |
| `argo-cd-dev` | self-hosted | Deploy ArgoCD via Helm |
| `run-tests` | self-hosted | Unit, integration, and smoke tests |
| `notify` | ubuntu-latest | Telegram notification with full results |

### `terraform.yml` — Infrastructure

Triggered on changes to `terraform/**` or manually.

| Action | Trigger |
|--------|---------|
| `plan` | Push / PR to main + manual |
| `apply` | Manual only |
| `destroy` | Manual only |

### `ansible.yml` — Cluster Provisioning

Manual trigger only. Selectable playbooks:

| Playbook | Description |
|----------|-------------|
| `site.yml` | Full cluster setup (recommended for first run) |
| `common.yml` | Base packages + kernel config |
| `master_k8s.yml` | Initialize Kubernetes master node |
| `calico.yml` | Install and configure Calico CNI |
| `worker_k8s.yml` | Join worker nodes to the cluster |
| `helm_group.yml` | Install Helm + create ECR pull secret |
| `github_runner.yml` | Register self-hosted GitHub Actions runner |

---

## Monitoring

### Stack Components

| Component | Role | Dev | Prod |
|-----------|------|-----|------|
| VictoriaMetrics | Metrics storage | 3d retention | 14d + 20Gi PVC |
| VM Agent | Metrics scraping every 10s | enabled | enabled |
| Grafana | Dashboards | NodePort 30300 | ClusterIP + Ingress |
| Loki | Log aggregation | filesystem | filesystem |
| Promtail | Log shipping from pods | enabled | enabled |
| Node Exporter | Host-level metrics | enabled | enabled |
| Alertmanager | Alert routing | disabled | enabled |

### Pre-configured Grafana Datasources

- **VictoriaMetrics** — `http://monitoring-victoria-metrics-single-server:8428` (default)
- **Loki** — `http://monitoring-loki:3100`

### Pre-configured Dashboards (prod)

- **Node Exporter Full** (gnetId: 1860)
- **Kubernetes Cluster** (gnetId: 315)

---

## API Endpoints

Base URL: `/api/v1`

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login, returns JWT access token |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me` | Get current user profile |
| PUT | `/users/me` | Update name, email, or password |
| DELETE | `/users/me` | Permanently delete account |

### AWS Accounts

| Method | Path | Description |
|--------|------|-------------|
| POST | `/aws_accounts/` | Connect an AWS account via IAM Role |
| GET | `/aws_accounts/` | List all connected accounts |
| GET | `/aws_accounts/{id}` | Get details for a specific account |

### Costs

| Method | Path | Query Params | Description |
|--------|------|--------------|-------------|
| GET | `/costs/{account_id}/costs` | `start_date`, `end_date`, `granularity`, `group_by` | Cost and usage data |
| GET | `/costs/{account_id}/forecast` | `start_date`, `end_date` | 90-day cost forecast |
| GET | `/costs/{account_id}/breakdown` | `start_date`, `end_date` | Cost breakdown by service |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/health` | Health check (verifies DB connection) |
| GET | `/health/ready` | Readiness probe for Kubernetes |

---

## Testing

Tests are in `src/tests/` and run automatically in the CI/CD pipeline.

```bash
cd src

# Unit tests
pytest tests/unit/ -v

# Integration tests (uses in-memory SQLite — no DB required)
pytest tests/integration/ -v

# Smoke tests (requires a running application)
APP_URL=http://localhost:8000 pytest tests/smoke/ -v

# All tests with JUnit XML output
pytest -v --junitxml=results.xml
```

| Type | Location | Scope |
|------|----------|-------|
| Unit | `tests/unit/` | Security functions, schema validation, AWS service mocking |
| Integration | `tests/integration/` | Full API flow with SQLite in-memory database |
| Smoke | `tests/smoke/` | End-to-end tests against a live deployed application |

Test results are uploaded as artifacts in GitHub Actions and reported to SonarCloud for quality gate analysis.
