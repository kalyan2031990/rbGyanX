"""Single source of truth for rbGyanX product version and help/about sync."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rbgyanx.paths import get_app_root


def read_version_from_file(root: Path | None = None) -> str:
    root = root or get_app_root()
    version_file = root / "VERSION.txt"
    default = "1.0.0"
    if not version_file.is_file():
        return default
    try:
        text = version_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.search(r"Version\s+([\d.]+)", line, re.I)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return default


def read_release_date(root: Path | None = None) -> str:
    root = root or get_app_root()
    version_file = root / "VERSION.txt"
    if not version_file.is_file():
        return ""
    try:
        for line in version_file.read_text(encoding="utf-8").splitlines():
            if "Release Date" in line:
                return line.split(":", 1)[-1].strip()
    except OSError:
        pass
    return ""


def sync_feature_registry(root: Path | None = None) -> bool:
    """Align core/feature_registry.json app_info with VERSION.txt."""
    root = root or get_app_root()
    registry_path = root / "core" / "feature_registry.json"
    if not registry_path.is_file():
        return False
    version = read_version_from_file(root)
    try:
        data: dict[str, Any] = json.loads(registry_path.read_text(encoding="utf-8"))
        app_info = data.setdefault("app_info", {})
        changed = app_info.get("version") != version or app_info.get("name") != "rbGyanX"
        app_info["version"] = version
        app_info["name"] = "rbGyanX"
        app_info.setdefault(
            "description",
            "Radiobiology CDSS: DICOM TCP/NTCP, UTCP, QUANTEC, plan-quality indices, optional ML (ADVANCED)",
        )
        if changed:
            registry_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return changed
    except (OSError, json.JSONDecodeError):
        return False


def resolve_display_version(feature_registry: dict | None, root: Path | None = None) -> str:
    """Version string for About / Help — VERSION.txt wins over stale registry."""
    file_ver = read_version_from_file(root)
    if feature_registry:
        reg_ver = (feature_registry.get("app_info") or {}).get("version")
        if reg_ver and reg_ver != file_ver:
            return file_ver
        if reg_ver:
            return reg_ver
    return file_ver
