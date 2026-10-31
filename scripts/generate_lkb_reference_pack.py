#!/usr/bin/env python3
"""Regenerate rbgyanx/ai/reference_packs/rbgyanx_lkb_defaults.json from the engine config.

The pack has always declared ``generated_from: engine/config/site_params_ntcp_default.yaml``, but
no generator was committed, so the claim could only be kept true by hand -- and it drifted: when
the v1.5.0 parameter review changed HN/SpinalCord from 45.0 to 66.5 Gy, the pack still said 45.0
and ``tests/test_ai_literature.py::test_the_lkb_pack_agrees_with_the_engine_yaml`` caught it. This
script makes the claim mechanical.

Each entry's citation now carries the value's real source, page and endpoint from the YAML's
per-model provenance, instead of pointing back at the YAML, and an unsourced value says so.

Usage:
    python scripts/generate_lkb_reference_pack.py [--check]

``--check`` regenerates in memory and exits non-zero if the committed pack differs, which is what
CI wants; without it the pack is rewritten in place.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "engine" / "config" / "site_params_ntcp_default.yaml"
PACK_PATH = ROOT / "rbgyanx" / "ai" / "reference_packs" / "rbgyanx_lkb_defaults.json"

MODELS = ("LKB_loglogit", "LKB_probit", "RS")
GY_METRICS = {"TD50_gy", "D50_gy"}

PACK_HEADER = {
    "pack_id": "rbgyanx-lkb-defaults",
    "pack_version": "1.2.0",
    "title": "rbGyanX shipped NTCP model parameters",
    "description": (
        "The LKB / relative-seriality parameter values rbGyanX itself uses, exposed so a "
        "comparison against them is arithmetic rather than a model's recollection. Since v1.5.0 "
        "each entry carries the source, table and page the value was transcribed from, or states "
        "that it has none."
    ),
    "applicability": (
        "These are the tool's own defaults, not a clinical standard. A site that overrides them "
        "in site_params_ntcp_user.yaml should regenerate this pack. An entry whose citation says "
        "'no published source' is illustrative: BASIC mode refuses it and ADVANCED mode labels it."
    ),
    "maintainer_review": "generated",
    "generated_from": "engine/config/site_params_ntcp_default.yaml",
}


def citation_for(provenance: dict | None) -> str:
    """One line a reader can chase, built from the value's own provenance block."""
    if not isinstance(provenance, dict) or provenance.get("illustrative", True):
        note = str((provenance or {}).get("note", "")).strip()
        base = (
            "rbGyanX shipped default with no published source (illustrative): BASIC mode refuses "
            "it, ADVANCED mode labels it"
        )
        return f"{base}. {note}" if note else base
    parts = [str(provenance.get("source", "")).strip()]
    page = str(provenance.get("table_page", "")).strip()
    if page:
        parts.append(page)
    endpoint = str(provenance.get("endpoint", "")).strip()
    if endpoint and endpoint != "not stated":
        parts.append(f"endpoint: {endpoint}")
    structure = str(provenance.get("structure_definition", "")).strip()
    if structure and structure != "not stated":
        parts.append(f"structure: {structure}")
    return " — ".join(p for p in parts if p)


def build_pack() -> dict:
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    entries: list[dict] = []
    for site_key, site in raw.items():
        for organ, params in (site.get("organs") or {}).items():
            provenance = params.get("provenance") or {}
            for model in MODELS:
                block = params.get(model) or {}
                for name, value in block.items():
                    entries.append(
                        {
                            "organ": organ,
                            "site": site_key,
                            "endpoint": f"{model} parameter",
                            "metric": name,
                            "comparator": "=",
                            "value": float(value),
                            "units": "Gy" if name in GY_METRICS else None,
                            "risk_pct": None,
                            "citation": citation_for(provenance.get(model)),
                        }
                    )
    return {**PACK_HEADER, "entries": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed pack differs from the engine config",
    )
    args = parser.parse_args()

    pack = build_pack()
    rendered = json.dumps(pack, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = PACK_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(
                "rbgyanx_lkb_defaults.json is out of date with "
                "engine/config/site_params_ntcp_default.yaml. "
                "Run: python scripts/generate_lkb_reference_pack.py",
                file=sys.stderr,
            )
            return 1
        print(f"pack is current: {len(pack['entries'])} entries")
        return 0

    PACK_PATH.write_text(rendered, encoding="utf-8")
    sourced = sum(
        1 for e in pack["entries"] if not e["citation"].startswith("rbGyanX shipped default")
    )
    print(
        f"wrote {PACK_PATH.relative_to(ROOT)}: {len(pack['entries'])} entries, "
        f"{sourced} with a published source"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
