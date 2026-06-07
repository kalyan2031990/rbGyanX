#!/usr/bin/env python3
"""Verify BASIC/ADVANCED GUI contract and engine integration (no Tk display required)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rbgyanx.app_metadata import read_version_from_file, sync_feature_registry
from rbgyanx.logic.mode_controller import CAPABILITY_EXPOSURE, ModeController, RunMode
from rbgyanx.paths import APP_VERSION, get_engine_root


def main() -> int:
    errors: list[str] = []
    print("=== rbGyanX GUI / mode verification ===\n")

    ver = read_version_from_file(ROOT)
    print(f"VERSION.txt: {ver}")
    print(f"paths.APP_VERSION: {APP_VERSION}")
    if ver != APP_VERSION:
        errors.append(f"Version mismatch: VERSION.txt={ver} vs APP_VERSION={APP_VERSION}")

    sync_feature_registry(ROOT)
    import json

    reg = json.loads((ROOT / "core" / "feature_registry.json").read_text(encoding="utf-8"))
    reg_ver = reg.get("app_info", {}).get("version")
    print(f"feature_registry: {reg_ver}")
    if reg_ver != ver:
        errors.append(f"feature_registry version {reg_ver} != {ver}")

    engine = get_engine_root()
    print(f"engine: {engine}")
    if engine is None:
        errors.append("rbgyanx-engine not found under engine/ or engine_bundle/")

    for mode in (RunMode.BASIC, RunMode.ADVANCED):
        mc = ModeController(mode)
        caps = CAPABILITY_EXPOSURE[mode]
        ai = caps.get("ai_integration")
        ml_cap = "on" if ai else "off"
        print(f"\n{mode.value.upper()}: ai_integration={ml_cap}")
        if mode == RunMode.BASIC and ai:
            errors.append("BASIC must not enable ai_integration")
        if mode == RunMode.ADVANCED and not ai:
            errors.append("ADVANCED should enable ai_integration")

    try:
        from rbgyanx.logic import engine_bridge

        print(f"\nengine_bridge available: {engine_bridge.is_engine_available()}")
        if not engine_bridge.is_engine_available():
            errors.append("engine_bridge.is_engine_available() is False")
    except ImportError as e:
        errors.append(f"engine_bridge import: {e}")

    manual = ROOT / "docs" / "rbgyanx_user_manual.html"
    if manual.is_file():
        import re

        m = re.search(r'<meta name="version" content="([^"]+)"', manual.read_text(encoding="utf-8")[:2000])
        if m and m.group(1) != ver:
            print(f"\nManual version meta: {m.group(1)} (run Help or regenerate manual)")
        elif m:
            print(f"\nManual version meta: {m.group(1)} OK")
    else:
        print("\nManual: not generated yet (opens on first Help → User Manual)")

    print("\n---")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
