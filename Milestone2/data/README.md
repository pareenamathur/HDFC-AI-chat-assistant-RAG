# `Milestone2/data/` — required layout

Your repository should keep this structure (paths relative to **`Milestone2/`**):

```text
Milestone2/
└── data/
    ├── indexed/      # Chroma vector store (see indexed/README.md)
    └── processed/    # Pipeline JSON (e.g. chunked_data_phase1.4.json)
```

| Folder | In Git | Purpose |
|--------|--------|---------|
| **`processed/`** | Yes (JSON artifacts) | Scheme names + chunks for ingestion / API startup scheme list |
| **`indexed/`** | **README only**; Chroma files are **gitignored** (`data/indexed/*`) | Runtime vector DB — build locally or in CI, then deploy or mount |

---

# Data directory (detail)

This tree holds all assistant data, organized by processing stage.

## Full layout (optional folders)

```text
data/
├── raw/           # Optional — raw downloads (Phase 1.1)
├── html/          # Scraped HTML (may be gitignored in your fork)
├── documents/     # PDFs (may be gitignored)
├── processed/     # Cleaned / chunked JSON (Phases 1.2–1.4+)
└── indexed/       # ChromaDB persistence (Phase 1.6)
```

## Data flow (summary)

```text
Fetcher → html/documents → processed → indexed (Chroma)
```

See **`indexed/README.md`** for how to populate Chroma when `indexed/` is empty after clone.
