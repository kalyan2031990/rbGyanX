"""TCP site parameters for all supported cancer sites."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_YAML = _CONFIG_DIR / "site_params_default.yaml"
_USER_YAML = _CONFIG_DIR / "site_params_user.yaml"

_SITE_KEY_MAP = {
    # Anatomical / histology keys (not delivery technique).
    "BRAIN": "BRAIN_GBM",
    "BRAIN_GBM": "BRAIN_GBM",
    "GBM": "BRAIN_GBM",
    "GLIOMA": "BRAIN_GBM",
    "BRAIN_METS": "BRAIN_METS",
    "METS": "BRAIN_METS",
    "HN": "HN",
    "LUNG": "LUNG",
    "LUNG_SBRT": "LUNG",  # deprecated alias
    "NSCLC": "LUNG",
    "BREAST": "BREAST",
    "PROSTATE": "PROSTATE",
    "PELVIS": "PELVIS",
    "LIVER": "LIVER",
}


@dataclass
class TCPSiteParams:
    site: str
    alpha_gy_inv: float
    beta_gy_inv2: float
    alpha_beta_gy: float
    N0_gtv: float
    N0_ctv: float
    Tpot_days: float
    Tk_days: Optional[float]
    TCD50_gy: float
    gamma50: float
    geud_a: float
    D50_logistic_gy: float
    k_logistic: float
    lq_valid_max_dpf_gy: float
    repopulation_relevant: bool
    notes: str = ""
    params_source: str = "hardcoded"

    def _replace(self, **kwargs) -> "TCPSiteParams":
        return replace(self, **kwargs)


_KNOWN_PARAM_FIELDS = frozenset(
    f.name
    for f in fields(TCPSiteParams)
    if f.name not in ("params_source", "notes", "site")
)


SITE_PARAMS: dict[str, TCPSiteParams] = {
    "BRAIN_GBM": TCPSiteParams(
        site="BRAIN_GBM",
        alpha_gy_inv=0.30,
        beta_gy_inv2=0.033,
        alpha_beta_gy=9.0,
        N0_gtv=1e8,
        N0_ctv=1e5,
        Tpot_days=8.0,
        Tk_days=21.0,
        TCD50_gy=60.0,
        gamma50=1.8,
        geud_a=-10.0,
        D50_logistic_gy=60.0,
        k_logistic=1.8,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=True,
        notes="Glioblastoma. Standard 60Gy/30fr. High N0 due to CSC. Stupp protocol.",
    ),
    "BRAIN_METS": TCPSiteParams(
        site="BRAIN_METS",
        alpha_gy_inv=0.30,
        beta_gy_inv2=0.030,
        alpha_beta_gy=10.0,
        N0_gtv=1e6,
        N0_ctv=1e4,
        Tpot_days=10.0,
        Tk_days=None,
        TCD50_gy=19.0,
        gamma50=2.5,
        geud_a=-10.0,
        D50_logistic_gy=18.0,
        k_logistic=2.5,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=False,
        notes="Brain metastases. SRS: USC required. TCD50 in physical Gy (single fraction).",
    ),
    "HN": TCPSiteParams(
        site="HN",
        alpha_gy_inv=0.35,
        beta_gy_inv2=0.035,
        alpha_beta_gy=10.0,
        N0_gtv=1e7,
        N0_ctv=1e5,
        Tpot_days=4.0,
        Tk_days=21.0,
        TCD50_gy=60.0,
        gamma50=2.0,
        geud_a=-10.0,
        D50_logistic_gy=60.0,
        k_logistic=2.0,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=True,
        notes="H&N squamous cell carcinoma. Repopulation critical after Tk. "
        "Key modifiers: HPV status, T/N stage.",
    ),
    "LUNG": TCPSiteParams(
        site="LUNG",
        alpha_gy_inv=0.30,
        beta_gy_inv2=0.034,
        alpha_beta_gy=8.8,
        N0_gtv=1e6,
        N0_ctv=1e4,
        Tpot_days=7.0,
        Tk_days=None,
        TCD50_gy=84.5,
        gamma50=1.8,
        geud_a=-10.0,
        D50_logistic_gy=84.5,
        k_logistic=1.8,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=False,
        notes="Thoracic NSCLC (conventional or hypofractionated). "
        "LQ caution when dose/fraction > lq_valid_max_dpf_gy.",
    ),
    "BREAST": TCPSiteParams(
        site="BREAST",
        alpha_gy_inv=0.20,
        beta_gy_inv2=0.057,
        alpha_beta_gy=3.5,
        N0_gtv=5e5,
        N0_ctv=1e4,
        Tpot_days=12.0,
        Tk_days=None,
        TCD50_gy=68.0,
        gamma50=1.5,
        geud_a=-9.0,
        D50_logistic_gy=68.0,
        k_logistic=1.8,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=False,
        notes="Breast carcinoma. Low alpha/beta=3.5 → hypofractionation biologically "
        "rational (START-B, FAST-Forward). Key factors: ER/PR/HER2, grade, LVI.",
    ),
    "PROSTATE": TCPSiteParams(
        site="PROSTATE",
        alpha_gy_inv=0.15,
        beta_gy_inv2=0.10,
        alpha_beta_gy=1.5,
        N0_gtv=1e8,
        N0_ctv=1e7,
        Tpot_days=42.0,
        Tk_days=21.0,
        TCD50_gy=72.0,
        gamma50=2.2,
        geud_a=-13.0,
        D50_logistic_gy=72.0,
        k_logistic=2.2,
        lq_valid_max_dpf_gy=6.0,
        repopulation_relevant=False,
        notes="Prostate adenocarcinoma. Low alpha/beta; repopulation negligible clinically.",
    ),
    "LIVER": TCPSiteParams(
        site="LIVER",
        alpha_gy_inv=0.30,
        beta_gy_inv2=0.12,
        alpha_beta_gy=2.5,
        N0_gtv=1e6,
        N0_ctv=1e5,
        Tpot_days=10.0,
        Tk_days=None,
        TCD50_gy=55.0,
        gamma50=2.0,
        geud_a=-10.0,
        D50_logistic_gy=55.0,
        k_logistic=2.0,
        lq_valid_max_dpf_gy=10.0,
        repopulation_relevant=False,
        notes="HCC / liver SBRT or conventional.",
    ),
}


def _resolve_site_key(site: str) -> str:
    key = site.upper().strip()
    resolved = _SITE_KEY_MAP.get(key)
    if resolved is None:
        raise ValueError(
            f"Unknown site '{site}'. Supported: BRAIN_GBM, BRAIN_METS, "
            "HN, LUNG, BREAST (or BRAIN/LUNG aliases)."
        )
    return resolved


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _apply_yaml_overlay(base: TCPSiteParams, overlay: dict[str, Any]) -> TCPSiteParams:
    updates: dict[str, Any] = {}
    for key, value in overlay.items():
        if key in _KNOWN_PARAM_FIELDS:
            updates[key] = value
        else:
            logger.warning("Unknown YAML parameter key '%s' ignored", key)
    if not updates:
        return base
    return replace(base, **updates)


def build_params_snapshot(site_params: TCPSiteParams) -> dict[str, float | str | None]:
    """Build reproducibility snapshot from TCPSiteParams."""
    return {
        "alpha": float(site_params.alpha_gy_inv),
        "beta": float(site_params.beta_gy_inv2),
        "alpha_beta": float(site_params.alpha_beta_gy),
        "N0_gtv": float(site_params.N0_gtv),
        "TCD50_gy": float(site_params.TCD50_gy),
        "gamma50": float(site_params.gamma50),
        "geud_a": float(site_params.geud_a),
        "Tpot_days": float(site_params.Tpot_days),
        "Tk_days": site_params.Tk_days,
        "params_source": site_params.params_source,
    }


def load_site_params(
    site: str, user_config: Path | str | None = None
) -> TCPSiteParams:
    """
    Load TCPSiteParams for a site, merging YAML overrides onto hardcoded defaults.

    Resolution order (first found wins for each parameter):
      1. user_config path (if provided and exists)
      2. config/site_params_user.yaml (auto-detected next to site_params.py)
      3. config/site_params_default.yaml
      4. SITE_PARAMS[site] hardcoded dict
    """
    resolved = _resolve_site_key(site)
    if resolved not in SITE_PARAMS:
        raise ValueError(f"Site '{resolved}' not found in SITE_PARAMS.")

    params = SITE_PARAMS[resolved]
    params_source = "hardcoded"

    default_yaml = _load_yaml(_DEFAULT_YAML)
    if resolved in default_yaml and isinstance(default_yaml[resolved], dict):
        params = _apply_yaml_overlay(params, default_yaml[resolved])
        params_source = "default_yaml"

    user_path = Path(user_config) if user_config is not None else _USER_YAML
    user_yaml = _load_yaml(user_path) if user_path.exists() else {}
    if resolved in user_yaml and isinstance(user_yaml[resolved], dict):
        params = _apply_yaml_overlay(params, user_yaml[resolved])
        params_source = "user_yaml"

    return replace(params, site=resolved, params_source=params_source)


def get_site_params(site: str) -> TCPSiteParams:
    """Deprecated alias for load_site_params()."""
    import warnings

    warnings.warn(
        "get_site_params() is deprecated; use load_site_params() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return load_site_params(site)


def _extract_site_params_from_call(
    args: tuple[Any, ...], kwargs: dict[str, Any]
) -> TCPSiteParams | None:
    if "site_params" in kwargs:
        return kwargs["site_params"]
    for arg in args:
        if isinstance(arg, TCPSiteParams):
            return arg
    return None


def _wrap_tcp_method(func):
    """Attach params_snapshot to calculator result dicts without editing radiobiology."""

    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        site_params = _extract_site_params_from_call(args, kwargs)
        if isinstance(result, dict) and site_params is not None:
            result = dict(result)
            result["params_snapshot"] = build_params_snapshot(site_params)
        return result

    wrapper.__name__ = getattr(func, "__name__", "wrapper")
    wrapper.__doc__ = func.__doc__
    return wrapper


def _patch_tcp_calculators() -> None:
    """Inject params_snapshot into radiobiology calculator return dicts."""
    from radiobiology.geud_tcp import GEUDTCPCalculator
    from radiobiology.logistic_tcp import LogisticTCPCalculator
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from radiobiology.tcp_calculator import TCPCalculator
    from radiobiology.zaider_minerbo import ZMTCPCalculator

    patches = [
        (PoissonTCPCalculator, ("compute_tcp_uniform", "compute_tcp_dvh")),
        (ZMTCPCalculator, ("compute_tcp_uniform", "compute_tcp_dvh")),
        (GEUDTCPCalculator, ("compute_tcp",)),
        (LogisticTCPCalculator, ("compute_tcp",)),
        (TCPCalculator, ("compute_all",)),
    ]
    for cls, method_names in patches:
        for name in method_names:
            if hasattr(cls, name):
                original = getattr(cls, name)
                setattr(cls, name, _wrap_tcp_method(original))


_patch_tcp_calculators()
