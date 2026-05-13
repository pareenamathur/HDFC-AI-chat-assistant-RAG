"""
Streamlit Cloud entrypoint when the Git repo root is above `Milestone2/`.

The real app lives at `Milestone2/streamlit_app.py`. Set Streamlit **Packages file**
to `Milestone2/requirements.txt` (Advanced settings).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import runpy

_ROOT = Path(__file__).resolve().parent
_APP = _ROOT / "Milestone2" / "streamlit_app.py"

if not _APP.is_file():
    raise FileNotFoundError(
        f"Expected {_APP}. Clone must include the Milestone2 folder."
    )

os.chdir(_APP.parent)
if str(_APP.parent) not in sys.path:
    sys.path.insert(0, str(_APP.parent))

runpy.run_path(str(_APP), run_name="__main__")
