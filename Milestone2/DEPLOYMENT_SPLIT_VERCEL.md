# Split deployment: Streamlit (UI) + FastAPI (API) + Vercel (Next.js UI)

This is a **foolproof, ordered** plan to stop “deploy never finishes” / crash loops. Read **Section 0** first: it explains what each part does and which service must run where.

---

## 0. Architecture (read this — prevents wrong hosting)

| Component | What it is | Where it can run | Serves to browser |
|-----------|------------|------------------|-------------------|
| **`Milestone2/frontend/`** | Next.js 14 app; calls `GET /health`, `POST /query` | **Vercel** (or any Node host) | Public marketing / chat UI |
| **`Milestone2/backend/app.py`** | **FastAPI** — REST API for the Next.js app | **Long-running Python host** (Railway, Render, Fly.io, Google Cloud Run, etc.) | JSON only (not a web page) |
| **`Milestone2/streamlit_app.py`** | **Streamlit** — all-in-one Python UI + RAG | **Streamlit Cloud** (or same host as API in dev) | Streamlit web app |

**Critical fact:** the Vercel frontend does **not** talk to Streamlit. It only talks to **FastAPI** via `NEXT_PUBLIC_API_URL`. If you deploy only Streamlit Cloud and Vercel, the chat UI will show “backend not available” until a **FastAPI** URL is live and CORS is correct.

**“App crashes / deploy does not complete”** usually means one of these:

1. **Wrong process type** — e.g. Vercel trying to run Python+torch+Chroma (Vercel is not suitable for the RAG API).
2. **Out of memory (OOM)** on the API host during first query (embeddings + Chroma + torch).
3. **Missing `data/indexed/`** in the container or wrong `WORKING_DIR` / paths.
4. **Build order** — frontend built before the API URL exists, or `NEXT_PUBLIC_*` not set at build time on Vercel.
5. **Streamlit Cloud 404** — wrong Main file; see `DEPLOYMENT_STREAMLIT_FINAL.md`.

Use the **checklist order** in Section 6 on every new environment.

---

## 1. What to deploy (three optional surfaces)

You can run **all three** or **only what you need**:

- **A — Public website (Next.js):** Vercel → `Milestone2/frontend/`
- **B — API for that website (FastAPI):** any container/VM with **≥ 1 GB RAM** (2 GB safer for first query)
- **C — Streamlit-only demo (no Next.js):** Streamlit Cloud → `streamlit_app.py` (root or `Milestone2/`)

**Minimum for the Vercel app to work:** **A + B** only. **C** is optional.

---

## 2. Phase 1 — Deploy FastAPI (do this first)

### 2.1 One repo layout (this project)

- App code for the API lives under **`Milestone2/`** (contains `backend/`, `data/`, `phase2_*/`, `phase3_*/`, `requirements.txt`).
- Uvicorn target: **`backend.app:app`**
- Working directory for Python: **`Milestone2/`** (so `data/indexed` relative paths resolve like local).

### 2.2 Dependencies (avoid “ModuleNotFoundError: fastapi”)

The main `requirements.txt` is tuned for **Streamlit Cloud** and does **not** include FastAPI. For the API service use:

```bash
cd Milestone2
pip install -r requirements-api.txt
```

`requirements-api.txt` extends `requirements.txt` and adds `fastapi`, `uvicorn`, `python-multipart`.

### 2.3 Docker (recommended for consistent deploys)

From the directory that will become **image root = contents of `Milestone2/`** (so `backend/`, `data/`, `requirements-api.txt` are at the top level of the build context):

```bash
cd Milestone2
docker build -f Dockerfile.api -t hdfc-mf-api .
docker run --rm -p 8000:8000 -e GROQ_API_KEY=sk-... hdfc-mf-api
```

Verify:

```bash
curl -s https://YOUR_API_HOST/health
curl -s -X POST https://YOUR_API_HOST/query -H "Content-Type: application/json" \
  -d '{"query":"test","chat_history":[]}'
```

### 2.4 Managed platforms (Railway / Render / Fly.io pattern)

1. Create a **Web Service** from the same repo.
2. **Root directory:** `Milestone2` (if the repo root is above `Milestone2/`, set this in the UI).
3. **Start command:**  
   `uvicorn backend.app:app --host 0.0.0.0 --port $PORT --workers 1`  
   (Railway/Render inject `$PORT`; Fly/GCP may differ.)
4. **Build:** Nixpacks or Dockerfile — if Dockerfile, use **`Dockerfile.api`** with context **`Milestone2/`**.
5. **RAM:** start at **1024 MB**; if the deploy kills the process on first question, raise to **2048 MB**.
6. **Environment variables (API host):**

   | Variable | Required | Purpose |
   |----------|----------|---------|
   | `GROQ_API_KEY` | For real LLM answers | Groq |
   | `PORT` | Usually auto | Injected by host |
   | `INDEXED_DATA_PATH` / `PROCESSED_DATA_PATH` / `DATA_PATH` | If non-default | Point to indexed corpus (see `backend/app.py`) |
   | `USE_BM25` | `false` on small plans | Less RAM |
   | `USE_RERANKER` | `false` | Less RAM |
   | `CORS_ALLOW_ORIGINS` | Optional | If you add env-based CORS in app (currently `allow_origins=["*"]` is fine to start) |

7. **Disk / image:** ensure **`data/indexed/`** (Chroma) is **inside the deployed artifact** or mounted from persistent volume. If `.gitignore` excludes your index, **upload artifacts in CI** or **attach volume** — empty index → confusing runtime failures.

### 2.5 Why not host FastAPI on Vercel?

Vercel serverless is **not** a fit for long-lived torch/sentence-transformers/Chroma workloads (bundle limits, cold starts, timeouts). Put **FastAPI on a container/VM**; put **only Next.js on Vercel**.

---

## 3. Phase 2 — Deploy Next.js on Vercel

### 3.1 Project settings

1. Import the GitHub repo into Vercel.
2. **Root Directory:** `Milestone2/frontend`  
   (If your repo root is `Desktop/` with `Milestone2/` inside, this is mandatory.)
3. **Framework Preset:** Next.js (auto).
4. **Build Command:** `npm run build` (default; `vercel.json` matches this).
5. **Output:** default for App Router.

### 3.2 Environment variables (build + runtime)

Set in **Vercel → Project → Settings → Environment Variables** for **Production** (and Preview if you use preview URLs):

| Name | Example | Notes |
|------|---------|--------|
| `NEXT_PUBLIC_API_URL` | `https://your-service.up.railway.app` | **No trailing slash.** Must be live **before** you rely on the UI. |

**Important:** `NEXT_PUBLIC_*` is inlined at **build** time. After changing it, trigger **Redeploy** so the new URL is baked in.

### 3.3 Local parity

Copy `frontend/.env.example` → `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Run API: from `Milestone2/backend` with deps installed, use `ALLOW_LOCAL_FASTAPI=1` pattern from `DEPLOYMENT_STREAMLIT_FINAL.md` or run uvicorn as in Section 2.

### 3.4 CORS

Backend currently allows `allow_origins=["*"]`. For production hardening, restrict to your Vercel domain in `backend/app.py` once stable.

---

## 4. Phase 3 — Streamlit Cloud (optional second UI)

Use **`DEPLOYMENT_STREAMLIT_FINAL.md`** as the source of truth.

- **Main file:** `streamlit_app.py` (repo root) **or** `Milestone2/streamlit_app.py`
- **Packages:** `Milestone2/requirements.txt`
- **Secrets:** `GROQ_API_KEY`, etc.

This deployment is **independent** of Vercel: different URL, different process. Good for demos and operator testing; **not** a substitute for FastAPI if you use the Next.js frontend.

---

## 5. Failure modes → fixes (quick reference)

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| Vercel build fails | Wrong root directory | Set root to `Milestone2/frontend` |
| Browser: failed to fetch / CORS | API down or wrong URL | Fix `NEXT_PUBLIC_API_URL`; redeploy frontend |
| API exits during install | OOM or missing wheels | Use Linux image; increase RAM; see `requirements.txt` pins |
| First query kills container | OOM | Increase RAM; set `USE_BM25=false`, lower `STREAMLIT_VECTOR_FETCH_K` where applicable |
| `/health` OK but `/query` 500 | Missing index / bad paths | Verify `data/indexed/` in deployment |
| Streamlit Cloud 404 health | Wrong entrypoint | Not `backend/app.py`; use `streamlit_app.py` |

---

## 6. Go-live checklist (do in order)

1. [ ] Index committed or deployed to API host (`data/indexed/`).
2. [ ] `pip install -r requirements-api.txt` succeeds in CI or Docker build logs.
3. [ ] API deployed; `GET /health` returns 200 from **public URL**.
4. [ ] `POST /query` works with `curl` from your laptop.
5. [ ] Vercel env `NEXT_PUBLIC_API_URL` set to that URL (no trailing slash).
6. [ ] Vercel **Redeploy** production after env change.
7. [ ] Open Vercel URL; send a chat message; confirm no console network errors.
8. [ ] (Optional) Streamlit Cloud redeployed with correct Main file and Secrets.

---

## 7. Files added for this split layout

| File | Purpose |
|------|---------|
| `requirements-api.txt` | Streamlit stack **plus** FastAPI/uvicorn for API servers |
| `Dockerfile.api` | Reproducible FastAPI image; build context = `Milestone2/` |
| `frontend/.env.example` | Documents `NEXT_PUBLIC_API_URL` |
| `frontend/vercel.json` | Pins Next.js framework / build for Vercel |

---

## 8. Summary

- **Vercel** = **Next.js frontend** only.  
- **Python RAG API** for that frontend = **FastAPI** on a **proper Python host** (Docker + Railway/Fly/Render/Cloud Run).  
- **Streamlit Cloud** = **optional** second UI; it does **not** replace the API for `NEXT_PUBLIC_API_URL`.

Following **Phase 1 (API) → Phase 2 (Vercel) → optional Phase 3 (Streamlit)** avoids the common failure of a green Vercel build with a broken or missing backend.
