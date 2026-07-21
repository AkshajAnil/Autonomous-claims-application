# Deployment Guide – Universal AI Claims Platform

This guide outlines the recommended platforms and steps to deploy the **Universal AI Claims Platform** to production.

---

## 🚀 Option 1: VPS with Docker & Nginx (Recommended for Full Control & Cost)
**Platforms:** DigitalOcean Droplet ($12/mo), AWS EC2 (t3.medium), Hetzner, GCP Compute Engine.

### Steps:
1. **Provision Linux Server:** Spin up an Ubuntu 22.04 LTS instance with at least 2GB RAM and Docker installed.
2. **Clone Codebase:**
   ```bash
   git clone <your-repo-url> /var/www/claims-platform
   cd /var/www/claims-platform
   ```
3. **Configure Environment Variables:**
   Create `.env` in the root directory:
   ```env
   GEMINI_API_KEY=your_google_gemini_api_key
   SECRET_KEY=your_production_secret_key
   POSTGRES_DB=claims_db
   POSTGRES_USER=claims_user
   POSTGRES_PASSWORD=your_secure_db_password
   ```
4. **Build & Start Containers:**
   ```bash
   docker-compose up -d --build
   ```
5. **Enable HTTPS / SSL (Let's Encrypt):**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

---

## ☁️ Option 2: Render.com / Railway.app (Easiest Managed Deployment)
**Platforms:** Render.com, Railway.app, Fly.io.

### Steps:
1. **Database:** Create a managed PostgreSQL database instance on Render/Railway and copy the `DATABASE_URL`.
2. **Backend Service:**
   - Connect your GitHub repository.
   - Environment: `Python 3.11`
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Add `GEMINI_API_KEY`, `DATABASE_URL`, and `SECRET_KEY` in environment settings.
3. **Frontend Service (Vercel / Netlify):**
   - Connect the `frontend` folder to Vercel/Netlify.
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Environment Variable: `VITE_API_BASE=https://your-backend-url.onrender.com`

---

## 🌩️ Option 3: AWS App Runner + Amazon RDS (Enterprise Cloud)
**Platforms:** AWS App Runner, AWS ECS (Fargate), Amazon RDS PostgreSQL.

### Steps:
1. **Database:** Create an Amazon RDS PostgreSQL instance.
2. **Backend:** Deploy the backend Dockerfile to **AWS App Runner** or **AWS ECS Fargate**.
3. **Frontend:** Deploy static assets to **AWS S3 + CloudFront** CDN.
4. **Load Balancer:** Use AWS Application Load Balancer (ALB) with SSL certificates managed by AWS ACM.

---

## 🔒 Security Checklist for Production
- [ ] Set `SECRET_KEY` in `backend/app/config.py` to a secure random 64-character token.
- [ ] Ensure `CORS_ORIGINS` strictly permits your production frontend domain.
- [ ] Enforce SSL/TLS HTTPS certificates across all API endpoints.
- [ ] Enable PostgreSQL connection SSL mode (`sslmode=require`).
