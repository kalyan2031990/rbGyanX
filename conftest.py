"""
Root pytest configuration — ensures monorepo packages import without RBGYANX_ENGINE_PATH.

Preferred install (reproducible):
    pip install -e ./engine -e ./engine_advanced -e ./engine_advanced_f -e ".[dev]"
    pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Editable installs should satisfy imports; these paths are a clean-checkout fallback only.
_FALLBACK_PATHS = (
    ROOT,
    ROOT / "engine",
    ROOT / "engine" / "tests",
    ROOT / "engine_advanced",
    ROOT / "engine_advanced_f",
)

for p in _FALLBACK_PATHS:
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
