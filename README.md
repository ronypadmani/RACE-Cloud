# RACE-Cloud: Resource Analysis & Cost Explorer for Cloud

**Cloud-Native Resource Monitoring and Cost Optimization Platform on AWS**

> Academic SGP Project — Advisory-Only Platform (No Automatic AWS Changes)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Login /  │ │Dashboard │ │  Report  │ │   IAM Setup       │  │
│  │ Register │ │  (Charts)│ │  Viewer  │ │   Guide           │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────────────────┘  │
│       │             │            │                               │
│       └─────────────┼────────────┘                               │
│                     │  HTTP REST API (JSON)                      │
└─────────────────────┼───────────────────────────────────────────┘
                      │
              ┌───────▼───────┐
              │   FLASK API   │
              │   BACKEND     │
              │               │
              │ ┌───────────┐ │
              │ │  Auth &   │ │
              │ │  Session  │ │
              │ └───────────┘ │
              │ ┌───────────┐ │       ┌─────────────────┐
              │ │  AWS      │ │──────►│   AWS APIs       │
              │ │  Service  │ │ boto3 │ • IAM            │
              │ │  Layer    │ │◄──────│ • EC2            │
              │ └───────────┘ │       │ • CloudWatch     │
              │ ┌───────────┐ │       │ • Cost Explorer  │
              │ │  Rule     │ │       │ • S3             │
              │ │  Engine   │ │       │ • RDS            │
              │ └───────────┘ │       └─────────────────┘
              │ ┌───────────┐ │
              │ │  Report   │ │
              │ │  Generator│ │
              │ └───────────┘ │
              │       │       │
              └───────┼───────┘
                      │
              ┌───────▼───────┐
              │   SQLite DB   │
              │ • Users       │
              │ • AWS Accounts│
              │ • Recomm.     │
              │   History     │
              └───────────────┘
```

### Architecture Principles

1. **Strict Separation**: Frontend NEVER communicates with AWS directly
2. **Backend-Only AWS Access**: All boto3 calls happen exclusively in the backend
3. **Credential Security**: AWS keys encrypted at rest using Fernet symmetric encryption
4. **Read-Only IAM**: Platform uses IAM users with read-only policies only
5. **Advisory Only**: No write/modify operations on AWS resources — recommendations only
6. **Modular Rule Engine**: Pluggable rules with severity levels and savings estimates

---

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python, Flask, boto3              |
| Frontend   | React, Recharts, React Router     |
| Database   | SQLite                            |
| AWS APIs   | IAM, EC2, CloudWatch, Cost Explorer, S3, RDS |
| Security   | Fernet encryption, bcrypt hashing |

---

## Project Execution Plan (2-Person Role Split)

### Person A — Backend Engineer
- Flask application setup and configuration
- Database schema design and ORM models
- Authentication system (signup/login/session)
- AWS integration layer (boto3 service classes)
- Rule engine architecture and rule implementation
- Report generation module
- API endpoint development
- Security: encryption, credential validation

### Person B — Frontend Engineer
- React project setup and routing
- Login / Registration pages
- IAM Setup Guide page (educational)
- AWS credential input form
- Dashboard layout (KPI cards, charts, tables)
- Report viewer and download functionality
- UI/UX polish (Power-BI-style design)
- Integration with backend APIs

---

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ (for React frontend build)
- AWS Free Tier account with IAM user (ReadOnlyAccess)

### Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python run.py
```
Backend runs on `http://localhost:5000`

### Frontend Setup
```bash
cd frontend
npm install
npm start
```
Frontend runs on `http://localhost:3000`

---

## Security Design

| Concern                | Solution                                              |
|------------------------|-------------------------------------------------------|
| AWS Key Storage        | Fernet-encrypted in SQLite, never plain text           |
| Password Storage       | bcrypt hashed with salt                                |
| API Authentication     | JWT tokens with expiration                             |
| CORS                   | Restricted to frontend origin only                     |
| AWS Permission Level   | IAM ReadOnlyAccess policy — no write/modify capability |
| Frontend AWS Access    | Blocked — all AWS calls go through backend only        |
| Report Data            | No credentials, logs, or raw metrics in output         |

---

## Database Schema

```sql
-- Users table
users (id, username, email, password_hash, created_at, updated_at)

-- AWS account metadata
aws_accounts (id, user_id, account_alias, encrypted_access_key, encrypted_secret_key,
              region, is_validated, last_synced, created_at)

-- Recommendation history
recommendations (id, user_id, aws_account_id, rule_id, resource_id, resource_type,
                 recommendation_text, severity, estimated_savings, status, created_at)

-- Analysis reports
reports (id, user_id, aws_account_id, report_data_json, created_at)
```

---

## API Endpoints

| Method | Endpoint                        | Description                        |
|--------|----------------------------------|------------------------------------|
| POST   | /api/auth/register              | User registration                  |
| POST   | /api/auth/login                 | User login (returns JWT)           |
| GET    | /api/auth/me                    | Current user profile               |
| POST   | /api/aws/credentials            | Submit & validate AWS credentials  |
| GET    | /api/aws/status                 | Check AWS connection status        |
| GET    | /api/aws/resources              | Fetch AWS resource summary         |
| GET    | /api/aws/costs                  | Fetch cost data                    |
| GET    | /api/aws/costs/breakdown        | Service-wise cost breakdown        |
| POST   | /api/analysis/run               | Run rule engine analysis           |
| GET    | /api/analysis/recommendations   | Get recommendations                |
| GET    | /api/reports/latest             | Get latest report                  |
| GET    | /api/reports/download           | Download report (HTML)             |
| GET    | /api/iam/guide                  | IAM setup guide content            |

---

## Rule Engine Rules

| # | Rule                      | Severity | Trigger                                        |
|---|---------------------------|----------|-------------------------------------------------|
| 1 | Underutilized EC2         | MEDIUM   | CPU avg < 10% over 14 days                     |
| 2 | Idle EC2                  | HIGH     | CPU avg < 2% over 7 days                       |
| 3 | Unused EBS Volumes        | MEDIUM   | Unattached EBS volumes                          |
| 4 | Oversized EC2             | MEDIUM   | CPU < 20%, consider downsizing instance type    |
| 5 | Cold S3 Data              | LOW      | S3 buckets with no access for 90+ days          |
| 6 | Idle RDS Instances        | HIGH     | RDS connections = 0 for 7+ days                 |
| 7 | High Monthly Cost Alert   | HIGH     | Monthly cost exceeds configurable threshold     |
| 8 | Old Generation Instances  | LOW      | EC2 using previous-gen instance types           |
| 9 | Unassociated Elastic IPs  | MEDIUM   | Elastic IPs not attached to running instances   |
|10 | GP2 to GP3 Migration      | LOW      | EBS gp2 volumes eligible for gp3 migration      |

---

## Future Enhancement Ideas (Design Only)

1. **Multi-Cloud Support** — Extend to Azure/GCP with pluggable cloud adapters
2. **Scheduled Analysis** — Cron-based periodic analysis with email alerts
3. **Team Collaboration** — Multi-user access with role-based permissions
4. **Cost Forecasting** — Trend-based cost projection using linear regression
5. **Custom Rules** — User-defined threshold rules via UI
6. **Slack/Teams Alerts** — Webhook-based notification integration
7. **Tagging Analysis** — Cost allocation by resource tags
8. **Budget Tracking** — AWS Budget vs actual spend comparison

---

## License

Academic project — For educational purposes only.

## Authors

SGP Team (2 Members) — Cloud-Native Resource Monitoring Platform
