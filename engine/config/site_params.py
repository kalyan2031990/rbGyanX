"""TCP site parameters for all supported cancer sites.

Resolution rule: a requested site either yields a parameter object whose ``site`` field is the
site that was asked for, or it raises. It never substitutes. Three defects against that rule
were fixed in v1.3.0:

* ``PROSTATE_SBRT`` had parameters in ``site_params_default.yaml`` -- materially different from
  conventional prostate (TCD50 36.25 Gy vs 72.0) -- but was missing from ``_SITE_KEY_MAP``, so
  it was rejected as an unknown site and those parameters were unreachable;
* ``PELVIS`` was mapped but had no parameter object anywhere, so it failed with an
  internal-sounding "not found in SITE_PARAMS" message. It is now declared in
  ``_SITES_WITHOUT_TCP_PARAMS`` and raises :class:`SiteParamsUnavailable` with the reason;
* ``LUNG_SBRT`` was mapped to ``LUNG``, so a caller asking for SBRT parameters was handed the
  conventional-fractionation set with no indication. It now resolves to its own entry. Those
  values are still the conventional ones -- no SBRT-specific lung set has been adopted -- but
  the object says so in ``notes`` instead of the substitution being invisible.

Also exposes :func:`SiteParamsUnavailable` so callers can tell "not parameterised" from
"misspelled".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, cast

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_YAML = _CONFIG_DIR / "site_params_default.yaml"
_USER_YAML = _CONFIG_DIR / "site_params_user.yaml"

_SITE_KEY_MAP = {
    # Anatomical / histology keys, plus the two technique-specific keys that carry their own
    # parameter sets. A key may only map to something other than itself when the two are
    # genuinely the same parameter set (e.g. GBM -> BRAIN_GBM); it must never map a
    # technique-specific request onto a conventional-fractionation set. See
    # _SITES_WITHOUT_TCP_PARAMS for recognised sites that have no parameters at all.
    "BRAIN": "BRAIN_GBM",
    "BRAIN_GBM": "BRAIN_GBM",
    "GBM": "BRAIN_GBM",
    "GLIOMA": "BRAIN_GBM",
    "BRAIN_METS": "BRAIN_METS",
    "METS": "BRAIN_METS",
    "HN": "HN",
    "LUNG": "LUNG",
    "LUNG_SBRT": "LUNG_SBRT",
    "NSCLC": "LUNG",
    "BREAST": "BREAST",
    "PROSTATE": "PROSTATE",
    "PROSTATE_SBRT": "PROSTATE_SBRT",
    "PELVIS": "PELVIS",
    "LIVER": "LIVER",
}

#: Sites the detector and the interface recognise, but for which this project has adopted no
#: TCP parameter set. Requesting one raises :class:`SiteParamsUnavailable` naming the reason.
#: Listing them explicitly is the point: a site that is merely absent from SITE_PARAMS fails
#: with an internal-sounding error, and the previous PELVIS behaviour was exactly that.
_SITES_WITHOUT_TCP_PARAMS: dict[str, str] = {
    "PELVIS": (
        "no single published TCP parameter set applies to a pelvic volume, which is treated as "
        "a multi-target site (cervix, endometrium, rectum, nodal volumes) with different "
        "alpha/beta and clonogen assumptions per target. Pelvic plans are supported for DVH, "
        "NTCP and UTCP scoring; TCP requires you to name the specific target site."
    ),
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
    Tk_days: float | None
    TCD50_gy: float
    gamma50: float
    geud_a: float
    D50_logistic_gy: float
    k_logistic: float
    lq_valid_max_dpf_gy: float
    repopulation_relevant: bool
    notes: str = ""
    params_source: str = "hardcoded"

    def _replace(self, **kwargs) -> TCPSiteParams:
        return replace(self, **kwargs)


_KNOWN_PARAM_FIELDS = frozenset(
    f.name for f in fields(TCPSiteParams) if f.name not in ("params_source", "notes", "site")
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
    # Values are exactly those declared for LUNG_SBRT in site_params_default.yaml, which are
    # the conventional LUNG values. They are NOT an SBRT-specific parameter set: this project
    # has not adopted one. The key exists so that a caller asking for LUNG_SBRT is answered with
    # a parameter object that says LUNG_SBRT and carries this caveat, instead of being silently
    # handed the conventional LUNG object as though it had been validated for SBRT.
    # lq_valid_max_dpf_gy stays at the conventional 10 Gy precisely so that SBRT fractionation
    # trips the LQ-validity guard rather than passing unremarked. See docs/KNOWN_LIMITATIONS.md.
    "LUNG_SBRT": TCPSiteParams(
        site="LUNG_SBRT",
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
        notes="Lung SBRT. WARNING: these are the CONVENTIONAL thoracic NSCLC parameters; no "
        "SBRT-specific lung TCP parameter set has been adopted in this project. TCD50 is a "
        "conventional-fractionation value and the LQ validity cap is 10 Gy/fraction, which "
        "typical SBRT fractionation exceeds. Treat TCP for this site as indicative only.",
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
    # Values as declared for PROSTATE_SBRT in site_params_default.yaml. Unlike LUNG_SBRT these
    # differ materially from the conventional set (TCD50 36.25 Gy vs 72.0, gamma50 2.5 vs 2.2),
    # so the parameters were present and simply unreachable: PROSTATE_SBRT was absent from
    # _SITE_KEY_MAP, and load_site_params rejected it as an unknown site.
    "PROSTATE_SBRT": TCPSiteParams(
        site="PROSTATE_SBRT",
        alpha_gy_inv=0.15,
        beta_gy_inv2=0.10,
        alpha_beta_gy=1.5,
        N0_gtv=1e8,
        N0_ctv=1e7,
        Tpot_days=42.0,
        Tk_days=21.0,
        TCD50_gy=36.25,
        gamma50=2.5,
        geud_a=-13.0,
        D50_logistic_gy=36.25,
        k_logistic=2.5,
        lq_valid_max_dpf_gy=6.0,
        repopulation_relevant=False,
        notes="Prostate SBRT / ultrahypofractionation. TCD50 expressed for the SBRT regime, "
        "not the conventional 72 Gy value. Low alpha/beta = 1.5.",
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


class SiteParamsUnavailable(ValueError):
    """A recognised site for which no TCP parameter set has been adopted.

    Distinct from an unknown site: the caller spelled something this project understands, and
    the answer is "not parameterised", with a reason. Subclasses ValueError so existing callers
    that catch ValueError keep working.
    """


def _supported_sites() -> str:
    """The sites that actually load, derived rather than hardcoded.

    The previous message was a hand-maintained list that had gone stale -- it advertised five
    sites and omitted PROSTATE, LIVER and PELVIS. Deriving it means it cannot drift again.
    """
    loadable = sorted(k for k, v in _SITE_KEY_MAP.items() if v in SITE_PARAMS)
    return ", ".join(loadable)


def _resolve_site_key(site: str) -> str:
    """Resolve a site spelling to a canonical SITE_PARAMS key.

    Raises rather than substituting. A technique-specific key (LUNG_SBRT, PROSTATE_SBRT) resolves
    to its own parameter set, never to the conventional-fractionation set for the same anatomy:
    silently answering an SBRT request with conventional parameters is the failure mode this
    function exists to prevent.
    """
    key = site.upper().strip()
    resolved = _SITE_KEY_MAP.get(key)
    if resolved is None:
        raise ValueError(
            f"Unknown site {site!r}. Supported: {_supported_sites()}."
        )
    if resolved in _SITES_WITHOUT_TCP_PARAMS:
        raise SiteParamsUnavailable(
            f"No TCP parameter set is defined for site {resolved!r}: "
            f"{_SITES_WITHOUT_TCP_PARAMS[resolved]} "
            f"Sites with TCP parameters: {_supported_sites()}."
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


def load_site_params(site: str, user_config: Path | str | None = None) -> TCPSiteParams:
    """
    Load TCPSiteParams for a site, merging YAML overrides onto hardcoded defaults.

    Resolution order (first found wins for each parameter):
      1. user_config path (if provided and exists)
      2. config/site_params_user.yaml (auto-detected next to site_params.py)
      3. config/site_params_default.yaml
      4. SITE_PARAMS[site] hardcoded dict
    """
    resolved = _resolve_site_key(site)
    if resolved not in SITE_PARAMS:  # pragma: no cover - guarded by _resolve_site_key
        # Reachable only if _SITE_KEY_MAP gains a target that is neither in SITE_PARAMS nor in
        # _SITES_WITHOUT_TCP_PARAMS. test_site_params_routing.py asserts that cannot happen, so
        # this is a belt-and-braces internal consistency check, not a user-facing path.
        raise ValueError(
            f"Internal inconsistency: site key {resolved!r} is mapped but has no parameter "
            f"object and is not declared in _SITES_WITHOUT_TCP_PARAMS."
        )

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
        return cast("TCPSiteParams | None", kwargs["site_params"])
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
