# Cloud Resource Cost Optimizer

A full-stack solution for monitoring, analyzing, and optimizing AWS cloud costs. Built with a FastAPI backend and PostgreSQL, deployed on a self-managed Kubernetes cluster provisioned entirely with Infrastructure as Code.

Besides reading the bill, it explains it: an AI advisor that sizes an AWS architecture and prices it from the live AWS Price List, an anomaly detector that finds cost spikes, and a rightsizing check on real CPU data. The language model never has the last word: code checks every number it returns, and every claim in this README about quality is a measured result in [`docs/experiments`](docs/experiments).

**Read next:** [`docs/DECISIONS.md`](docs/DECISIONS.md) (why it is built this way) and [`docs/experiments`](docs/experiments) (measured results).

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Local Development](#local-development)
- [Demo Without AWS](#demo-without-aws)
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
│  │  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │cost-optimizer│  │  monitoring │  │   argocd    │   │ │
│  │  │  namespace   │  │  namespace  │  │  namespace  │   │ │
│  │  │              │  │             │  │             │   │ │
│  │  │  FastAPI app │  │  Victoria   │  │   ArgoCD    │   │ │
│  │  │  PostgreSQL  │  │  Metrics    │  │             │   │ │
│  │  │              │  │  Grafana    │  │             │   │ │
│  │  │              │  │  Loki       │  │             │   │ │
│  │  │              │  │  Promtail   │  │             │   │ │
│  │  │              │  │  Alertmgr   │  │             │   │ │
│  │  └──────────────┘  └─────────────┘  └─────────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐   │
│  │   ECR    │  │    S3    │  │  Secrets   │  │   IAM   │   │
│  │  Docker  │  │ reports  │  │  Manager   │  │  roles  │   │
│  │  images  │  │ backups  │  │  kubeconf  │  │         │   │
│  │          │  │ tf state │  │  ssh keys  │  │         │   │
│  └──────────┘  └──────────┘  └────────────┘  └─────────┘   │
└─────────────────────────────────────────────────────────────┘
```

The application interacts with the **AWS Cost Explorer API** by assuming IAM roles in connected customer accounts, fetching cost data without storing long-term credentials.

---

## Features

**Cost analysis**

- **Multi-Account AWS Integration** — Connect AWS accounts via IAM Role + External ID, no stored long-term credentials
- **Cost & Usage Analysis** — Queries by date range, granularity (daily/monthly), and dimension
- **Cost Forecasting** — Monthly cost predictions up to 90 days ahead (Cost Explorer forecast)
- **Service Cost Breakdown** — Cost distribution across AWS services sorted by spend

**Optimization**

- **AI Architecture Advisor** — Turns free-text requirements into an AWS architecture plan. Retrieval over a curated catalog finds the relevant guidance; the model proposes, and code verifies instance counts and capacity (`POST /advisor/recommend`)
- **Cost Estimate** — Monthly list price of a plan from the live AWS Price List API, with usage-based items, a range instead of a false single number, and cheaper alternatives such as reserved or Graviton (`POST /advisor/cost`)
- **Cost Anomaly Detection** — Rolling-median baseline plus Isolation Forest, with guardrails against false alarms. On demand (`/anomalies`) or as a Kubernetes CronJob (`anomalyDetection.enabled` in the Helm values)
- **Spike Explanation and Advice** — For each anomaly: which usage types and regions grew, then possible causes and next steps. Dollar amounts must come from the facts and evidence must point at usage types that really grew, otherwise the advice is dropped
- **Rightsizing** — Idle, downsize, upsize or keep for EC2 instances from CloudWatch CPU history; a downsize is proposed only if the projected load stays safe (`/rightsizing`)
- **Daily Cost Alerts** — A scheduled workflow checks the budget and anomalies and sends the result, with advice, to Telegram

**Quality**

- **Measured, not claimed** — Evaluation sets for the advisor and the spike advice, and benchmarks for the detector and the attribution, with results in [`docs/experiments`](docs/experiments)
- **Rate limit and size limit** on the advisor, because every call costs money

**Platform**

- **User Authentication** — Registration and login with JWT tokens
- **Automated Infrastructure** — Full IaC with Terraform and Ansible, dev and stage environments
- **Keyless CI** — GitHub Actions signs in to AWS with OIDC and a narrow role per environment and workflow
- **GitOps Deployment** — ArgoCD for Kubernetes-native continuous delivery
- **Database Migrations** — Alembic run as a Helm post-install hook
- **Comprehensive Monitoring** — Metrics, logs, and alerts out of the box
- **Security Scanning** — Trivy image scanning + SonarCloud static analysis on every build
- **Telegram Notifications** — Pipeline results and cost alerts

### Measured results

| What                                            | Result                                                                 | Details                                                       |
| ----------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------- |
| Anomaly detector (hybrid, 420 synthetic series) | precision 1.00, recall 0.92, F1 0.96; best of the four detectors tried | [anomaly-detection.md](docs/experiments/anomaly-detection.md) |
| Naming the usage type behind a spike            | 0.96 average, against 0.12 for "the biggest line of the bill"          | [spike-attribution.md](docs/experiments/spike-attribution.md) |

---

## Tech Stack

| Layer          | Technology                                                                                                                                            |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend        | Python 3.11, FastAPI, SQLAlchemy (async), Pydantic v2                                                                                                 |
| Database       | PostgreSQL, asyncpg, Alembic                                                                                                                          |
| Auth           | JWT, python-jose, passlib/bcrypt                                                                                                                      |
| AI / ML        | OpenAI-compatible LLM client (provider and model are settings), retrieval over a catalog stored in PostgreSQL, scikit-learn (Isolation Forest), NumPy |
| AWS data       | Cost Explorer, CloudWatch, Price List API                                                                                                             |
| Infrastructure | Terraform, AWS (EC2, RDS, ECR, S3, IAM, Secrets Manager, DynamoDB), GitHub OIDC                                                                       |
| Kubernetes     | kubeadm 1.28, Calico CNI, Helm 3                                                                                                                      |
| CI/CD          | GitHub Actions, ArgoCD, SonarCloud, Trivy                                                                                                             |
| Monitoring     | VictoriaMetrics, Grafana, Loki, Promtail, Alertmanager, Node Exporter                                                                                 |
| Provisioning   | Ansible, amazon.aws collection                                                                                                                        |
| Container      | Docker (multi-stage build)                                                                                                                            |

---

## Repository Structure

```
.
├── .github/workflows/
│   ├── ansible.yml          # Cluster provisioning workflow
│   ├── cost-alerts.yml      # Daily cost check and Telegram alerts
│   ├── deploy.yml           # Build, test, and deploy workflow
│   └── terraform.yml        # Infrastructure lifecycle workflow
├── ansible/
│   ├── inventory/dev/       # AWS EC2 dynamic inventory
│   ├── playbooks/           # site_k8s, site_k3s, master, worker, calico, helm, runner
│   └── roles/               # common, kubernetes, master, worker, helm, github-runner, calico
├── docs/
│   ├── DECISIONS.md         # Design decisions and known gaps
│   └── experiments/         # Measured results
├── docker/
│   └── Dockerfile           # Multi-stage Python build
├── helm/
│   ├── argocd/              # ArgoCD Helm chart (values, values-dev)
│   ├── cost-optimizer/      # Application Helm chart
│   └── monitoring/          # Full monitoring stack Helm chart
├── src/
│   ├── alembic/             # Database migrations
│   ├── app/
│   │   ├── api/v1/          # Routers: auth, users, aws_accounts, costs, anomalies, rightsizing, advisor, health
│   │   ├── core/            # Config, database, security, deps
│   │   ├── jobs/            # Commands: detect_anomalies, ingest_knowledge, evals, benchmarks
│   │   ├── knowledge/       # Advisor catalog, spike playbook, evaluation cases
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   └── services/        # Cost Explorer, advisor, pricing, anomalies, rightsizing, LLM client
│   ├── scripts/             # check_costs.py: the daily cost alert job
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

### AWS access (OIDC)

Workflows sign in to AWS with short-lived OIDC roles, so no AWS access key is stored in GitHub. The
roles are created once from `terraform/bootstrap`, with administrator credentials:

```bash
cd terraform/bootstrap
terraform init && terraform apply
terraform output aws_account_id
```

Each workflow runs in a GitHub Environment (`dev`, `stage`) and can assume only the roles of that
environment. See `docs/DECISIONS.md` (OIDC) for the permissions of every role.

### Required GitHub Variables

Configure these in **Settings → Secrets and variables → Actions → Variables**:

| Variable                   | Description                                                                               |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| `AWS_ACCOUNT_ID`           | AWS account ID (`terraform output aws_account_id`); workflows build the role ARNs from it |
| `AWS_COST_ALERTS_ROLE_ARN` | Role of the Cost Alerts workflow (`terraform output github_cost_alerts_role_arn`)         |
| `BUDGET_LIMIT`             | Monthly budget in dollars for the cost alerts                                             |
| `ANOMALY_THRESHOLD`        | Daily cost in dollars that triggers the simple anomaly alert                              |

### Required GitHub Secrets

Configure these in **Settings → Secrets and variables → Actions → Secrets** before running any workflow:

| Secret               | Description                             |
| -------------------- | --------------------------------------- |
| `AWS_REGION`         | AWS region (e.g. `us-east-1`)           |
| `DEV_SECRET_KEY`     | Application JWT secret key              |
| `DEV_DB_PASSWORD`    | PostgreSQL password for dev             |
| `SONAR_TOKEN`        | SonarCloud authentication token         |
| `TOKEN`              | GitHub token for SonarCloud             |
| `GH_RUNNER_PAT`      | GitHub PAT for runner registration      |
| `K3S_TOKEN`          | Token for k3s cluster (used by Ansible) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications    |
| `TELEGRAM_CHAT_ID`   | Telegram chat ID for notifications      |

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

## Demo Without AWS

The daily cost alert can run on invented data, so the whole path (anomaly detector, usage-type breakdown, advice, message) can be seen without an AWS account, an API key or a bill. From the repository root:

```bash
pip install -r src/requirements.txt

# Prints the notification to the terminal
DEMO=1 PYTHONPATH=src python src/scripts/check_costs.py

# Sends it to Telegram instead
DEMO=1 TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... PYTHONPATH=src python src/scripts/check_costs.py

# Advice from a real model instead of the script (costs about a cent with gpt-4o-mini)
DEMO=1 LLM_API_KEY=... LLM_MODEL=gpt-4o-mini PYTHONPATH=src python src/scripts/check_costs.py
```

The invented bill has five services with steady costs and a spike in NAT Gateway traffic two days ago. The run takes a few seconds and calls no AWS API. Every demo message starts with a `DEMO` line; without an API key the advice is written by a script (and says so), with a key it comes from the model and goes through the same checks as in production.

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

**Resources created:** VPC, subnets, Security Groups, EC2 instances (t3.medium), ECR repository, S3 buckets (reports + backups), IAM roles and policies, Secrets Manager secrets (SSH key, kubeconfig, ArgoCD password).

### Step 3 — Configure Kubernetes Cluster

Via GitHub Actions → **Ansible** workflow → select playbook.

**Supported playbooks:**

| Playbook            | Description                                |
| ------------------- | ------------------------------------------ |
| `site_k8s.yml`      | Full kubeadm cluster setup (recommended)   |
| `site_k3s.yml`      | Full k3s cluster setup                     |
| `common.yml`        | Base packages + kernel config              |
| `master_k8s.yml`    | Initialize Kubernetes master node          |
| `calico.yml`        | Install and configure Calico CNI           |
| `worker_k8s.yml`    | Join worker nodes to the cluster           |
| `helm_group.yml`    | Install Helm + create ECR pull secret      |
| `github_runner.yml` | Register self-hosted GitHub Actions runner |

**kubeadm flow (`site_k8s.yml`):**

```
common setup → kubernetes install → master init → calico CNI → worker join → helm install → github runner
```

**k3s flow (`site_k3s.yml`):**

```
common setup → k3s deploy → helm install → github runner
```

After completion, kubeconfig is automatically saved to AWS Secrets Manager as `cost-optimizer-dev-kubeconfig`.

---

## Kubernetes & Helm

### Namespaces

| Namespace        | Components                                                            |
| ---------------- | --------------------------------------------------------------------- |
| `cost-optimizer` | FastAPI application, PostgreSQL                                       |
| `monitoring`     | VictoriaMetrics, Grafana, Loki, Promtail, Node Exporter, Alertmanager |
| `argocd`         | ArgoCD server                                                         |

### Deploy Commands

**Application:**

```bash
helm dependency build ./helm/cost-optimizer --skip-refresh
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
helm dependency build ./helm/monitoring --skip-refresh
helm upgrade --install monitoring ./helm/monitoring \
  -f ./helm/monitoring/values-dev.yaml \
  --namespace monitoring --create-namespace \
  --timeout 600s --wait
```

**ArgoCD:**

```bash
helm dependency build ./helm/argocd --skip-refresh
helm upgrade --install argocd ./helm/argocd \
  -f ./helm/argocd/values-dev.yaml \
  --namespace argocd --create-namespace \
  --timeout 300s --wait
```

### Access Services in Dev

| Service         | NodePort | URL                                         |
| --------------- | -------- | ------------------------------------------- |
| Application     | 30080    | `http://<EC2_IP>:30080`                     |
| Grafana         | 30300    | `http://<EC2_IP>:30300` (admin / admin)     |
| ArgoCD          | 30808    | `http://<EC2_IP>:30808` (admin / see below) |
| VictoriaMetrics | 8428     | port-forward required                       |

**Get ArgoCD admin password:**

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Or from AWS Secrets Manager:
aws secretsmanager get-secret-value \
  --secret-id "cost-optimizer-dev-argocd-password" \
  --query SecretString --output text
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
sonarcloud ───────────────────────────────────────────────────────────────┐
                                                                           ▼
build-and-push ──► helm-deploy-dev ──────────────► run-tests ────────► notify
                        │
                        ├──► helm-deploy-monitoring-dev ──────────────────┤
                        └──► argo-cd-dev ────────────────────────────────┘
```

| Job                          | Runner        | Description                                                 |
| ---------------------------- | ------------- | ----------------------------------------------------------- |
| `sonarcloud`                 | ubuntu-latest | Static code analysis                                        |
| `build-and-push`             | ubuntu-latest | Build Docker image, Trivy scan, push to ECR                 |
| `helm-deploy-dev`            | self-hosted   | Deploy application via Helm                                 |
| `helm-deploy-monitoring-dev` | self-hosted   | Deploy monitoring stack via Helm                            |
| `argo-cd-dev`                | self-hosted   | Deploy ArgoCD via Helm (`continue-on-error: true` on login) |
| `run-tests`                  | self-hosted   | Unit, integration, and smoke tests                          |
| `notify`                     | ubuntu-latest | Telegram notification with full results                     |

> **Note:** Note: The ArgoCD login step uses `continue-on-error: true` because it is not a critical step — the application is already deployed via Helm in the previous job. The login only verifies that ArgoCD is accessible after deployment.

### `terraform.yml` — Infrastructure

Triggered on changes to `terraform/**` or manually.

| Action    | Trigger                    |
| --------- | -------------------------- |
| `plan`    | Push / PR to main + manual |
| `apply`   | Manual only                |
| `destroy` | Manual only                |

### `ansible.yml` — Cluster Provisioning

Manual trigger only. Supports both kubeadm (k8s) and k3s cluster flavors.

---

## Monitoring

### Stack Components

| Component       | Role                       | Dev            | Prod                |
| --------------- | -------------------------- | -------------- | ------------------- |
| VictoriaMetrics | Metrics storage            | 3d retention   | 14d + 20Gi PVC      |
| VM Agent        | Metrics scraping every 10s | enabled        | enabled             |
| Grafana         | Dashboards                 | NodePort 30300 | ClusterIP + Ingress |
| Loki            | Log aggregation            | filesystem     | filesystem          |
| Promtail        | Log shipping from pods     | enabled        | enabled             |
| Node Exporter   | Host-level metrics         | enabled        | enabled             |
| Alertmanager    | Alert routing              | disabled       | enabled             |

### Pre-configured Grafana Datasources

- **VictoriaMetrics** — `http://monitoring-victoria-metrics-single-server:8428` (default)
- **Loki** — `http://monitoring-loki:3100`

### Pre-configured Dashboards (prod)

- **Node Exporter Full** (gnetId: 1860)
- **Kubernetes Cluster** (gnetId: 315)

### Application Metrics

The FastAPI app exposes Prometheus metrics at `/metrics` via `prometheus-fastapi-instrumentator`. VictoriaMetrics agent scrapes it at `cost-optimizer.cost-optimizer.svc.cluster.local:80`.

---

## API Endpoints

Base URL: `/api/v1`

### Authentication

| Method | Path             | Description                     |
| ------ | ---------------- | ------------------------------- |
| POST   | `/auth/register` | Register a new user             |
| POST   | `/auth/login`    | Login, returns JWT access token |

### Users

| Method | Path        | Description                     |
| ------ | ----------- | ------------------------------- |
| GET    | `/users/me` | Get current user profile        |
| PUT    | `/users/me` | Update name, email, or password |
| DELETE | `/users/me` | Permanently delete account      |

### AWS Accounts

| Method | Path                 | Description                         |
| ------ | -------------------- | ----------------------------------- |
| POST   | `/aws_accounts/`     | Connect an AWS account via IAM Role |
| GET    | `/aws_accounts/`     | List all connected accounts         |
| GET    | `/aws_accounts/{id}` | Get details for a specific account  |

### Costs

| Method | Path                            | Query Params                                        | Description               |
| ------ | ------------------------------- | --------------------------------------------------- | ------------------------- |
| GET    | `/costs/{account_id}/costs`     | `start_date`, `end_date`, `granularity`, `group_by` | Cost and usage data       |
| GET    | `/costs/{account_id}/forecast`  | `start_date`, `end_date`                            | 90-day cost forecast      |
| GET    | `/costs/{account_id}/breakdown` | `start_date`, `end_date`                            | Cost breakdown by service |

### Anomalies

| Method | Path                                   | Query Params                        | Description                                      |
| ------ | -------------------------------------- | ----------------------------------- | ------------------------------------------------ |
| POST   | `/costs/{account_id}/anomalies/detect` | `days` (21–365, default 90)         | Analyse the cost history and store new anomalies |
| GET    | `/costs/{account_id}/anomalies`        | `start_date`, `end_date`, `service` | List stored anomalies                            |

### Rightsizing

| Method | Path                                     | Query Params                         | Description                                        |
| ------ | ---------------------------------------- | ------------------------------------ | -------------------------------------------------- |
| POST   | `/costs/{account_id}/rightsizing/detect` | `regions`, `days` (7–30, default 14) | Check EC2 instances against CloudWatch CPU history |
| GET    | `/costs/{account_id}/rightsizing`        | `action`                             | List stored recommendations                        |

### AI Advisor

| Method | Path                 | Description                                                           |
| ------ | -------------------- | --------------------------------------------------------------------- |
| POST   | `/advisor/recommend` | Architecture plan from free-text requirements (rate limited per user) |
| POST   | `/advisor/cost`      | Monthly list-price cost of a plan, with alternatives                  |

The advisor needs an LLM key (`LLM_API_KEY`; `LLM_PROVIDER`, `LLM_BASE_URL` and `LLM_MODEL` are settings, default model `gpt-4o-mini`) and a filled catalog: run `python -m app.jobs.ingest_knowledge` after the database is created.

### Health

| Method | Path             | Description                           |
| ------ | ---------------- | ------------------------------------- |
| GET    | `/health/health` | Health check (verifies DB connection) |
| GET    | `/health/ready`  | Readiness probe for Kubernetes        |

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

| Type        | Location             | Scope                                                      |
| ----------- | -------------------- | ---------------------------------------------------------- |
| Unit        | `tests/unit/`        | Security functions, schema validation, AWS service mocking |
| Integration | `tests/integration/` | Full API flow with SQLite in-memory database               |
| Smoke       | `tests/smoke/`       | End-to-end tests against a live deployed application       |

Test results are uploaded as artifacts in GitHub Actions and reported to SonarCloud for quality gate analysis.

### Evaluations and benchmarks

These measure quality and are described in [`docs/experiments`](docs/experiments). Run from `src`:

```bash
# Detector benchmark: no database, network or API key (about 3 minutes)
python -m app.jobs.anomaly_benchmark --series 20

# Usage-type attribution benchmark: no API key
python -m app.jobs.explain_benchmark --trials 500

# Advisor evaluation: uses the real LLM and the catalog in the database, costs a few cents
LLM_API_KEY=... python -m app.jobs.advisor_eval --runs 1

# Spike advice evaluation: real LLM, about 11 cents per run with gpt-4o
LLM_API_KEY=... LLM_MODEL=gpt-4o python -m app.jobs.spike_advice_eval --runs 1
```

The evaluations call a paid API, so they are not part of CI.

### What Smoke Tests Cover

- Health and readiness endpoints
- OpenAPI schema presence and required routes
- Auth registration and login flows
- JWT middleware enforcement
- User profile CRUD
- AWS account creation and listing
- Cost endpoint availability (without real AWS credentials)
