# HDFC Mutual Fund Assistant

An **AI-powered informational assistant** for HDFC Mutual Fund schemes. Users ask natural-language questions about NAV, expense ratios, holdings, and fund characteristics; the system retrieves relevant corpus excerpts via **semantic search** and generates concise, source-backed answers.

Built as a production-style **RAG (Retrieval-Augmented Generation)** application with a **Next.js** frontend and **FastAPI** backend, deployed on **Vercel** and **Railway**.

---

## Project Overview

This project implements a **retrieval-augmented Q&A pipeline** over a curated HDFC mutual fund corpus:

1. **Ingestion** — Fund pages and public data are fetched, cleaned, chunked, and embedded offline.
2. **Indexing** — Chunks are stored in **ChromaDB** with **Sentence Transformers (MiniLM)** vectors for semantic search.
3. **Retrieval** — User queries are embedded and matched against the indexed corpus (with optional scheme-aware filtering).
4. **Generation** — **Groq (LLM)** synthesizes short, factual answers from retrieved context; responses include official source links where available.

The **frontend** provides a modern chat experience (sidebar history, responsive layout). The **backend** exposes REST endpoints (`/health`, `/query`, `/schemes`) optimized for cloud deployment with lazy model loading and bounded timeouts.

> **Deep deployment guide:** see [DEPLOYMENT_FINAL_RAILWAY_VERCEL.md](./DEPLOYMENT_FINAL_RAILWAY_VERCEL.md) for Railway/Vercel variables, health semantics, and corpus refresh workflows.

---

## Features

- **AI-powered fund Q&A** — Natural-language questions answered with Groq-backed summarization
- **Semantic retrieval** — Vector search over `all-MiniLM-L6-v2` embeddings in ChromaDB
- **Latest corpus refresh** — Offline pipeline + `corpus_version.json`; GitHub Actions for scheduled refresh (see deployment doc)
- **Source-backed responses** — Citations and links derived from chunk metadata (official HDFC URL fallback)
- **Chat history** — Conversations persisted in browser `localStorage` with sidebar navigation
- **Responsive UI** — Dark, ChatGPT-style interface built with Next.js and Tailwind CSS
- **Railway + Vercel deployment** — API on Railway (≥ 1 GB RAM recommended); UI on Vercel

---

## Data Sources

Answers are grounded in a **whitelisted, publicly available** corpus built from:

| Source | Content |
|--------|---------|
| **HDFC Mutual Fund** official pages | Scheme names, product information, official references |
| **Groww mutual fund pages** | NAV snippets, fund overview text, performance context |
| **Public NAV / fund information** | As-of dates and NAV figures embedded in scraped HTML |
| **Fund fact sheets & SID-style disclosures** | Expense ratio, exit load, and policy text where present in corpus |
| **Portfolio & scheme metadata** | Holdings references, AUM/manager lines, and scheme-level fields from indexed chunks |

The indexed snapshot lives under `data/indexed/` (Chroma) and `data/processed/` (chunked JSON). Refresh locally with `python scripts/run_corpus_refresh.py` or via the repository’s corpus GitHub Action.

---

## Sample Questions / Q&A

Example prompts the assistant is designed to handle:

| Question | What it exercises |
|----------|-------------------|
| *What is the latest NAV of HDFC Sensex Index Fund?* | Scheme resolution + NAV extraction |
| *Compare HDFC Flexi Cap Fund vs HDFC Index Fund* | Multi-fund retrieval + comparative summary |
| *What is the expense ratio of HDFC Top 100 Fund?* | Intent detection + fee facts |
| *Show top holdings of HDFC Mid-Cap Opportunities Fund* | Holdings / portfolio chunks |
| *Which HDFC fund has lower volatility?* | Cross-scheme retrieval (informational; not advice) |

**Example flow**

```
User: What is the expense ratio for HDFC Flexi Cap Fund?
→ Semantic search (Chroma + MiniLM)
→ Top chunks + compact context
→ Groq LLM answer (or structured extractive fallback)
→ Response with source link + NAV as-of metadata
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | [Next.js](https://nextjs.org/) 14, [React](https://react.dev/), TypeScript, Tailwind CSS |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/), Uvicorn, Python 3.11 |
| **Vector DB** | [ChromaDB](https://www.trychroma.com/) (on-disk persistent index) |
| **Embeddings** | [Sentence Transformers](https://www.sbert.net/) — `all-MiniLM-L6-v2` |
| **LLM** | [Groq](https://groq.com/) API (`llama-3.1-8b-instant` with fallbacks) |
| **Hosting** | [Railway](https://railway.app) (API) · [Vercel](https://vercel.com) (UI) |

---

## Architecture (high level)

```
┌─────────────┐     HTTPS      ┌──────────────────┐
│  Next.js    │ ─────────────► │  FastAPI (Railway)│
│  (Vercel)   │   /query       │  RAG Orchestrator │
└─────────────┘                └────────┬─────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             Query processor      ChromaDB + MiniLM      Groq LLM
             (scheme/intent)     (semantic search)     (generation)
```

**Phased codebase** (offline + online):

- `phase1_ingestion_corpus_build/` — Fetch, extract, clean, chunk, embed, index
- `phase2_retrieval_layer/` — Hybrid retriever, context builder
- `phase3_reasoning_guardrails/` — Orchestrator, LLM client, answer policy
- `backend/` — Production API entrypoint
- `frontend/` — User-facing chat UI

---

## Deployment Links

| Resource | URL |
|----------|-----|
| **Live frontend** | `https://your-app.vercel.app` *(replace with your Vercel deployment)* |
| **Backend API** | `https://your-app.up.railway.app` *(replace with your Railway service)* |
| **GitHub repository** | `https://github.com/pareenamathur/milestone2_hdfc` |

**Health check:** `GET /health` on the API — returns `ready`, `rag_available`, `rag_ready`, corpus timestamps, and `api_version`.

---

## Setup Instructions

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (LTS recommended)
- **Groq API key** ([console.groq.com](https://console.groq.com)) for live LLM answers
- Committed Chroma index under `data/indexed/` (or run `python scripts/rebuild_chroma_from_chunks.py --force` after building chunks)

### Backend

From the **`Milestone2`** directory (Railway root):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp backend/.env.example backend/.env   # optional; edit GROQ_API_KEY
```

Run the API:

```bash
# From Milestone2/
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

Verify: [http://localhost:8000/health](http://localhost:8000/health)

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Environment variables

**Backend (Railway / `backend/.env`)**

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Recommended | Groq API key (`gsk_…`) for AI answers |
| `CORS_ALLOW_ORIGINS` | Production | Vercel origin(s), comma-separated |
| `QUERY_TIMEOUT_SECONDS` | Optional | Wall clock for retrieval + answer (default `120`) |
| `LLM_TIMEOUT_SECONDS` | Optional | Per Groq call timeout (default `75`) |
| `LLM_QUERY_BUDGET_SECONDS` | Optional | Reserved LLM time after retrieval (default `90`) |
| `RAG_INIT_TIMEOUT_SECONDS` | Optional | First Chroma attach timeout (default `120`) |
| `INDEXED_DATA_PATH` | Optional | Default `data/indexed` |
| `PROCESSED_DATA_PATH` | Optional | Default `data/processed` |
| `USE_BM25` / `USE_RERANKER` | Optional | Keep `false` on small cloud instances |

**Frontend (Vercel / `frontend/.env.local`)**

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | **Yes** (prod) | Railway HTTPS URL, no trailing slash |

> `OPENAI_API_KEY` is not used by the production stack; generation is **Groq-only**.

### Useful commands

```bash
# Production API (same as Railway)
sh scripts/railway_start.sh

# Rebuild Chroma from chunks
python scripts/rebuild_chroma_from_chunks.py --force

# Full corpus refresh (fetch → chunk → index)
python scripts/run_corpus_refresh.py

# Post-refresh validation
python scripts/post_refresh_check.py
```

---

## Disclaimer

**This application is an AI-powered informational assistant and should not be considered financial advice.** Responses are generated from an indexed corpus and may be incomplete, outdated, or incorrect. **Users should verify all investment information from official sources** (including [HDFC Mutual Fund](https://www.hdfcfund.com/)) before making financial decisions. The authors and deployers assume no liability for investment actions taken based on this tool.

---

## Additional documentation

| Document | Purpose |
|----------|---------|
| [DEPLOYMENT_FINAL_RAILWAY_VERCEL.md](./DEPLOYMENT_FINAL_RAILWAY_VERCEL.md) | Production deploy, env vars, troubleshooting |
| [frontend/README.md](./frontend/README.md) | Frontend-only setup |
| [data/indexed/README.md](./data/indexed/README.md) | Chroma index layout |
| [phase0_foundation_governance/](./phase0_foundation_governance/) | Scope, guardrails, stack decisions |

---

## License & attribution

Educational / portfolio project. HDFC Mutual Fund names and public data belong to their respective owners. Not affiliated with HDFC Asset Management Company Ltd.
