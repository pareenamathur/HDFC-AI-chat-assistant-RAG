# HDFC Mutual Fund Assistant — Production deployment (Railway + Vercel)

**Production stack:** FastAPI on **Railway** · Next.js on **Vercel**.  
**Streamlit is not used** in production (no Streamlit Cloud, no Streamlit dependencies in `requirements.txt`).

---

## Architecture

| Layer | Technology | Host |
|--------|------------|------|
| API | FastAPI + Uvicorn (`backend.app:app`) | Railway |
| UI | Next.js 14 (App Router) | Vercel |
| Embeddings | `all-MiniLM-L6-v2` (lazy-loaded; often warmed in background via `RAG_BACKGROUND_WARM`) | Railway |
| Vector DB | ChromaDB on disk (`data/indexed/`) | Railway filesystem |

**Memory strategy:** schemes load at API boot (~low MB). **MiniLM, Chroma client, and LLM** load only on the **first** `/query` or `/chat`. BM25, rerankers, and cross-encoders stay **off** unless you explicitly set `USE_BM25=true` / `USE_RERANKER=true` (not recommended on small plans).

**Python:** 3.11.x (see `runtime.txt`). Features like `asyncio.timeout` require 3.11+.

### `GET /health` (never fails)

Returns **`status: healthy`** and **`ready: true`** whenever this handler runs — **not** gated on embeddings, Chroma, or Groq. Use **`rag_available`** for full RAG.

| Field | Meaning |
|-------|---------|
| `ready` | Always **`true`** here — API process is serving routes. |
| `rag_available` | Chroma + `RAGOrchestrator` initialized (`true` after successful bounded init). |
| `rag_ready` | **`true` after first successful retrieval** (embedding path exercised); until then `rag_available` may already be `true`. |
| `mock_mode` | **Only** “no `GROQ_API_KEY`” — LLM uses MockLLM when RAG runs; **not** tied to Chroma. |
| `chroma_loaded` | Chroma client + collection opened during RAG init. |
| `model_loaded` | SentenceTransformer loaded and retrieval exercised (background warm or first successful `answer_query`). |
| `degraded` | **`true`** if RAG init failed/timed out **or** the **last** `POST /query` ended in **`error`**, **`timeout`**, or **`degraded`** status — until a later query returns **`success`**, **`refusal`**, or **`no_results`**. |
| `index_on_disk` | **`chroma.sqlite3`** exists at `INDEXED_DATA_PATH` — corpus shipped; **`rag_available`** still false until first **`POST /query`**. |
| `api_version` | Backend build string (matches OpenAPI app version). |
| `last_query_status` | Last completed `POST /query` status on **this** worker (`null` until the first query). |

Bounded RAG init: set **`RAG_INIT_TIMEOUT_SECONDS`** (app default **120**, max **600**) so first deploy can finish downloading **MiniLM** + opening Chroma on Railway.

### Corpus (NAV) freshness — not scheduled on Railway

The **FastAPI service does not refresh NAV on a timer.** Replies come from **`data/indexed/`** (last scrape + Chroma build you shipped).

- **`data/corpus_version.json`** — field **`last_updated`** records the last pipeline refresh you committed.
- **GitHub Actions:** `.github/workflows/corpus-health-check.yml` runs **daily** on the **default branch** (`cron: 30 4 * * *`), on **push** to `main`/`master` when `data/corpus_version.json` or this workflow changes, and on **workflow_dispatch**. It fails if `last_updated` is older than **`STALE_THRESHOLD_DAYS`** (set at the top of the workflow file, default **30**). Repo → **Settings → Actions → General**: allow **Actions** (and for forks, default workflow permissions). Then **Actions** tab → confirm runs.
- **Newer NAV:** re-run Phase **1.1–1.4** (fetch → chunk), then **`python scripts/rebuild_chroma_from_chunks.py --force`**, commit **`data/processed/`** + **`data/indexed/`**, redeploy.

**Source links:** Chroma metadata often stores only an HTML **basename**. The RAG context now includes **`Official citation URL: https://www.hdfcfund.com/`**, and **`POST /query`** responses set **`source_link`** to that URL when no `https` source is stored — so the UI/API always get a valid official link.

---

## 1. Railway — exact steps

1. Push this repo to GitHub (see §3).
2. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub** → select the repo.
3. **Root Directory:** set to **`Milestone2`** (when the repo root is above `Milestone2/`, e.g. Desktop monorepo).
4. Railway detects **`Procfile`** / **Start Command**. Ensure the start command is effectively:
   ```bash
   uvicorn backend.app:app --host 0.0.0.0 --port $PORT --workers 1
   ```
5. **Variables** (Project → Variables):

   | Variable | Example | Notes |
   |----------|---------|--------|
   | `GROQ_API_KEY` | `gsk_…` | Optional; without it the app uses **MockLLM** (still boots). |
   | `CORS_ALLOW_ORIGINS` | `https://your-app.vercel.app` | Comma-separated; use `*` only for debugging. |
   | `QUERY_TIMEOUT_SECONDS` | `90` | Max time for one `/query` request (async). |
   | `RAG_INIT_TIMEOUT_SECONDS` | `120` | Max time for first Chroma + orchestrator init (MiniLM download on cold Railway). |
   | `LLM_TIMEOUT_SECONDS` | `60` | Groq call wall time. |
   | `VECTOR_FETCH_K` | `10` | Lower = less RAM (bounds 4–24 internally). |
   | `USE_BM25` | `false` | Keep false on low-memory plans. |
   | `USE_RERANKER` | `false` | Keep false on low-memory plans. |
   | `INDEXED_DATA_PATH` | _(default `data/indexed`)_ | Override if you mount storage elsewhere. |
   | `PROCESSED_DATA_PATH` | _(default `data/processed`)_ | For `chunked_data_phase1.4.json` (scheme names). |

6. **Resources:** use **≥ 1 GB RAM**; **2 GB** if the first query still OOMs after tuning `VECTOR_FETCH_K`.

7. **Build / install:** Nixpacks should run `pip install -r requirements.txt` from **`Milestone2`**. If you use **Docker**, build from `Milestone2/` with `Dockerfile.api`.

8. After deploy, open Railway’s **public URL** — you should get JSON from `GET /`.

---

## 2. Vercel — exact steps

1. [Vercel](https://vercel.com) → **Add New** → **Project** → import the same GitHub repo.
2. **Root Directory:** **`Milestone2/frontend`**
3. **Framework:** Next.js (auto).
4. **Environment Variables** (Production — and Preview if needed):

   | Name | Value |
   |------|--------|
   | `NEXT_PUBLIC_API_URL` | `https://xxxx.up.railway.app` (your Railway URL, **no trailing slash**) |
   | `NEXT_PUBLIC_API_TIMEOUT_MS` | `90000` (optional) |

5. **Deploy.** After changing `NEXT_PUBLIC_*`, **Redeploy** so the client bundle picks up the new API URL.

---

## 3. GitHub push steps

From your machine (repo root that contains `Milestone2/`):

```bash
git add Milestone2
git status   # confirm only intended paths
git commit -m "Production: Railway API + Vercel frontend"
git push origin main
```

---

## 4. Environment variables (summary)

**Railway (server):** `GROQ_API_KEY`, `CORS_ALLOW_ORIGINS`, optional timeouts and `VECTOR_FETCH_K`, paths as above.  
**Vercel (build + browser):** `NEXT_PUBLIC_API_URL`, optional `NEXT_PUBLIC_API_TIMEOUT_MS`.

Secrets stay on Railway; **never** commit real API keys.

---

## 5. Railway RAM optimization (why it works)

- **No Streamlit** → smaller install surface and no second web stack.
- **CPU-only PyTorch** (`torch==2.2.2+cpu` from PyTorch CPU index) — **no CUDA / no `nvidia-*`** in `requirements.txt`.
- **Lazy RAG:** embedding model + Chroma-heavy paths run **after** first query, not at import.
- **Singleton:** one `RAGOrchestrator` instance per process.
- **BM25 off:** avoids loading the full document corpus into RAM for sparse indexing.
- **Reranker off:** avoids loading `CrossEncoder`.
- **Bounded Chroma query:** `vector_fetch_k` capped (default **10** via env).
- **Thread caps:** `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `TOKENIZERS_PARALLELISM` via env in code path.
- **`gc.collect()`** after heavy query path.
- **Protobuf:** `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` + compatible `protobuf` range reduces “Descriptors cannot be created directly” class of failures.

Target: **startup** roughly **under ~200 MB RSS** on Linux after schemes load (depends on host libraries); **peak** kept **under ~500 MB** with defaults on a 1–2 GB plan.

---

## 6. Crash prevention

| Risk | Mitigation |
|------|------------|
| OOM on first query | Raise Railway RAM; lower `VECTOR_FETCH_K`; keep BM25/reranker off. |
| Protobuf / gRPC mismatch | Pinned ranges + pure-Python protobuf runtime flag in app bootstrap. |
| Missing index | `/health` stays **healthy** with **`ready: true`** after boot; **`degraded: true`** once a query proves Chroma cannot load; **`/query`** returns a **safe placeholder** (`status: degraded`), not HTTP 503. |
| Missing Groq key | **`mock_mode: true`** in `/health`; **MockLLM** when RAG works; no startup failure. |
| Hanging LLM | `LLM_TIMEOUT_SECONDS` + `QUERY_TIMEOUT_SECONDS`. |
| CORS blocked | Set `CORS_ALLOW_ORIGINS` to your Vercel domain. |

---

## 7. API troubleshooting

| Symptom | Check |
|---------|--------|
| 503 on `/query` | Rare; most failures return **200** with `status: error` or `degraded`. If you see 503, check middleware or proxy. |
| Slow first answer | Expected “cold” load (MiniLM + Chroma). |
| Timeout | Increase `QUERY_TIMEOUT_SECONDS` slightly or shorten prompts. |
| Wrong CORS | Railway `CORS_ALLOW_ORIGINS` includes exact Vercel origin (scheme + host). |

---

## 8. Frontend troubleshooting

| Symptom | Check |
|---------|--------|
| “Cannot reach API” | `NEXT_PUBLIC_API_URL` wrong; Railway asleep — retry; HTTPS URL correct. |
| Old API URL after change | Redeploy Vercel after env change. |
| Status pill “offline” | Railway URL down or `/health` returning ≥500. |

---

## 9. Railway logs debugging

1. Railway → Service → **Deployments** → latest → **View logs**.
2. Confirm: `Startup complete — schemes=N` without traceback.
3. First user query: look for `Lazy-loading RAG orchestrator` and memory lines.
4. If crash: search logs for `Traceback`, `Memory`, `chromadb`, `CUDA` (should **not** appear).

---

## 10. Deployment order checklist

1. [ ] Push backend + frontend changes to GitHub (`main`).
2. [ ] Deploy **Railway** (root `Milestone2`).
3. [ ] `curl https://<railway>/health` → `status: healthy`, **`ready: true`** (even with zero env vars). Inspect `mock_mode`, `chroma_loaded`, `degraded`.
4. [ ] `curl -X POST https://<railway>/query -H "Content-Type: application/json" -d '{"query":"What is NAV?","chat_history":[]}'` → JSON answer or placeholder (`status: degraded`) if index is missing.
5. [ ] Set Vercel `NEXT_PUBLIC_API_URL` to Railway URL.
6. [ ] Deploy **Vercel** (`Milestone2/frontend`).
7. [ ] Open Vercel URL → status pill reflects **degraded** / **demo LLM** / **RAG ready** from `/health`.

---

## Local verification

```bash
cd Milestone2
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

```bash
cd Milestone2/frontend
npm install
npm run dev
# set frontend/.env.local: NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## Docker (optional)

From `Milestone2/`:

```bash
docker build -f Dockerfile.api -t hdfc-mf-api .
docker run --rm -p 8000:8000 -e GROQ_API_KEY=... hdfc-mf-api
```

---

*Single production guide for Railway + Vercel; Streamlit removed from this path.*
