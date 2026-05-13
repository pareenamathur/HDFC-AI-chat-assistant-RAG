# HDFC Mutual Fund Assistant — Streamlit Cloud (Single App)

This document is the **authoritative** deployment guide. Legacy Railway / Render / Vercel multi-service flows are **not** used.

---

## 0. Repository layout (required for Streamlit Cloud)

### If `Milestone2/` is the Git repository root

Use **Main file path:** `streamlit_app.py`  
Use **Packages file** (Advanced): `requirements.txt` (repo root = `Milestone2/`).

```text
Milestone2/
├── streamlit_app.py
├── requirements.txt
├── .streamlit/config.toml
├── data/indexed/
├── data/processed/
├── phase2_retrieval_layer/
└── phase3_reasoning_guardrails/
```

### If the Git repo root is **above** `Milestone2/` (e.g. Desktop monorepo)

A **root** `streamlit_app.py` at the repository root (next to the `Milestone2/` folder) forwards into `Milestone2/streamlit_app.py`.

- **Main file path:** `streamlit_app.py` (at repo root — **not** inside `Milestone2/`).
- **Packages file:** `Milestone2/requirements.txt` (do **not** use the repo-root `requirements.txt` on Desktop; it pulls unrelated heavy deps).
- **Secrets / env:** unchanged (`GROQ_API_KEY`, etc.).

Optional: point **Main file path** to `Milestone2/streamlit_app.py` instead — either works if that file is committed.

---

## 1. Streamlit Cloud setup (GitHub)

1. Push the repo to GitHub.
2. In [Streamlit Cloud](https://streamlit.io/cloud): **New app** → repo → branch **`main`** → **Main file** `streamlit_app.py` (or `Milestone2/streamlit_app.py` if nested).
3. **Secrets** (for real LLM answers):

   ```toml
   GROQ_API_KEY = "your-groq-api-key"
   ```

4. **Advanced** → Python **3.11** or **3.12** (matches local verification).

### Environment variables (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | — | Groq LLM (Secrets). |
| `INDEXED_DATA_PATH` | `data/indexed` | Chroma directory (relative to cwd). |
| `PROCESSED_DATA_PATH` | `data/processed` | Folder with `chunked_data_phase1.4.json`. |
| `USE_BM25` | `false` | `true` only with `rank-bm25` installed + higher RAM. |
| `USE_RERANKER` | `false` | Keep `false` on Cloud. |
| `STREAMLIT_VECTOR_FETCH_K` | `12` | Lower → less RAM. |
| `STREAMLIT_PROTOBUF_PYTHON_IMPL` | _(unset)_ | Set to `python` only if protobuf/grpc errors persist after redeploy (pure-Python runtime). Prefer pinned `requirements.txt`. |

---

## 2. Dependencies (`requirements.txt`)

- **Protobuf:** `protobuf==3.20.3` (pinned in `requirements.txt`). If `pip` reports dependency clashes with **chromadb/grpc**, relax pins or use `STREAMLIT_PROTOBUF_PYTHON_IMPL` / resolver overrides per environment.
- **CPU-only PyTorch:** `torch==2.2.2+cpu` + `--extra-index-url https://download.pytorch.org/whl/cpu`  
  (`torch==2.0.0+cpu` is **not** published for Python 3.12+; `2.2.2+cpu` is CPU-only and Cloud-safe.)
- **Embeddings:** `sentence-transformers` → **`all-MiniLM-L6-v2`** (default in `HybridRetriever`).
- **Vector store:** `chromadb>=1.0.0,<2` (prebuilt wheels on Linux Cloud; avoids source builds).
- **LLM:** `groq` (optional **MockLLM** if no key).
- **Not included:** `pandas`, `numpy`, `openai`, `rank-bm25` (BM25 off by default).

Local run:

```bash
cd Milestone2   # or your project root containing streamlit_app.py
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Windows note:** If `pip install` fails building `chroma-hnswlib`, upgrade pip and retry, or use **WSL/Linux**; Streamlit Cloud uses **Linux** wheels and typically installs without compiling.

---

## 3. Streamlit configuration (`.streamlit/config.toml`)

- **Theme:** Slate text (`#1E293B`), teal primary (`#0F766E`), light backgrounds — compatible with **dark mode** toggle in the app menu.
- **Server:** `headless`, upload caps, `fileWatcherType = "none"`.
- **Runner:** `fastReruns`, `magicEnabled = false`.

---

## 4. Obsolete deployment artifacts

Not used for Streamlit Cloud: Railway, Vercel, FastAPI as a separate service. Optional files under `backend/` are **not** the Cloud entrypoint.

---

## 5. Summary — memory optimizations

| Area | Change |
|------|--------|
| **Embedding** | `all-MiniLM-L6-v2` only; lazy-loaded once (`_ensure_embedding_model`). |
| **Torch** | CPU index wheels — **no CUDA** packages. |
| **Thread caps** | `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `TOKENIZERS_PARALLELISM` before imports. |
| **BM25 / reranker** | **Off** by default — no full-corpus `get()`, no `CrossEncoder`. |
| **Chroma** | Bounded `query` size via `vector_fetch_k`. |
| **LLM** | Lazy `AnswerGenerator` on first answer. |
| **No API key** | `MockLLM` — app still starts. |
| **Caching** | `@st.cache_resource` orchestrator; `@st.cache_data` scheme list. |
| **GC** | `gc.collect()` after query / heavy paths. |

---

## 6. Summary — UI / UX

| Item | Implementation |
|------|----------------|
| **Contrast** | Theme CSS variables; alerts/chat inherit `--text-color`. |
| **Typography** | Headers, captions, metrics; no forced white page chrome. |
| **Layout** | Wide layout, bordered sections, tabs, expanded sidebar. |
| **Primary buttons** | White label on theme primary for contrast. |

---

## 7. Expected RAM (approximate RSS)

| Phase | RSS |
|-------|-----|
| After startup (before first query) | ~80–140 MB |
| After first retrieval | ~220–320 MB |
| Peak | ~280–400 MB with defaults |

Reduce `STREAMLIT_VECTOR_FETCH_K` to `8` if needed.

---

## 8. Troubleshooting

| Symptom | Mitigation |
|---------|------------|
| **Memory exceeded** | Keep BM25/reranker off; lower `STREAMLIT_VECTOR_FETCH_K`. |
| **Empty index on Cloud** | `data/indexed/` must contain Chroma files — see `data/indexed/README.md` (index may be gitignored). |
| **Mock answers** | Set `GROQ_API_KEY` in Secrets. |
| **pip / Chroma on Windows** | Use Linux or ensure binary wheels; Cloud uses Linux. |

---

## 9. Verification checklist

- [ ] `pip install -r requirements.txt` succeeds on your target OS (or use Linux/WSL).
- [ ] `streamlit run streamlit_app.py` — UI loads (HTTP 200).
- [ ] Search runs after first query (model load).
- [ ] Streamlit Cloud **Main file** path matches repo layout.

---

*Aligned with: single `streamlit_app.py`, CPU torch, Chroma 1.x, MiniLM, BM25/reranker off by default.*

---

## Optional — FastAPI backend + Next.js frontend (local only)

Not used on Streamlit Cloud. To run locally:

1. **Backend:** from `Milestone2/backend/` run `pip install -r ../requirements.txt` (plus `fastapi`, `uvicorn`, `pydantic`) then `python app.py` → API at **http://127.0.0.1:8000**.
2. **Frontend:** from `Milestone2/frontend/` run `npm install` then `npm run dev` → **http://localhost:3000** with `NEXT_PUBLIC_API_URL=http://localhost:8000` (see `frontend/.env.local`).
3. Pin **`numpy<2`** if PyTorch reports NumPy ABI errors (already reflected in root `requirements.txt`).
