# HDFC Mutual Fund Assistant - Deployment Plan
# Backend on Render + Frontend on Vercel

## Overview
- **Backend:** FastAPI application deployed on Render
- **Frontend:** React/Next.js application deployed on Vercel
- **Database:** ChromaDB with persistent storage
- **API Integration:** CORS-enabled REST API communication

## Backend Deployment on Render

### 1. Repository Structure
```
Milestone2/
├── backend/
│   ├── app.py                 # Main FastAPI application
│   ├── requirements.txt         # Production dependencies
│   ├── .env.example          # Environment variables template
│   └── Dockerfile            # Container configuration
├── data/                    # Data directory (persistent storage)
│   ├── indexed/              # ChromaDB storage
│   └── processed/           # Processed data files
├── phase2_retrieval_layer/    # RAG retrieval components
├── phase3_reasoning_guardrails/ # RAG orchestrator
└── runtime.txt              # Python 3.11 specification
```

### 2. Render Configuration

#### Web Service Setup
- **Name:** hdfc-mutual-fund-backend
- **Branch:** main
- **Root Directory:** backend
- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

#### Environment Variables
```bash
# Core Configuration
PORT=8000
HOST=0.0.0.0

# Memory Optimization
USE_BM25=false
USE_RERANKER=false

# API Keys (Required)
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Data Paths
DATA_PATH=/opt/render/project/src/data
INDEXED_DATA_PATH=/opt/render/project/src/data/indexed
PROCESSED_DATA_PATH=/opt/render/project/src/data/processed

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 3. Persistent Storage Setup

#### Render Disk Storage
- **Type:** Render Disk
- **Size:** 10GB (minimum for ChromaDB + data)
- **Mount Path:** `/opt/render/project/src/data`
- **Purpose:** Persistent ChromaDB storage and processed data

#### Data Directory Structure
```
/opt/render/project/src/data/
├── indexed/
│   └── chroma.sqlite3    # ChromaDB database
└── processed/
    └── chunked_data_phase1.4.json  # Schemes data
```

### 4. Build and Deployment Process

#### Pre-deployment Steps
1. **Verify Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   python -c "import app; print('Dependencies OK')"
   ```

2. **Data Preparation**
   ```bash
   # Ensure data directory exists
   mkdir -p /opt/render/project/src/data/indexed
   mkdir -p /opt/render/project/src/data/processed
   
   # Copy or generate required data files
   # ChromaDB will be created on first run
   ```

3. **Environment Testing**
   ```bash
   # Test with production-like environment
   export PORT=8000
   export DATA_PATH=/opt/render/project/src/data
   python app.py
   ```

#### Render Deployment Steps
1. **Connect Repository**
   - GitHub: `pareenamathur/milestone2_hdfc`
   - Branch: `main`

2. **Configure Web Service**
   - Name: `hdfc-mutual-fund-backend`
   - Region: `Oregon (us-west-2)` or nearest
   - Instance Type: `Free` (upgrade as needed)

3. **Set Environment Variables**
   - Add all required environment variables
   - Set sensitive values (API keys) securely

4. **Configure Persistent Storage**
   - Add Render Disk (10GB minimum)
   - Mount to `/opt/render/project/src/data`

5. **Deploy**
   - Build and deploy from main branch
   - Monitor build logs for errors

## Frontend Deployment on Vercel

### 1. Repository Structure
```
Milestone2/
├── frontend/
│   ├── package.json          # Dependencies and scripts
│   ├── next.config.js        # Next.js configuration
│   ├── vercel.json          # Vercel deployment settings
│   └── src/                # React components
│       ├── components/
│       ├── pages/
│       └── utils/
└── public/                 # Static assets
```

### 2. Vercel Configuration

#### Project Settings
- **Name:** hdfc-mutual-fund-frontend
- **Framework Preset:** Next.js
- **Root Directory:** frontend
- **Build Command:** `npm run build`
- **Output Directory:** `.next`
- **Node.js Version:** 18.x

#### Environment Variables
```bash
# Backend API URL
NEXT_PUBLIC_API_URL=https://hdfc-mutual-fund-backend.onrender.com

# API Keys (if needed for frontend)
NEXT_PUBLIC_GROQ_API_KEY=your_groq_api_key_here
NEXT_PUBLIC_OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Build and Deployment Process

#### Pre-deployment Steps
1. **Install Dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Environment Configuration**
   ```bash
   # Test with production URL
   export NEXT_PUBLIC_API_URL=https://hdfc-mutual-fund-backend.onrender.com
   npm run build
   ```

3. **Build Verification**
   ```bash
   npm run build
   npm run start  # Test production build
   ```

#### Vercel Deployment Steps
1. **Connect Repository**
   - GitHub: `pareenamathur/milestone2_hdfc`
   - Branch: `main`

2. **Configure Project**
   - Framework: Next.js
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

3. **Set Environment Variables**
   - Add backend API URL
   - Add any required API keys

4. **Deploy**
   - Automatic deployment on git push
   - Monitor build logs

## Integration and Testing

### 1. CORS Configuration
```python
# Backend CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hdfc-mutual-fund-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. API Endpoints
- **Health Check:** `GET /health`
- **Schemes List:** `GET /schemes`
- **Query:** `POST /query`
- **Chat:** `POST /chat`

### 3. Frontend API Integration
```javascript
// API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Example API call
const response = await fetch(`${API_BASE_URL}/query`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ query: userQuery }),
});
```

## Deployment Checklist

### Backend (Render)
- [ ] Repository connected to Render
- [ ] Environment variables configured
- [ ] Persistent storage (Render Disk) added
- [ ] Build command tested
- [ ] Start command configured
- [ ] Health endpoint accessible
- [ ] API endpoints tested
- [ ] Data persistence verified

### Frontend (Vercel)
- [ ] Repository connected to Vercel
- [ ] Environment variables configured
- [ ] Build command tested
- [ ] Production build successful
- [ ] API integration working
- [ ] CORS properly configured
- [ ] All pages accessible

### Post-Deployment Testing
- [ ] Backend health check: `GET /health`
- [ ] API functionality test: `POST /query`
- [ ] Frontend-backend integration
- [ ] Error handling verification
- [ ] Performance testing
- [ ] Mobile responsiveness
- [ ] Cross-browser compatibility

## Troubleshooting

### Common Issues and Solutions

#### Backend Issues
1. **Port Binding Error**
   - Solution: Use `$PORT` environment variable
   - Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

2. **Data Persistence Issues**
   - Solution: Use Render Disk for persistent storage
   - Mount path: `/opt/render/project/src/data`

3. **Memory Issues**
   - Solution: Set `USE_BM25=false` and `USE_RERANKER=false`
   - Monitor memory usage in Render dashboard

4. **API Key Issues**
   - Solution: Set environment variables in Render dashboard
   - Never hardcode API keys in code

#### Frontend Issues
1. **CORS Errors**
   - Solution: Update backend CORS origins
   - Add frontend domain to allowed origins

2. **API Connection Issues**
   - Solution: Use correct environment variable
   - `NEXT_PUBLIC_API_URL` for production

3. **Build Failures**
   - Solution: Check Node.js version compatibility
   - Verify all dependencies installed

## Monitoring and Maintenance

### Backend Monitoring
- **Render Dashboard:** Monitor uptime, memory, and performance
- **Logs:** Check application logs regularly
- **Health Checks:** Implement `/health` endpoint monitoring

### Frontend Monitoring
- **Vercel Analytics:** Monitor page views and performance
- **Build Logs:** Check deployment logs for errors
- **Error Tracking:** Implement frontend error reporting

## Rollback Plan

### Backend Rollback
1. **Git Revert:** `git revert <commit-hash>`
2. **Redeploy:** Push revert commit to trigger new deployment
3. **Verify:** Test all endpoints after rollback

### Frontend Rollback
1. **Vercel Rollback:** Use Vercel dashboard to revert
2. **Previous Deployments:** Select and deploy previous successful version
3. **Verify:** Test all functionality after rollback

## Security Considerations

### Backend Security
- **API Keys:** Never commit to repository
- **Environment Variables:** Use Render's secure storage
- **CORS:** Restrict to frontend domain only
- **Rate Limiting:** Implement for production

### Frontend Security
- **Environment Variables:** Use `NEXT_PUBLIC_` prefix for client-side
- **API Communication:** Use HTTPS endpoints
- **Input Validation:** Sanitize all user inputs

## Cost Optimization

### Render Costs
- **Free Tier:** 750 hours/month, 512MB RAM
- **Upgrade Plans:** Based on traffic and memory needs
- **Storage:** Monitor disk usage and optimize

### Vercel Costs
- **Free Tier:** 100GB bandwidth, Pro features
- **Upgrade Plans:** Based on traffic and build needs
- **Optimization:** Code splitting and lazy loading

## Next Steps

1. **Deploy Backend to Render**
   - Set up persistent storage
   - Configure environment variables
   - Test all endpoints

2. **Deploy Frontend to Vercel**
   - Configure API integration
   - Test production build
   - Verify CORS setup

3. **End-to-End Testing**
   - Test complete user flows
   - Verify error handling
   - Performance optimization

4. **Monitoring Setup**
   - Configure alerts and monitoring
   - Set up logging and analytics
   - Document maintenance procedures
