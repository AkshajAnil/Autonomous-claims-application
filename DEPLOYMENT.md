# 📖 Comprehensive Deployment Guide

This guide provides step-by-step instructions for deploying the **Autonomous Claims Processing System** under two production architecture patterns:

1. **[Pattern A: Single-Instance Docker Compose Deployment](#pattern-a-single-instance-docker-compose-deployment)** *(Ideal for single VPS hosts like DigitalOcean, AWS EC2, Linode, or Staging)*
2. **[Pattern B: Distributed Cloud Microservices Deployment](#pattern-b-distributed-cloud-microservices-deployment)** *(Ideal for Enterprise Cloud Platforms like Render, AWS ECS/RDS, GCP Cloud Run)*

---

## 🏛️ Architecture & Component Interaction

```mermaid
graph TD
    Nginx[🌐 Nginx Reverse Proxy / Load Balancer] -->|Port 80| Frontend[💻 React Dashboard Frontend]
    Nginx -->|Port 8000| Backend[⚙️ FastAPI Backend Service]
    
    Backend -->|Database Queries| Postgres[(🐘 PostgreSQL Database)]
    Backend -->|Session Tokens| Redis[(⚡ Redis Cache)]
    Backend -->|Evidence Storage| Storage[(📦 Backblaze B2 S3 Object Storage)]
```

---

## Pattern A: Single-Instance Docker Compose Deployment

Deploying the complete microservice cluster onto a single server or Virtual Private Server (VPS).

### System Prerequisites
- **OS:** Ubuntu 22.04 LTS / Debian 12 / RHEL 9 / Windows Server
- **Hardware:** Minimum 2 vCPUs, 4GB RAM, 20GB SSD Storage
- **Installed Software:** Docker Engine v24.0+ and Docker Compose v2.20+

---

### Step-by-Step Deployment Commands

#### Step 1: Clone the Codebase
```bash
git clone https://github.com/AkshajAnil/Autonomous-claims-application.git
cd Autonomous-claims-application
```

#### Step 2: Configure Production Environment File
Create the `.env` file in the `backend/` directory:

```bash
cat << 'EOF' > backend/.env
DATABASE_URL=postgresql://claims_user:claims_pass@postgres_db:5432/claims_db
REDIS_URL=redis://redis_cache:6379/0
GEMINI_API_KEY=your_actual_google_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
CORS_ORIGINS=*
JWT_SECRET=supersecretkey
JWT_EXPIRATION_MINUTES=60
INVESTIGATION_VERSION=v1.0

# Backblaze B2 S3 Object Storage (REQUIRED for Evidence Storage)
# Note: S3_ENDPOINT depends on your bucket region (e.g. s3.us-west-004.backblazeb2.com, s3.us-east-005.backblazeb2.com)
S3_ENDPOINT=s3.us-west-004.backblazeb2.com
S3_ACCESS_KEY=your_backblaze_key_id
S3_SECRET_KEY=your_backblaze_application_key
S3_BUCKET=your_bucket_name
S3_SECURE=true
EOF
```

#### Step 3: Build & Launch Container Stack
Run Docker Compose in detached mode:

```bash
docker-compose up --build -d
```

#### Step 4: Verify Service Health
Check that all containers are active and healthy:

```bash
docker-compose ps
```

#### Step 5: Verify Endpoints
- **Web UI Dashboard:** Open `http://your-server-ip`
- **Backend Health Check:** Run `curl http://your-server-ip/api/health` $\rightarrow$ `{"status":"ok"}`

---

## Pattern B: Distributed Cloud Microservices Deployment

Deploying components across managed cloud services (Render, AWS, GCP, Vercel) for high scalability and availability.

### 1. PostgreSQL Database Instance (Managed)
Create a managed PostgreSQL database (e.g., Render Postgres, AWS RDS, Supabase):
- Database Name: `claims_db`
- Save the connection URI: `postgresql://user:password@host:5432/claims_db`

### 2. Redis Session Cache Instance (Managed)
Create a managed Redis instance (e.g., Render Redis, AWS ElastiCache, Upstash):
- Save the connection URI: `redis://default:password@redis-host:6379/0`

### 3. Backend Microservice Deployment (Render / AWS ECS / GCP Cloud Run)
Deploy the [`backend/`](file:///C:/Users/Akshaj%20Anil/Documents/Codex/2026-07-01/most-credit-scoring-is-built-around/claims-agent/backend) directory as a Web Service:
- **Root Directory:** `backend`
- **Runtime:** `Python 3` (Version `3.11.9`)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables:**
  - `DATABASE_URL`: *(Your Managed Postgres Connection String)*
  - `REDIS_URL`: *(Your Managed Redis Connection String)*
  - `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
  - `PYTHON_VERSION`: `3.11.9`
  - `S3_ENDPOINT`: *(Your Backblaze B2 S3 Endpoint for your region, e.g. `s3.us-west-004.backblazeb2.com`)*
  - `S3_ACCESS_KEY`: *(Your Backblaze B2 keyID - REQUIRED)*
  - `S3_SECRET_KEY`: *(Your Backblaze B2 applicationKey - REQUIRED)*
  - `S3_BUCKET`: *(Your Backblaze B2 bucket name - REQUIRED)*

### 4. Frontend Microservice Deployment (Vercel / Netlify / AWS S3)
Deploy the [`frontend/`](file:///C:/Users/Akshaj%20Anil/Documents/Codex/2026-07-01/most-credit-scoring-is-built-around/claims-agent/frontend) directory:
- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Publish Directory:** `dist`

---

## ⚙️ Environment Variables Reference

| Variable | Required | Default Value | Description |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | **YES** | `postgresql://...` | PostgreSQL connection string |
| `GEMINI_API_KEY` | **YES** | `""` | Google Gemini API key for multimodal vision & LLM |
| `S3_ENDPOINT` | **YES** | `s3.us-west-004.backblazeb2.com` | Backblaze B2 / AWS S3 Endpoint URL (varies by bucket region) |
| `S3_ACCESS_KEY` | **YES** | `""` | Backblaze B2 `keyID` / S3 Access Key |
| `S3_SECRET_KEY` | **YES** | `""` | Backblaze B2 `applicationKey` / S3 Secret Key |
| `S3_BUCKET` | **YES** | `claim-evidence` | Target storage bucket name |
| `REDIS_URL` | OPTIONAL | `redis://localhost:6379/0` | Redis session cache URL (falls back to memory if offline) |
| `JWT_SECRET` | **YES** | `supersecretkey` | HMAC SHA-256 key for signing auth tokens |
| `JWT_EXPIRATION_MINUTES` | OPTIONAL | `60` | JWT token expiration time in minutes |

---

## 🔑 Default Initial Credentials

When the backend starts for the first time, it automatically seeds three default accounts:

| Role | Username | Default Password | Customer / Employee ID |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `1234` | `ADM-SYSTEM` |
| **Claims Adjuster** | `adjuster_user` | `1234` | `ADJ-A12B98C` |
| **Customer** | `customer_user` | `1234` | `CUST-C7F8B2E` |

> ⚠️ **Security Notice:** Change these default passwords immediately after initial setup!
