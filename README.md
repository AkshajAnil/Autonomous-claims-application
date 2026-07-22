# 🤖 Autonomous Claims Processing System

An enterprise-grade, agentic insurance claims processing platform powered by **LangChain ReAct agents**, **Google Gemini 1.5 Flash Multimodal Vision**, **Qdrant Vector Policy RAG**, **XGBoost Machine Learning Fraud Scoring**, and the **Model Context Protocol (MCP)**.

---

## 🏛️ System Architecture

```mermaid
graph TD
    User([👤 User / Adjuster]) <-->|HTTP / SSE| Nginx[🌐 Nginx Reverse Proxy]
    
    subgraph Client Layer
        Nginx <--> Frontend[💻 React + Vite Dashboard]
    end

    subgraph API & Agentic Core Layer
        Nginx <--> Backend[⚙️ FastAPI Backend Service]
        Backend <--> LangChain[🧠 LangChain ReAct Agent]
        LangChain <--> MCPClient[🔌 MCP Client]
        MCPClient <--> MCPServer[🛠️ MCP Tool Server]
    end

    subgraph Verification & Intelligence Layer
        MCPServer -->|Vision OCR| Gemini[👁️ Gemini 1.5 Flash Vision]
        MCPServer -->|Policy RAG| Qdrant[(🔍 Qdrant Vector Store)]
        MCPServer -->|ML Scoring| XGBoost[📊 XGBoost Fraud Model]
        MCPServer -->|Geocoding| OSM[🗺️ OpenStreetMap API]
        MCPServer -->|Weather| OpenMeteo[🌤️ Open-Meteo Archive API]
        MCPServer -->|Disasters| GDACS[🌪️ GDACS Disaster Alert Feed]
    end

    subgraph Persistence & Cache Layer
        Backend <--> Postgres[(🐘 PostgreSQL Database)]
        Backend <--> Redis[(⚡ Redis Session Cache)]
        Backend <--> B2[(📦 Backblaze B2 / S3 Object Storage)]
    end
```

---

## 📂 Production Microservice Directory Structure

```text
claims-agent/
├── backend/                   # ⚙️ FastAPI API & Agent Infrastructure
│   ├── app/                   # Core application modules & MCP tools
│   ├── Dockerfile             # Standalone Backend container definition
│   └── requirements.txt       # Pinned Python dependencies
│
├── frontend/                  # 💻 React Dashboard User Interface
│   ├── src/                   # React components & state management
│   └── Dockerfile             # Multi-stage Nginx Frontend container definition
│
├── nginx/                     # 🌐 Nginx Reverse Proxy Service
│   └── nginx.conf             # Route load balancing & SSE streaming proxy config
│
├── postgres/                  # 🐘 PostgreSQL Database Service
│   └── init.sql               # Database extensions & setup script
│
├── redis/                     # ⚡ Redis Session Cache Service
│   └── redis.conf             # Production Redis cache configuration
│
├── .python-version            # 📌 Runtime version pin (Python 3.11.9)
├── docker-compose.yml         # 🐳 Full-stack microservice orchestration
└── DEPLOYMENT.md              # 📖 Production Deployment Documentation
```

---

## 🚀 Quick Start (Local Docker Compose)

To launch the full microservice stack on your local machine:

```bash
# 1. Clone repository
git clone https://github.com/AkshajAnil/Autonomous-claims-application.git
cd Autonomous-claims-application

# 2. Configure environment
cp backend/.env.example backend/.env
# (Edit backend/.env and insert your GEMINI_API_KEY)

# 3. Start single-instance Docker stack
docker-compose up --build -d
```

Access the dashboard at **http://localhost**!

For detailed cloud deployment instructions (Render, AWS, DigitalOcean, VPS), refer to **[DEPLOYMENT.md](DEPLOYMENT.md)**.
