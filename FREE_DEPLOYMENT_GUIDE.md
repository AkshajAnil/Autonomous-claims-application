# 100% Free Deployment Guide for GitHub Repository
**Repository:** [https://github.com/AkshajAnil/Autonomous-claims-application](https://github.com/AkshajAnil/Autonomous-claims-application)

This guide provides step-by-step instructions to deploy your repository for **100% FREE** using **Render** (Backend), **Neon/Supabase** (PostgreSQL Database), and **Vercel** (Frontend).

---

## 🗄️ Step 1: Create a Free PostgreSQL Database (Neon.tech or Supabase)

1. Go to [https://neon.tech](https://neon.tech) or [https://supabase.com](https://supabase.com) and create a free account.
2. Click **Create New Project** and name it `claims-db`.
3. Select PostgreSQL.
4. Copy the connection string (`DATABASE_URL`). It will look like:
   `postgresql://user:password@ep-cool-db.us-east-2.aws.neon.tech/neondb?sslmode=require`

---

## ⚙️ Step 2: Deploy Backend for Free (Render.com)

1. Go to [https://render.com](https://render.com) and sign in with GitHub.
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select your GitHub repository: `AkshajAnil/Autonomous-claims-application`.
4. Configure the Web Service settings:
   - **Name:** `claims-backend`
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
5. Scroll down to **Environment Variables** and add:
   - `DATABASE_URL` = *(Paste connection string from Step 1)*
   - `GEMINI_API_KEY` = *(Paste your Google Gemini API Key)*
   - `SECRET_KEY` = *(Any random long string)*
6. Click **Create Web Service**.
7. Copy your backend URL once live: e.g. `https://claims-backend.onrender.com`.

---

## 🌐 Step 3: Deploy Frontend for Free (Vercel.com)

1. Go to [https://vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **Add New...** $\rightarrow$ **Project**.
3. Import your GitHub repository `AkshajAnil/Autonomous-claims-application`.
4. Configure Project:
   - **Framework Preset:** `Vite`
   - **Root Directory:** Edit $\rightarrow$ Select `frontend`
5. Expand **Environment Variables** and add:
   - **Key:** `VITE_API_BASE`
   - **Value:** `https://claims-backend.onrender.com` *(your backend URL from Step 2)*
6. Click **Deploy**.

---

## 🎉 Your Platform is Live for Free!

- **Frontend Live URL:** `https://autonomous-claims-application.vercel.app`
- **Backend Live API:** `https://claims-backend.onrender.com`
- **Database:** Free Cloud PostgreSQL on Neon/Supabase.
