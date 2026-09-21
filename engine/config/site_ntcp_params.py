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


def _validate_default_organ_keys_reachable() -> None:
    """Every organ key in the shipped default NTCP YAML must resolve, through canon_target(),
    to itself as a recognised OAR.

    A key that doesn't is silently unreachable: get_oar_structures() (dicom_io/structure_mapper.py)
    drops the corresponding ROI with a bare `continue` before DVH extraction, with no warning and
    no reason code -- a real ROI's NTCP would simply never compute, indistinguishable from that
    patient never having had the structure at all. This found seven such keys (HN/BRAIN_GBM/
    BRAIN_METS "Brainstem", BREAST "Lung_Ipsi"/"Lung_Contra", PROSTATE "FemoralHead_L"/"_R") that
    had shipped silently broken. Runs once at import time -- not per site_key, so it can't stay
    hidden just because a given run never happens to exercise the affected site.
    """
    from dicom_io.structure_mapper import canon_target  # local import: avoids a module-load-order
    # dependency between config.site_ntcp_params and dicom_io at package-init time.

    data = _load_yaml(_DEFAULT)
    unreachable = []
    for site, block in data.items():
        for organ_key in (block.get("organs") or {}):
            mapped = canon_target(organ_key)
            if mapped["canonical"] != organ_key or mapped["category"] != "OAR":
                unreachable.append(
                    f"{site}/{organ_key} -> canon_target gives canonical={mapped['canonical']!r} "
                    f"category={mapped['category']!r} (needs canonical=={organ_key!r}, category=='OAR')"
                )
    if unreachable:
        raise RuntimeError(
            "site_params_ntcp_default.yaml has organ key(s) that do not resolve through "
            "canon_target() to themselves as a recognised OAR -- their NTCP would silently never "
            "compute for any patient. Fix the YAML key (or add a matching alias in "
            "config/structure_aliases.py) so canon_target(key) == key with category 'OAR':\n  "
            + "\n  ".join(unreachable)
        )


_validate_default_organ_keys_reachable()
