"""
If Streamlit Cloud's Main file wrongly points at a FastAPI module (e.g. backend/app.py),
the old behavior was sys.exit(0) — that terminates the Streamlit worker → health checks 404.

This helper keeps the Streamlit process alive and shows a fix-it page instead.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional


def run_backend_cli_or_streamlit_stub(
    app_import_str: Optional[str] = None,
    *,
    uvicorn_app: Any = None,
    default_port: str = "8000",
    logger: Optional[Any] = None,
    extra_uvicorn_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    """
    ALLOW_LOCAL_FASTAPI=1 → uvicorn.
    Else if loaded under `streamlit run` → show misconfiguration UI (do not exit).
    Else → stderr message + exit 0 for plain `python app.py`.
    """
    if app_import_str is None and uvicorn_app is None:
        raise ValueError("Provide app_import_str or uvicorn_app")

    allow = os.getenv("ALLOW_LOCAL_FASTAPI", "").strip().lower() in ("1", "true", "yes")
    if allow:
        import uvicorn

        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", default_port))
        kw: Dict[str, Any] = {
            "host": host,
            "port": port,
            "workers": 1,
            "reload": False,
            "access_log": True,
            "log_level": os.getenv("LOG_LEVEL", "info").lower(),
        }
        if extra_uvicorn_kwargs:
            kw.update(extra_uvicorn_kwargs)
        if logger:
            logger.info("Starting FastAPI server on %s:%s", host, port)
        if uvicorn_app is not None:
            uvicorn.run(uvicorn_app, **kw)
        else:
            uvicorn.run(app_import_str, **kw)
        return

    # Streamlit executes the script after importing streamlit itself — never kill the worker.
    if "streamlit" in sys.modules:
        import streamlit as st

        st.set_page_config(page_title="HDFC Assistant — fix entrypoint", layout="centered")
        st.error("Wrong Streamlit Main file")
        st.markdown(
            "This file is the **FastAPI** backend (`backend/app.py`), not the Streamlit UI.\n\n"
            "In **Streamlit Cloud → App settings**, set **Main file path** to:\n\n"
            "- **`streamlit_app.py`** (repo root), or\n"
            "- **`Milestone2/streamlit_app.py`**\n\n"
            "Use **Packages file** `Milestone2/requirements.txt` when applicable. "
            "Then **Redeploy**."
        )
        st.stop()
        return

    print(
        "FastAPI is opt-in. Deployment uses Streamlit (`streamlit_app.py`).\n"
        "Local API: ALLOW_LOCAL_FASTAPI=1 python app.py\n"
        "Or: uvicorn app:app --host 127.0.0.1 --port 8000",
        file=sys.stderr,
    )
    raise SystemExit(0)
