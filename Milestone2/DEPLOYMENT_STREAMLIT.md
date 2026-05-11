# Deployment Guide: Mutual Fund FAQ Assistant (Streamlit)

This document provides step-by-step instructions for deploying the Mutual Fund FAQ Assistant using **Streamlit** as a single unified application (frontend + backend combined).

---

## Architecture Overview

```
┌─────────────────────────────────┐
│     Streamlit Cloud (App)       │
│  ┌───────────────────────────┐  │
│  │   Streamlit UI + RAG      │  │
│  │   Engine (Python)         │  │
│  └───────────────────────────┘  │
│            │                     │
│            ▼                     │
│  ┌───────────────────────────┐  │
│  │   ChromaDB Vector Store   │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

**Key Difference**: Streamlit combines the frontend UI and backend RAG engine into a single Python application, eliminating the need for separate deployments.

---

## Prerequisites

1. **Streamlit Account**: [https://streamlit.io](https://streamlit.io)
2. **GitHub Repository**: Project must be pushed to GitHub
3. **OpenAI API Key**: For LLM functionality (set as environment variable)
4. **Data Files**: ChromaDB index and chunked data must be committed to repository

---

## Part 1: Prepare Repository

Ensure your repository structure includes:
```
Milestone2/
├── streamlit_app.py              # Main Streamlit application (production-ready)
├── requirements_streamlit.txt    # Streamlit-specific dependencies
├── phase3_reasoning_guardrails/
│   └── src/
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
└── .streamlit/
    └── config.toml              # Streamlit configuration
```

**streamlit_app.py Features:**
- Title: "Mutual Fund FAQ Assistant"
- Disclaimer: "Facts-only. No investment advice."
- Dark theme chat UI
- Chat input with session state history
- Displays answer, source link, and last updated date
- Loading spinner during query processing
- Graceful error handling
- Uses existing RAG orchestrator without backend logic changes

---

## Part 2: Create Streamlit Configuration

Create `.streamlit/config.toml` file:

```toml
[theme]
base = "dark"
primaryColor = "#00D09C"
backgroundColor = "#0D0D0D"
secondaryBackgroundColor = "#1A1A1A"
textColor = "#FFFFFF"
font = "sans serif"

[client]
showErrorDetails = true
maxUploadSize = 200

[logger]
level = "info"
```

---

## Part 3: Deploy to Streamlit Cloud

### 3.1 Via Streamlit Cloud (Recommended)

1. Go to [https://share.streamlit.io](https://share.streamlit.io)
2. Click "New app"
3. Connect your GitHub repository
4. Configure the app:
   - **Repository**: Select your repository
   - **Branch**: `main`
   - **Main file path**: `Milestone2/streamlit_app.py`
   - **Python version**: `3.11` or later
5. Click "Deploy"

### 3.2 Add Environment Variables

After deployment:

1. Go to your app on Streamlit Cloud
2. Click "Settings" → "Secrets"
3. Add the following secret:
   - **Name**: `OPENAI_API_KEY`
   - **Value**: Your actual OpenAI API key
4. Click "Save"
5. Click "Rerun" to restart the app with the new environment variable

### 3.3 Verify Deployment

1. Streamlit Cloud will provide a URL like: `https://your-app.streamlit.app`
2. Open the URL in a browser
3. Verify the app loads correctly
4. Check the sidebar for system status
5. Test with a question about HDFC mutual funds

---

## Part 4: Local Development

### 4.1 Install Dependencies

```bash
cd Milestone2
pip install -r requirements_streamlit.txt
```

### 4.2 Run Locally

```bash
# Set environment variable
export OPENAI_API_KEY=your_key_here

# Run Streamlit
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`

---

## Part 5: Data Management

### 5.1 ChromaDB Index Deployment

The ChromaDB index files in `data/indexed/` must be committed to the repository:

```bash
# Ensure index files are tracked
git add Milestone2/data/indexed/
git commit -m "Add ChromaDB index for Streamlit deployment"
git push
```

### 5.2 Data File Deployment

Ensure chunked data is committed:

```bash
git add Milestone2/data/processed/chunked_data_phase1.4.json
git commit -m "Add chunked data for Streamlit deployment"
git push
```

### 5.3 Data Updates

To update the corpus data:

1. Run the ingestion pipeline locally
2. Commit updated index and data files
3. Push to GitHub
4. Streamlit Cloud will auto-redeploy on push

---

## Part 6: Monitoring & Logging

### 6.1 Streamlit Cloud Monitoring

- **Logs**: Available in Streamlit Cloud dashboard under "Logs" tab
- **Metrics**: View app performance and usage statistics
- **Error Tracking**: Automatic error logging in the dashboard
- **Deployment History**: View past deployments and rollbacks

### 6.2 Local Logging

The app uses Python's logging module. Logs are visible in:
- Streamlit Cloud dashboard
- Local terminal when running locally

---

## Part 7: Environment Variables

### 7.1 Required Environment Variables

Set in Streamlit Cloud (Settings → Secrets):

```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

### 7.2 Optional Environment Variables

```bash
PYTHONUNBUFFERED=1
```

---

## Part 8: Troubleshooting

### 8.1 Common Issues

**Issue**: App fails to start with module not found
```
Solution: Ensure all dependencies are in requirements_streamlit.txt
```

**Issue**: ChromaDB not loading
```
Solution: Ensure data/indexed/ files are committed to repository
```

**Issue**: OpenAI API errors
```
Solution: Verify OPENAI_API_KEY is set in Streamlit Cloud secrets
```

**Issue**: App is slow to load
```
Solution: Streamlit Cloud free tier has resource limits. Consider upgrading for better performance.
```

**Issue**: Data file not found
```
Solution: Ensure chunked_data_phase1.4.json exists in data/processed/ directory
```

---

## Part 9: Cost Estimation

### 9.1 Streamlit Cloud Costs

- **Free Tier**: Free
  - 30 days of app inactivity (app sleeps)
  - Limited resources
  - Community support
- **Pro Plan**: $20/month
  - No app sleep timeout
  - Priority support
  - Additional resources

### 9.2 Storage Costs

- ChromaDB index and data files are stored in your GitHub repository
- No additional storage costs on Streamlit Cloud
- GitHub repository size limits apply (1GB for free accounts)

---

## Part 10: Security Best Practices

### 10.1 Security Considerations

- Never commit `.env` file to repository
- Use Streamlit Cloud secrets for API keys
- The app is public by default - consider authentication for production
- Streamlit Cloud provides automatic HTTPS
- Validate user inputs in the RAG orchestrator

### 10.2 Authentication (Optional)

For production deployments, consider adding authentication:

```python
import streamlit as st

def check_password():
    """Returns True if the user entered the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        return False
    else:
        return True

if check_password():
    # Show main app
    main_app()
```

---

## Part 11: CI/CD Integration

### 11.1 Automatic Deployments

Streamlit Cloud supports automatic deployments on git push:

```bash
git add .
git commit -m "Update Streamlit app"
git push origin main
```

Streamlit Cloud will auto-redeploy on push.

### 11.2 GitHub Actions Integration

You can add GitHub Actions to run tests before deployment:

```yaml
# .github/workflows/streamlit-deploy.yml
name: Streamlit CI
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
          cd Milestone2
          pip install -r requirements_streamlit.txt
      - name: Run tests
        run: |
          cd Milestone2
          pytest phase3_reasoning_guardrails/tests/
```

---

## Summary

1. **Single Deployment**: Streamlit combines frontend and backend in one app
2. **Simple Setup**: Just push streamlit_app.py and requirements_streamlit.txt
3. **Environment Variables**: Set OPENAI_API_KEY in Streamlit Cloud secrets
4. **Data**: Commit ChromaDB index and chunked data to repository
5. **Auto-Deploy**: Streamlit Cloud auto-redeploys on git push
6. **Monitoring**: Use Streamlit Cloud dashboard for logs and metrics
7. **Free Tier**: Available with 30-day sleep timeout

---

## Quick Start Commands

```bash
# Local development
cd Milestone2
pip install -r requirements_streamlit.txt
export OPENAI_API_KEY=your_key
streamlit run streamlit_app.py

# Deploy to Streamlit Cloud
# 1. Go to share.streamlit.io
# 2. Connect GitHub repo
# 3. Set main file to Milestone2/streamlit_app.py
# 4. Add OPENAI_API_KEY in secrets
# 5. Deploy
```

---

## Advantages of Streamlit Deployment

1. **Simpler Architecture**: No need for separate frontend and backend
2. **Easier Debugging**: Everything in one Python file
3. **Faster Development**: No need to manage API endpoints
4. **Built-in UI**: Streamlit provides beautiful UI components
5. **Auto-Scaling**: Streamlit Cloud handles scaling automatically
6. **Free Tier**: Available for small projects

---

## Support

- **Streamlit Documentation**: [https://docs.streamlit.io](https://docs.streamlit.io)
- **Streamlit Cloud**: [https://streamlit.io/cloud](https://streamlit.io/cloud)
- **FastAPI Documentation**: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
