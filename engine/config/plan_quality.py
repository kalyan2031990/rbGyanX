"""Load site/technique plan-quality index packs from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT = Path(__file__).resolve().parent / "plan_quality_indices_default.yaml"
_USER = Path(__file__).resolve().parent / "plan_quality_indices_user.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_plan_quality_config(user_config: Path | None = None) -> dict[str, Any]:
    merged = dict(_load_yaml(_DEFAULT))
    user_path = user_config or _USER
    if user_path.is_file():
        for site_key, site_block in _load_yaml(user_path).items():
            base = merged.setdefault(site_key, {})
            if isinstance(site_block, dict):
                for k, v in site_block.items():
                    if k == "technique_profiles" and isinstance(v, dict):
                        profiles = base.setdefault("technique_profiles", {})
                        profiles.update(v)
                    else:
                        base[k] = v
    return merged


def resolve_pack_site_key(site_params_key: str, technique_profile: str) -> str:
    if site_params_key == "LUNG" and technique_profile == "sbrt":
        return "LUNG_SBRT"
    return site_params_key


def infer_technique_profile(plan_metadata: dict) -> str:
    """
    Classify fractionation style for index-pack selection.

    Returns one of: ``sbrt``, ``hypofractionated``, ``conventional``.
    """
    dpf = float(plan_metadata.get("dose_per_fraction_gy") or 0.0)
    nfx = int(plan_metadata.get("number_of_fractions") or 0)
    if dpf >= 5.0 or (nfx > 0 and nfx <= 8 and dpf >= 4.0):
        return "sbrt"
    if dpf >= 2.6:
        return "hypofractionated"
    return "conventional"


def get_site_pack(
    site_params_key: str,
    technique_profile: str,
    user_config: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (pack_site_key, profile_block) with fallback to DEFAULT."""
    cfg = load_plan_quality_config(user_config)
    pack_key = resolve_pack_site_key(site_params_key, technique_profile)
    site_block = cfg.get(pack_key) or cfg.get(site_params_key) or cfg.get("DEFAULT", {})
    profiles = site_block.get("technique_profiles") or {}
    profile_block = profiles.get(technique_profile)
    if profile_block is None and technique_profile == "sbrt":
        profile_block = profiles.get("hypofractionated")
    if profile_block is None:
        profile_block = profiles.get("conventional") or {}
    return pack_key, profile_block


def physical_oar_canonicals(
    site_params_key: str,
    technique_profile: str,
    ntcp_oars: frozenset[str],
    user_config: Path | None = None,
) -> frozenset[str]:
    cfg = load_plan_quality_config(user_config)
    pack_key = resolve_pack_site_key(site_params_key, technique_profile)
    site_block = cfg.get(pack_key) or cfg.get(site_params_key) or {}
    listed = site_block.get("oar_canonicals") or []
    return frozenset(set(listed) | set(ntcp_oars))
