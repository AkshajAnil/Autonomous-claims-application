# Autonomous Claims Agent

Full-stack cloud-ready implementation of an agentic insurance-claims workflow:

- React + Vite dashboard
- FastAPI backend
- PostgreSQL claim state
- Backblaze B2/S3-compatible image/object storage
- Qdrant policy RAG
- LangChain ReAct-style orchestrator
- MCP stdio tool server
- Server-Sent Events for live agent reasoning
- Gemini 1.5 Flash multimodal analysis

## Cloud Services

This project intentionally does not use Docker Compose or local service containers. Use:

- Railway PostgreSQL
- Backblaze B2 using its S3-compatible endpoint
- Qdrant Cloud

## Railway Backend

```powershell
cd backend
railway up
```

Railway runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Frontend On Vercel/Netlify

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL and submit a claim with images. The dashboard streams the agent's tool use and final routing decision from FastAPI.

## Required Environment

Set these in `backend/.env`:

- `DATABASE_URL`
- `S3_ENDPOINT`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_BUCKET`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `GEMINI_API_KEY`

`GEMINI_API_KEY` is required for live multimodal image analysis. The rest are required because this version uses the real cloud stack now, not local placeholders.
