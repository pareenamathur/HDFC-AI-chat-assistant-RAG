# Chroma vector index (`data/indexed/`)

The FastAPI retriever expects a **persistent Chroma 1.x** database in this folder:

| File / dir | Role |
|------------|------|
| `chroma.sqlite3` | Chroma metadata & config |
| UUID-named subfolders | HNSW / segment binary data |

Collection name: **`mf_faq_corpus`** (cosine space; embeddings from **`all-MiniLM-L6-v2`**).

## Why Railway needs this

If this folder is **empty** or **incomplete**, `HybridRetriever` cannot call `get_collection("mf_faq_corpus")` and the API stays in **degraded** mode (`rag_available=false`).  
**`mock_mode`** in `/health` refers only to **missing `GROQ_API_KEY`** (LLM demo), **not** to Chroma.

## Rebuild from processed chunks (recommended)

From **`Milestone2/`** (after `pip install -r requirements.txt`):

```bash
python scripts/rebuild_chroma_from_chunks.py --force
```

Source: `data/processed/chunked_data_phase1.4.json`  
Output: this directory (relative paths in metadata; safe on Linux + Windows).

Then **commit** `chroma.sqlite3` and the UUID folder(s) so Railway clones include the index.

## Diagnostics

```bash
python scripts/diagnose_data_index.py
```

Prints `INDEXED_FOLDER_EXISTS`, `CHROMA_SQLITE_PRESENT`, chunk counts, and collection size.

## Railway timeouts

First cold start downloads **SentenceTransformer** weights. Set **`RAG_INIT_TIMEOUT_SECONDS`** (default in app **120**) high enough in Railway variables if deploys are slow.
