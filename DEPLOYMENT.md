# 🏗️ Production Distributed Microservices Deployment Architecture

This project is structured as a fully decoupled, production-grade microservice application. Each component can be deployed independently on **separate cloud instances/servers** or orchestrated together.

---

## 🏛️ Microservice Architecture & Instance Breakdown

```
 ┌────────────────┐       ┌────────────────┐       ┌────────────────────────┐
 │ Frontend Host  │ ────► │ Nginx Proxy /  │ ────► │ FastAPI Backend        │
 │ (Vercel/S3/CDN)│       │ Load Balancer  │       │ (Instance 1..N)        │
 └────────────────┘       └────────────────┘       └───────────┬────────────┘
                                                               │
                                               ┌───────────────┴───────────────┐
                                               ▼                               ▼
                                    ┌────────────────────┐          ┌────────────────────┐
                                    │ PostgreSQL Database│          │ Redis Cache Cluster│
                                    │ (Managed Instance) │          │ (Managed Instance) │
                                    └────────────────────┘          └────────────────────┘
```

---

## 1. Backend Microservice Instance (`/backend`)
Deployed as an isolated Python API container or server.

- **Independent Files:** `Dockerfile`, `Procfile`, `.python-version`, `requirements.txt`, `.env.example`
- **Port:** `8000`
- **Environment Variables Needed:**
  - `DATABASE_URL`: Connection string to PostgreSQL instance
  - `REDIS_URL`: Connection string to Redis instance
  - `GEMINI_API_KEY`: Google Gemini AI Key
  - `S3_ENDPOINT`: Backblaze B2 / AWS S3 Endpoint

### Standalone Backend Deployment:
```bash
cd backend
docker build -t claims-backend .
docker run -p 8000:8000 --env-file .env claims-backend
```

---

## 2. Frontend Microservice Instance (`/frontend`)
Deployed independently as a static web app or React container.

- **Independent Files:** `Dockerfile`, `package.json`, `vite.config.js`
- **Port:** `80` (or host port)

### Standalone Frontend Deployment:
```bash
cd frontend
docker build -t claims-frontend .
docker run -p 80:80 claims-frontend
```

---

## 3. Database & Cache Instances
- **PostgreSQL 15+ Instance:** Managed database (e.g. AWS RDS, Render Postgres, Supabase).
- **Redis 7+ Instance:** Managed cache (e.g. AWS ElastiCache, Render Redis, Upstash).

---

## 4. Single-Command Local/Staging Orchestration
To test the full distributed stack locally or on a single staging VPS:

```bash
docker-compose up --build -d
```
