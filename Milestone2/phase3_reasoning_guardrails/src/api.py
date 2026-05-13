"""
Compatibility shim when the start command still targets this module, e.g.:

  uvicorn phase3_reasoning_guardrails.src.api:app

Canonical production entry (Railway / docs):

  uvicorn backend.app:app --host 0.0.0.0 --port $PORT

Both resolve to the **same** FastAPI application instance from `backend.app`.
"""

from __future__ import annotations

import os
import sys

_THIS = os.path.abspath(__file__)
# .../Milestone2/phase3_reasoning_guardrails/src/api.py → Milestone2 root
_MILESTONE2 = os.path.dirname(os.path.dirname(os.path.dirname(_THIS)))
if _MILESTONE2 not in sys.path:
    sys.path.insert(0, _MILESTONE2)

from backend.app import app  # noqa: E402

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=1,
    )
