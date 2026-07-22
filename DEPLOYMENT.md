# 📖 Comprehensive Deployment Guide

This guide provides step-by-step instructions for deploying the **Autonomous Claims Processing System** under two production architecture patterns:

1. **[Pattern A: Local & Single-Instance Server Deployment](#pattern-a-local--single-instance-server-deployment)** *(Local development or VPS deployment)*
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

## Pattern A: Local & Single-Instance Server Deployment

### 💻 Option 1: Direct Local Execution (Without Docker)

#### Step 1: Run Backend Service
```bash
cd backend
cp .env.example .env
# Edit .env and configure credentials

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 2: Run Frontend Service
```bash
cd frontend
npm install
npm run dev
```

---

### 🐳 Option 2: Docker Compose Orchestration

#### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name
```

#### Step 2: Configure Environment
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and populate your environment variables
```

#### Step 3: Launch Stack
```bash
docker-compose up --build -d
```

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

### 3. Backblaze B2 S3 Object Storage (Managed Cloud Bucket)
Create an S3-compatible Bucket on Backblaze B2 (or AWS S3 / Cloudflare R2):
- Save your credentials:
  - **S3 Endpoint:** `your_s3_endpoint_here`
  - **Access Key (`keyID`):** `your_s3_access_key_here`
  - **Secret Key (`applicationKey`):** `your_s3_secret_key_here`
  - **Bucket Name:** `your_s3_bucket_name_here`

### 4. Backend Microservice Deployment (Render / AWS ECS / GCP Cloud Run)
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
  - `S3_ENDPOINT`: *(Your S3 Endpoint - REQUIRED)*
  - `S3_ACCESS_KEY`: *(Your S3 Access Key - REQUIRED)*
  - `S3_SECRET_KEY`: *(Your S3 Secret Key - REQUIRED)*
  - `S3_BUCKET`: *(Your S3 Bucket Name - REQUIRED)*

### 5. Frontend Microservice Deployment (Vercel / Netlify / AWS S3)
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
| `S3_ENDPOINT` | **YES** | `""` | Backblaze B2 / AWS S3 Endpoint URL (e.g., `s3.us-west-004.backblazeb2.com`) |
| `S3_ACCESS_KEY` | **YES** | `""` | Backblaze B2 `keyID` / S3 Access Key |
| `S3_SECRET_KEY` | **YES** | `""` | Backblaze B2 `applicationKey` / S3 Secret Key |
| `S3_BUCKET` | **YES** | `""` | Target storage bucket name |
| `REDIS_URL` | OPTIONAL | `""` | Redis session cache URL (falls back to local memory if offline) |
| `JWT_SECRET` | **YES** | `""` | Secret key for signing auth tokens (e.g. `your_jwt_secret_here`) |
| `JWT_EXPIRATION_MINUTES` | OPTIONAL | `60` | JWT token expiration time in minutes |

---

## 🔑 Default Initial Credentials

When the backend starts for the first time, it automatically seeds the initial System Admin account:

| Role | Username | Default Password | Customer / Employee ID |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `1234` | `ADM-SYSTEM` |

> ⚠️ **Security Notice:** Change these default passwords immediately after initial setup!
