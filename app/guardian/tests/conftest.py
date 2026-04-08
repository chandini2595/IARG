from __future__ import annotations

import os
import sys


# Ensure `src/` is importable when running `pytest` from this folder.
SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

