# 🚀 Production & Free Cloud Deployment Guide

This repository contains the complete **Autonomous Claims Processing System**. You can deploy it using **Render (Free Cloud)** or run it locally/on VPS using **Docker Compose (with Nginx & Redis)**.

---

## Option 1: Free Cloud Deployment on Render (Recommended)

### Step 1: Create a PostgreSQL Database on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** $\rightarrow$ **PostgreSQL**.
2. Set Name: `claims-db`
3. Select **Free Plan**.
4. Once created, copy the **Internal Database URL** (or External Database URL).

### Step 2: Create a Web Service for Backend
1. Click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub Repository: `Autonomous-claims-application`.
3. Set the following settings:
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add the following **Environment Variables**:
   - `DATABASE_URL`: *(Paste your Render PostgreSQL URL)*
   - `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
   - `PYTHON_VERSION`: `3.11.9`
   - `S3_ENDPOINT`: *(Optional: Backblaze B2 S3 endpoint, e.g., `s3.us-west-004.backblazeb2.com`)*
   - `S3_ACCESS_KEY`: *(Optional: Backblaze B2 keyID)*
   - `S3_SECRET_KEY`: *(Optional: Backblaze B2 applicationKey)*
   - `S3_BUCKET`: *(Optional: Backblaze B2 bucket name)*
   - `REDIS_URL`: *(Optional: Render Redis internal URL)*
5. Click **Create Web Service**.

---

## Option 2: Full Docker Stack Deployment (Nginx + Redis + Postgres)

Run the entire microservice architecture (Nginx Load Balancer, 3 Backend Replicas, Redis Cache, Postgres Database, React Frontend) with a single command:

```bash
docker-compose up --build -d
```

### Stack Architecture:
- 🌐 **Nginx Load Balancer (`:80`):** Handles incoming web traffic, load-balances requests across 3 backend containers using `least_conn`, and proxies SSE live streams without buffering.
- ⚡ **Redis Cache (`:6379`):** High-speed in-memory session management and state caching.
- 🐘 **PostgreSQL DB (`:5432`):** Persistent transactional storage for claims, audit logs, and users.
- ⚙️ **FastAPI Backend (3 Replicas):** Autonomous AI claims evaluation engine.
- 💻 **React Frontend:** User dashboard.

---

## 📁 Repository Structure Overview

```
├── .python-version      # Force Python 3.11.9 runtime
├── DEPLOYMENT.md        # Official Deployment Guide
├── docker-compose.yml   # Multi-container orchestration (Nginx, Redis, Postgres, Backend x3, Frontend)
├── nginx.conf           # Load balancer & SSE streaming proxy config
├── backend/             # FastAPI App, AI Agent & ML Services
│   ├── app/             # Application source code
│   └── requirements.txt # Pinned Python dependencies
└── frontend/            # React UI Dashboard
```
