"""
Application paths for rbGyanX Desktop (dev tree and PyInstaller frozen build).

Resolution order for engine root:
  1. RBGYANX_ENGINE_PATH environment variable
  2. <app_root>/engine_bundle  (shipped with standalone installer)
  3. <app_root>/engine  (monorepo layout)
  4. <app_root>/../rbGyanX_cdss  (legacy sibling repo)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "rbGyanX"


def _load_app_version() -> str:
    vf = Path(__file__).resolve().parents[1] / "VERSION.txt"
    if vf.is_file():
        import re

        for line in vf.read_text(encoding="utf-8").splitlines():
            m = re.search(r"Version\s+([\d.]+)", line, re.I)
            if m:
                return m.group(1).strip()
    return "1.0.0"


APP_VERSION = _load_app_version()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    """Directory containing rbGyanX.exe or the rbgyanx_dual project root."""
    env = os.environ.get("RBGYANX_APP_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # rbgyanx/paths.py -> rbgyanx_dual
    return Path(__file__).resolve().parents[1]


def get_scripts_dir() -> Path:
    """Legacy code1–7 and utils live at app root."""
    return get_app_root()


def _engine_marker(root: Path) -> Path:
    return root / "rbgyanx_engine" / "__init__.py"


def get_engine_root() -> Path | None:
    """Resolved rbgyanx-engine repository root, or None if not found."""
    candidates: list[Path] = []
    env = os.environ.get("RBGYANX_ENGINE_PATH", "").strip()
    if env:
        candidates.append(Path(env))
    app = get_app_root()
    candidates.extend(
        [
            app / "engine_bundle",
            app / "engine",
            app.parent / "rbGyanX_cdss",
            app.parent / "rbgyanx_cdss",
        ]
    )
    seen: set[str] = set()
    for root in candidates:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if _engine_marker(resolved).is_file():
            return resolved
    return None


def get_user_data_dir() -> Path:
    """Writable per-user folder (configs, logs) — not inside Program Files."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        path = Path(base) / "rbGyanX"
    else:
        path = Path.home() / ".rbgyanx"
    path.mkdir(parents=True, exist_ok=True)
    return path


def engine_status_message() -> str:
    root = get_engine_root()
    if root is None:
        return "rbgyanx-engine: NOT FOUND (install engine_bundle or set RBGYANX_ENGINE_PATH)"
    return f"rbgyanx-engine: OK ({root})"
