# ApexIntel

Autonomous multi-agent pipeline that discovers top performers in any field and synthesises their strategies into structured, actionable Obsidian knowledge vaults.

## Features

- **Querying Agent** — Gemini 2.5 Flash generates and self-scores Tavily search queries, retrying with feedback if quality falls below threshold
- **URL Extractor** — Tavily Extract pulls full article content from every discovered strategy URL
- **Synthesizer Agent** — five Gemini sub-agents produce three Obsidian notes per performer: strategy overview, phased action tasks, and annotated sources
- **Structure Validation** — a validator agent scores each note and a repair agent fixes structural failures automatically
- **Live Log Streaming** — real-time pipeline progress via Server-Sent Events
- **Notes Vault Viewer** — browse and copy generated Markdown notes directly in the UI
- **Arize Phoenix Observability** — every LLM call traced to a per-job Phoenix Cloud project
- **Concurrent-safe** — isolated JobContext per run, no shared state between concurrent pipelines

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Gemini 2.5 Flash via Vertex AI |
| Agent framework | Google ADK (Agent Development Kit) |
| Search | Tavily Search + Tavily Extract |
| Backend | FastAPI, Python 3.12, Server-Sent Events |
| Frontend | React 18, Vite |
| Infrastructure | Google Cloud Run, Google Cloud Storage |
| Observability | Arize Phoenix Cloud (OTLP tracing) |
| Secrets | Google Cloud Secret Manager |

## Prerequisites

- Python 3.12+
- Node.js 18+
- Google Cloud CLI (`gcloud`) authenticated
- A GCP project with these APIs enabled:
  - Vertex AI (`aiplatform.googleapis.com`)
  - Cloud Run (`run.googleapis.com`)
  - Cloud Storage (`storage.googleapis.com`)
  - Secret Manager (`secretmanager.googleapis.com`)
  - Artifact Registry (`artifactregistry.googleapis.com`)
- Tavily API key — https://tavily.com
- Arize Phoenix API key — https://app.phoenix.arize.com

## Setup

### 1 — Clone the repo

```bash
git clone https://github.com/yourteam/apexintel.git
cd apexintel
```

### 2 — Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your_gcp_project_id
GOOGLE_CLOUD_LOCATION=us-central1
TAVILY_API_KEY=tvly-your_key_here
PHOENIX_API_KEY=your_phoenix_api_key_here
GCS_BUCKET_NAME=apexintel-workspaces-your_project_id
```

### 3 — Install backend dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 4 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5 — Authenticate locally with GCP

```bash
gcloud auth application-default login
```

## Running Locally

Open two terminals from the `apexintel/` root:

```bash
# Terminal 1 — backend
source backend/venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

```bash
# Terminal 2 — frontend
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

## Deploying to Google Cloud

### Build and push backend image

```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/apexintel/backend:latest .
```

### Deploy backend to Cloud Run

```bash
gcloud run deploy apexintel-backend \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/apexintel/backend:latest \
  --region us-central1 \
  --min-instances 1 \
  --memory 4Gi \
  --cpu 4 \
  --timeout 3600 \
  --set-env-vars GCS_BUCKET_NAME=apexintel-workspaces-YOUR_PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1 \
  --set-secrets TAVILY_API_KEY=TAVILY_API_KEY:latest,PHOENIX_API_KEY=PHOENIX_API_KEY:latest
```

### Deploy frontend to Firebase Hosting

```bash
cd frontend
VITE_API_URL=https://your-cloud-run-url.a.run.app npm run build
firebase deploy
```

## How to Use

1. Open the app and click **New Run**
2. Type a field — e.g. `venture capital`, `competitive programming`, `machine learning`
3. Click **Launch Pipeline** and watch live logs stream in real time
4. When complete, click **View Notes** to browse the generated Obsidian vault
5. Copy any note's Markdown or click **Open in Obsidian** to import directly
6. Click the **Phoenix Traces** button to inspect every LLM call for that run

## License

MIT — see [LICENSE](./LICENSE)
