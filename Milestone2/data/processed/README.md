# `data/processed/`

Required for the **FastAPI** app to load **scheme names** at startup (`chunked_data_phase1.4.json`).

Typical files (your pipeline may vary):

- `chunked_data_phase1.4.json` — chunks + `scheme_name` (used by `backend.app`)
- Earlier phase outputs (`extracted_*`, `cleaned_*`, `embedded_*`) — ingestion only

If this folder is missing or empty, the API still boots but **`schemes_loaded`** may be **0**.
