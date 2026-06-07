"""Re-export from rbgyanx-engine — single source of truth."""
import sys
from pathlib import Path

_engine_root = Path(__file__).resolve().parents[3] / "engine"
if str(_engine_root) not in sys.path:
    sys.path.insert(0, str(_engine_root))

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit  # noqa: F401

__all__ = ["calculate_ntcp_lkb_loglogit"]
