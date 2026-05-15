#!/usr/bin/env sh
set -eu

# Railway / production defaults — avoid OOM crash loops on small instances
export PYTHONPATH="${PYTHONPATH:-.}"
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export RAG_BACKGROUND_WARM="${RAG_BACKGROUND_WARM:-false}"
export RAG_EMBEDDING_WARM="${RAG_EMBEDDING_WARM:-false}"

PORT="${PORT:-8000}"
exec uvicorn backend.app:app --host 0.0.0.0 --port "${PORT}" --workers 1
