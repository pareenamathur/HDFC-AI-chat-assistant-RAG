# Chroma vector index (required at runtime)

Railway / Docker expect a persisted Chroma database **here** (`data/indexed/`), typically:

- `chroma.sqlite3`
- UUID subfolder(s) with segment data

## If this folder is empty after `git clone`

1. Build the index locally using your ingestion/embed pipeline, **or**
2. Copy a prepared `data/indexed/` directory into the project before deploy, **or**
3. Remove `data/indexed/*` from `.gitignore` temporarily and commit the index (large repo).

The API opens `PersistDirectory=…/data/indexed` and expects collection **`mf_faq_corpus`**.
