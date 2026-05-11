# Deployment Guide: Mutual Fund FAQ Assistant

This document provides step-by-step instructions for deploying the Mutual Fund FAQ Assistant with:
- **Backend**: Render (FastAPI + ChromaDB)
- **Frontend**: Vercel (Static HTML/JS)

---

## Architecture Overview

```
┌─────────────────┐         ┌─────────────────┐
│   Vercel (UI)   │────────▶│   Render (API)  │
│  Static HTML/JS │  HTTPS  │  FastAPI + RAG  │
└─────────────────┘         └─────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │   ChromaDB    │
                            │  Vector Store │
                            └───────────────┘
```

---

## Prerequisites

1. **Render Account**: [https://render.com](https://render.com)
2. **Vercel Account**: [https://vercel.com](https://vercel.com)
3. **GitHub Repository**: Project must be pushed to GitHub
4. **OpenAI API Key**: For LLM functionality (set as environment variable)
5. **Data Files**: ChromaDB index and chunked data must be committed to repository

---

## Part 1: Backend Deployment (Render)

### 1.1 Prepare Repository

Ensure your repository structure includes:
```
Milestone2/
├── phase3_reasoning_guardrails/
│   └── src/
│       ├── api.py
│       ├── orchestrator.py
│       ├── llm_client.py
│       └── answer_generator.py
├── phase2_retrieval_layer/
│   └── src/
│       └── (retrieval modules)
├── data/
│   ├── indexed/
│   │   └── (ChromaDB index files)
│   └── processed/
│       └── chunked_data_phase1.4.json
├── requirements.txt
└── render.yaml
```

### 1.2 Configure render.yaml

The `render.yaml` file at the repository root configures the Render deployment:

```yaml
services:
  - type: web
    name: hdfc-faq-assistant-api
    runtime: python
    buildCommand: cd Milestone2 && pip install -r requirements.txt
    startCommand: cd Milestone2 && uvicorn phase3_reasoning_guardrails.src.api:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: PORT
        value: 8000
    healthCheckPath: /health
```

### 1.3 Configure Environment Variables

Create environment variables in Render dashboard after deployment:

**Required:**
- `OPENAI_API_KEY`: Your OpenAI API key

**Optional:**
- `PYTHONUNBUFFERED`: 1
- `PORT`: 8000 (auto-set by Render)

### 1.4 Deploy to Render

#### Option A: Via Render Dashboard (Recommended)

1. Go to [https://render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `hdfc-faq-assistant-api`
   - **Region**: Choose nearest region (e.g., Oregon, Singapore)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `cd Milestone2 && pip install -r requirements.txt`
   - **Start Command**: `cd Milestone2 && uvicorn phase3_reasoning_guardrails.src.api:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (512MB RAM, 0.1 CPU) or Standard ($7/month, 1GB RAM, 1 CPU)
5. Click "Create Web Service"
6. After deployment, add environment variables:
   - Go to service → Settings → Environment
   - Add `OPENAI_API_KEY` with your key
7. Redeploy the service to apply environment variables

#### Option B: Via render.yaml (Automatic)

If `render.yaml` is present at the repository root, Render will auto-detect the configuration:

1. Go to [https://render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Render will read `render.yaml` and auto-fill the configuration
5. Review and adjust as needed
6. Add environment variables after deployment
7. Click "Create Web Service"

### 1.5 Verify Backend Deployment

1. Render will provide a URL like: `https://hdfc-faq-assistant-api.onrender.com`
2. Test health endpoint:
```bash
curl https://hdfc-faq-assistant-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "schemes_loaded": 12
}
```

3. Test chat endpoint:
```bash
curl -X POST https://hdfc-faq-assistant-api.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the expense ratio of HDFC Balanced Advantage Fund?"}'
```

### 1.6 Render Configuration Details

**render.yaml** - Render service configuration:
```yaml
services:
  - type: web
    name: hdfc-faq-assistant-api
    runtime: python
    buildCommand: cd Milestone2 && pip install -r requirements.txt
    startCommand: cd Milestone2 && uvicorn phase3_reasoning_guardrails.src.api:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: PORT
        value: 8000
    healthCheckPath: /health
```

---

## Part 2: Frontend Deployment (Vercel)

### 2.1 Update Frontend API Endpoint

Edit `phase4_user_interface/index.html` and update the API endpoint:

```javascript
// Find the API URL configuration (around line ~400+)
const API_URL = 'https://hdfc-faq-assistant-api.onrender.com';
```

Replace `hdfc-faq-assistant-api.onrender.com` with your actual Render backend URL.

### 2.2 Deploy to Vercel

#### Option A: Via Vercel CLI (Recommended)

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy:
```bash
cd Milestone2
vercel
```

4. Follow prompts:
   - Set up and deploy? → Yes
   - Which scope? → Your account
   - Link to existing project? → No
   - Project name → `hdfc-faq-assistant`
   - Directory → `./`
   - Override settings? → No

5. Deploy to production:
```bash
vercel --prod
```

#### Option B: Via Vercel Dashboard

1. Go to [https://vercel.com](https://vercel.com)
2. Click "Add New Project"
3. Import your GitHub repository
4. Configure project:
   - **Framework Preset**: Other
   - **Root Directory**: `./`
   - **Build Command**: (leave empty for static)
   - **Output Directory**: `phase4_user_interface`
5. Click "Deploy"

### 2.3 Configure Vercel Settings

**vercel.json** - Vercel configuration:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "phase4_user_interface/index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/phase4_user_interface/index.html"
    }
  ]
}
```

### 2.4 Verify Frontend Deployment

1. Vercel will provide a URL like: `https://your-project.vercel.app`
2. Open the URL in a browser
3. Test the chat interface with a question
4. Verify responses from backend

---

## Part 3: CORS Configuration

### 3.1 Update Backend CORS Settings

In `phase3_reasoning_guardrails/src/api.py`, update the CORS middleware:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-project.vercel.app"],  # Your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Replace `https://your-project.vercel.app` with your actual Vercel frontend URL.

### 3.2 For Multiple Frontend Domains

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-project.vercel.app",
        "http://localhost:3000",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Part 4: Data Management

### 4.1 ChromaDB Index Deployment

The ChromaDB index files in `data/indexed/` must be committed to the repository:

```bash
# Ensure index files are tracked
git add Milestone2/data/indexed/
git commit -m "Add ChromaDB index for deployment"
git push
```

### 4.2 Data File Deployment

Ensure chunked data is committed:

```bash
git add Milestone2/data/processed/chunked_data_phase1.4.json
git commit -m "Add chunked data for deployment"
git push
```

### 4.3 Data Updates

To update the corpus data:

1. Run the ingestion pipeline locally
2. Commit updated index and data files
3. Push to GitHub
4. Render will auto-redeploy on push
5. Vercel will auto-redeploy on push

---

## Part 5: Monitoring & Logging

### 5.1 Render Monitoring

- **Logs**: Available in Render dashboard under "Logs" tab
- **Metrics**: CPU, Memory, and Network usage in "Metrics" tab
- **Health Checks**: Automatic health checks at `/health` endpoint
- **Alerts**: Configure alerts for deployment failures and high resource usage

### 5.2 Vercel Monitoring

- **Logs**: Available in Vercel dashboard under "Logs" tab
- **Analytics**: Page views, bandwidth, and build metrics
- **Deployments**: Build logs and deployment history
- **Webhooks**: Configure webhooks for deployment events

---

## Part 6: Environment Variables

### 6.1 Render Environment Variables

Set these in Render dashboard (Service → Settings → Environment):

```bash
OPENAI_API_KEY=sk-your-actual-key-here
PYTHONUNBUFFERED=1
PORT=8000
```

### 6.2 Vercel Environment Variables

For frontend API configuration, update the `API_URL` in `index.html` directly, or use environment variables with a build step.

---

## Part 7: Troubleshooting

### 7.1 Render Issues

**Issue**: Build fails with module not found
```
Solution: Ensure all dependencies are in requirements.txt
```

**Issue**: Health check fails
```
Solution: Check /health endpoint returns valid JSON
```

**Issue**: ChromaDB not loading
```
Solution: Ensure data/indexed/ files are committed to repository
```

**Issue**: 503 Service Unavailable
```
Solution: Check orchestrator initialization logs in Render dashboard
```

**Issue**: Instance crashes due to memory
```
Solution: Upgrade to Standard instance type (1GB RAM) for ChromaDB
```

### 7.2 Vercel Issues

**Issue**: 404 on frontend
```
Solution: Ensure vercel.json routes are correct
```

**Issue**: CORS errors
```
Solution: Update backend CORS allow_origins to include Vercel URL
```

**Issue**: API calls failing
```
Solution: Verify API_URL in index.html matches Render backend URL
```

---

## Part 8: Cost Estimation

### 8.1 Render Costs

- **Free Tier**: Free (512MB RAM, 0.1 CPU, spins down after 15min inactivity)
- **Standard Plan**: $7/month (1GB RAM, 1 CPU, always on)
- **Pro Plan**: $25/month (2GB RAM, 2 CPU, always on)
- **Storage**: Included in plan (up to 10GB)

### 8.2 Vercel Costs

- **Hobby Plan**: Free (100GB bandwidth, 6 builds/month)
- **Pro Plan**: $20/month (1TB bandwidth, unlimited builds)
- **Static Hosting**: No additional cost for static files

---

## Part 9: Security Best Practices

### 9.1 Backend Security

- Never commit `.env` file to repository
- Use Render environment variables for secrets
- Update CORS to specific frontend domains only
- Implement rate limiting (add to FastAPI middleware)
- Use HTTPS only (Render provides automatic SSL)

### 9.2 Frontend Security

- Vercel provides automatic HTTPS
- Validate user inputs on backend
- Implement CSP headers if needed
- Use Vercel Analytics for monitoring

---

## Part 10: CI/CD Integration

### 10.1 Automatic Deployments

Both Render and Vercel support automatic deployments on git push:

```bash
git add .
git commit -m "Update application"
git push origin main
```

- Render will auto-redeploy on push
- Vercel will auto-redeploy on push

### 10.2 GitHub Actions Integration

You can add GitHub Actions to run tests before deployment:

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest phase3_reasoning_guardrails/tests/
```

---

## Summary

1. **Backend (Render)**: FastAPI + ChromaDB deployed with render.yaml
2. **Frontend (Vercel)**: Static HTML/JS deployed with vercel.json
3. **CORS**: Configure backend to allow frontend domain
4. **Data**: Commit ChromaDB index and chunked data to repository
5. **Environment Variables**: Set OPENAI_API_KEY in Render dashboard
6. **Auto-Deploy**: Both platforms auto-redeploy on git push
7. **Monitoring**: Use Render and Vercel dashboards for logs and metrics

---

## Quick Start Commands

```bash
# Render (via dashboard)
# 1. Go to render.com
# 2. Connect GitHub repo
# 3. Configure build and start commands
# 4. Add OPENAI_API_KEY environment variable

# Vercel
vercel login
vercel
vercel --prod
```

---

## Support

- **Render Documentation**: [https://render.com/docs](https://render.com/docs)
- **Vercel Documentation**: [https://vercel.com/docs](https://vercel.com/docs)
- **FastAPI Documentation**: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
