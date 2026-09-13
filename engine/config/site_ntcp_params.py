"""Load multi-site NTCP organ parameters from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT = Path(__file__).resolve().parent / "site_params_ntcp_default.yaml"
_USER = Path(__file__).resolve().parent / "site_params_ntcp_user.yaml"


@dataclass
class OrganNTCPParams:
    canonical: str
    geud_a: float = 3.0
    alpha_beta_gy: float = 3.0
    lkb_loglogit: dict[str, float] | None = None
    lkb_probit: dict[str, float] | None = None
    rs: dict[str, float] | None = None


@dataclass
class SiteNTCPParams:
    site_key: str
    organs: dict[str, OrganNTCPParams] = field(default_factory=dict)
    params_source: str = "default"


def _parse_organ(name: str, raw: dict[str, Any]) -> OrganNTCPParams:
    return OrganNTCPParams(
        canonical=name,
        geud_a=float(raw.get("geud_a", 3.0)),
        alpha_beta_gy=float(raw.get("alpha_beta_gy", 3.0)),
        lkb_loglogit=raw.get("LKB_loglogit"),
        lkb_probit=raw.get("LKB_probit"),
        rs=raw.get("RS"),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_site_ntcp_params(
    site_key: str,
    user_config: Path | None = None,
) -> SiteNTCPParams:
    """Merge default and optional user NTCP YAML for a site key."""
    merged: dict[str, Any] = dict(_load_yaml(_DEFAULT).get(site_key, {}))
    user_path = user_config or _USER
    if user_path.is_file():
        user_site = _load_yaml(user_path).get(site_key, {})
        for organ, params in (user_site.get("organs") or {}).items():
            base_organs = merged.setdefault("organs", {})
            base_organs[organ] = {**(base_organs.get(organ) or {}), **params}

    organs_raw = merged.get("organs") or {}
    organs = {k: _parse_organ(k, v) for k, v in organs_raw.items()}
    source = "user+default" if user_path.is_file() else "default"
    return SiteNTCPParams(site_key=site_key, organs=organs, params_source=source)


def allowed_oar_names(site_key: str, user_config: Path | None = None) -> frozenset[str]:
    return frozenset(load_site_ntcp_params(site_key, user_config).organs.keys())
