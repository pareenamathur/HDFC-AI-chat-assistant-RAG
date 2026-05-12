# Deployment Plan: Backend on Streamlit, Frontend on Vercel

## Architecture Overview
```
┌─────────────────┐    HTTP API    ┌─────────────────┐
│   Vercel       │◄──────────────►│  Streamlit      │
│  (Frontend)    │                │   (Backend)     │
│   React/Next.js │                │   FastAPI       │
└─────────────────┘                └─────────────────┘
```

## Backend Deployment (Streamlit Cloud)

### 1. Backend Structure
- **Location**: `Milestone2/backend/`
- **Framework**: FastAPI (not Streamlit UI)
- **Purpose**: RAG API endpoints for mutual fund queries

### 2. Key Files
```
backend/
├── app.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── .env.example       # Environment variables template
└── Dockerfile         # Container configuration
```

### 3. API Endpoints
- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /schemes` - List available mutual funds
- `POST /query` - Ask questions about funds
- `POST /chat` - Chat with history support

### 4. Streamlit Cloud Deployment Steps
1. Create new Streamlit Cloud app
2. Point to `backend/app.py` as main file
3. Set environment variables in Secrets:
   - `GROQ_API_KEY` - Groq API key
   - `OPENAI_API_KEY` - OpenAI API key
   - `USE_BM25=false` - Memory optimization
   - `USE_RERANKER=false` - Memory optimization
4. Deploy with automatic GitHub sync

## Frontend Deployment (Vercel)

### 1. Frontend Structure
- **Location**: `Milestone2/frontend/`
- **Framework**: Next.js 14 with React 18
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

### 2. Key Files
```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx      # Main chat interface
│   │   ├── layout.tsx     # App layout
│   │   └── globals.css    # Global styles
│   └── ...
├── package.json          # Dependencies
├── next.config.js        # Next.js config
├── tailwind.config.js    # Tailwind config
└── vercel.json          # Vercel deployment config
```

### 3. Vercel Deployment Steps
1. Connect Vercel to GitHub repository
2. Set root directory to `frontend/`
3. Set environment variables:
   - `NEXT_PUBLIC_API_URL` - Backend URL (Streamlit Cloud URL)
4. Automatic deployment on push to main branch

## Integration Details

### API Communication
- Frontend calls backend via HTTP API
- CORS configured for cross-origin requests
- Error handling for network issues
- Loading states and user feedback

### Data Flow
1. User types query in frontend
2. Frontend sends POST to `/query` endpoint
3. Backend processes with RAG system
4. Backend returns structured response
5. Frontend displays answer with source info

## Environment Variables

### Backend (.env)
```bash
PORT=8501
USE_BM25=false
USE_RERANKER=false
GROQ_API_KEY=your_key
OPENAI_API_KEY=your_key
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_API_URL=https://your-app.streamlit.app
```

## Benefits of This Architecture

1. **Separation of Concerns**
   - Backend: RAG processing, data management
   - Frontend: UI/UX, user interaction

2. **Scalability**
   - Backend can be scaled independently
   - Frontend can be cached effectively on Vercel

3. **Resource Optimization**
   - Memory-intensive RAG on dedicated backend
   - Lightweight frontend for better performance

4. **Development Flexibility**
   - Can update frontend without touching backend
   - Can optimize backend without affecting UI

5. **Cost Efficiency**
   - Streamlit Cloud for backend (resource limits managed)
   - Vercel for frontend (generous free tier)

## Deployment Commands

### Backend (Streamlit Cloud)
```bash
# Streamlit Cloud handles deployment automatically
# Just push to GitHub with backend changes
git add backend/
git commit -m "Update backend"
git push origin main
```

### Frontend (Vercel)
```bash
# Vercel handles deployment automatically
# Just push to GitHub with frontend changes
git add frontend/
git commit -m "Update frontend"
git push origin main
```

## Testing

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8501

# Frontend
cd frontend
npm install
npm run dev
```

### Production Testing
1. Deploy both services
2. Test API endpoints directly
3. Test frontend UI functionality
4. Verify CORS and error handling

## Monitoring

### Backend Health
- `/health` endpoint provides status
- Monitor resource usage on Streamlit Cloud
- Check API response times

### Frontend Performance
- Vercel Analytics
- Core Web Vitals monitoring
- Error tracking through Vercel logs

## Security Considerations

1. **API Keys**: Store in environment variables, not code
2. **CORS**: Restrict to Vercel domain in production
3. **Input Validation**: Backend validates all inputs
4. **Rate Limiting**: Consider implementing for production

## Rollback Plan

### Backend Issues
- Revert to previous commit on GitHub
- Streamlit Cloud automatically updates

### Frontend Issues
- Vercel supports instant rollbacks
- Can deploy previous commit manually

## Next Steps

1. Fix TypeScript/ESLint errors in frontend
2. Test local integration
3. Deploy backend to Streamlit Cloud
4. Deploy frontend to Vercel
5. Configure production environment variables
6. End-to-end testing
7. Monitor and optimize
