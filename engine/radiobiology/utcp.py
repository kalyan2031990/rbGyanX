"""
UTCP — Uncomplicated TCP (Complication-Free Tumour Control Probability).

P+ = TCP × Π_{k=1}^{K} (1 − NTCP_k)

where k runs over ALL scored OARs for the treatment site.

Reference:
  Brahme A. Acta Radiol Oncol 1984;23:379–391.
  Källman P, Lind BK, Brahme A. Phys Med Biol 1992;37:871–890.
  Ågren A-K, Brahme A, Turesson I. IJROBP 1990;19:1077–1085.

Terminology note:
  UTCP ≠ uTCP.
  uTCP  = uncertainty-aware TCP   (MC CI bands, uncertainty/parameter_mc.py).
  UTCP  = Uncomplicated TCP       (plan quality composite metric, THIS module).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

UTCP_OAR_MAP: dict[str, list[dict]] = {
    "BRAIN_GBM": [
        {"oar": "Brainstem", "severity_weight": 1.0},
        {"oar": "OpticChiasm", "severity_weight": 1.0},
        {"oar": "OpticNerve_L", "severity_weight": 1.0},
        {"oar": "OpticNerve_R", "severity_weight": 1.0},
        {"oar": "NormalBrain", "severity_weight": 0.7},
        {"oar": "Hippocampus_L", "severity_weight": 0.7},
        {"oar": "Hippocampus_R", "severity_weight": 0.7},
        {"oar": "Cochlea_L", "severity_weight": 0.4},
        {"oar": "Cochlea_R", "severity_weight": 0.4},
        {"oar": "Pituitary", "severity_weight": 0.4},
    ],
    "BRAIN_METS": [
        {"oar": "Brainstem", "severity_weight": 1.0},
        {"oar": "OpticChiasm", "severity_weight": 1.0},
        {"oar": "OpticNerve_L", "severity_weight": 1.0},
        {"oar": "OpticNerve_R", "severity_weight": 1.0},
        {"oar": "NormalBrain", "severity_weight": 0.7},
        {"oar": "Hippocampus_L", "severity_weight": 0.7},
        {"oar": "Hippocampus_R", "severity_weight": 0.7},
        {"oar": "Cochlea_L", "severity_weight": 0.4},
        {"oar": "Cochlea_R", "severity_weight": 0.4},
    ],
    "HN": [
        {"oar": "SpinalCord", "severity_weight": 1.0},
        {"oar": "Brainstem", "severity_weight": 1.0},
        {"oar": "Parotid_L", "severity_weight": 0.7},
        {"oar": "Parotid_R", "severity_weight": 0.7},
        {"oar": "Mandible", "severity_weight": 0.7},
        {"oar": "PharynxConstrictor", "severity_weight": 0.7},
        {"oar": "OralCavity", "severity_weight": 0.4},
        {"oar": "Larynx", "severity_weight": 0.7},
    ],
    "LUNG_CONV": [
        {"oar": "SpinalCord", "severity_weight": 1.0},
        {"oar": "LungTotal", "severity_weight": 0.7},
        {"oar": "Lung_L", "severity_weight": 0.7},
        {"oar": "Lung_R", "severity_weight": 0.7},
        {"oar": "Esophagus", "severity_weight": 0.7},
        {"oar": "Heart", "severity_weight": 0.7},
    ],
    "LUNG_SBRT": [
        {"oar": "SpinalCord", "severity_weight": 1.0},
        {"oar": "LungTotal", "severity_weight": 0.7},
        {"oar": "Esophagus", "severity_weight": 0.7},
        {"oar": "Heart", "severity_weight": 0.7},
        {"oar": "ChestWall", "severity_weight": 0.4},
        {"oar": "Rib", "severity_weight": 0.4},
    ],
    "PROSTATE": [
        {"oar": "Rectum", "severity_weight": 1.0},
        {"oar": "Bladder", "severity_weight": 0.7},
        {"oar": "FemoralHead_L", "severity_weight": 0.4},
        {"oar": "FemoralHead_R", "severity_weight": 0.4},
        {"oar": "Urethra", "severity_weight": 0.7},
        {"oar": "SpinalCord", "severity_weight": 1.0},
    ],
    "PELVIS": [
        {"oar": "Rectum", "severity_weight": 1.0},
        {"oar": "Bladder", "severity_weight": 0.7},
        {"oar": "FemoralHead_L", "severity_weight": 0.4},
        {"oar": "FemoralHead_R", "severity_weight": 0.4},
        {"oar": "BowelBag", "severity_weight": 0.7},
        {"oar": "SpinalCord", "severity_weight": 1.0},
    ],
    "LIVER": [
        {"oar": "Liver", "severity_weight": 1.0},
        {"oar": "SpinalCord", "severity_weight": 1.0},
        {"oar": "Duodenum", "severity_weight": 0.7},
        {"oar": "Stomach", "severity_weight": 0.7},
        {"oar": "Esophagus", "severity_weight": 0.7},
    ],
    "BREAST": [
        {"oar": "Heart", "severity_weight": 1.0},
        {"oar": "LAD", "severity_weight": 0.7},
        {"oar": "Lung_Ipsi", "severity_weight": 0.7},
        {"oar": "Esophagus", "severity_weight": 0.7},
        {"oar": "Thyroid", "severity_weight": 0.4},
        {"oar": "BrachialPlexus", "severity_weight": 0.7},
        {"oar": "SpinalCord", "severity_weight": 0.7},
        {"oar": "Lung_Contra", "severity_weight": 0.4},
    ],
}

_UTCP_SITE_ALIASES = {
    "LUNG": "LUNG_CONV",
    "LUNG_SBRT": "LUNG_SBRT",
    "PROSTATE_SBRT": "PROSTATE",
    "CAP": "PROSTATE",
    "PELVIS": "PELVIS",
    "CERVIX": "PELVIS",
    "ENDOMETRIUM": "PELVIS",
    "HCC": "LIVER",
    "LIVER_SBRT": "LIVER",
}


def normalize_utcp_site(site_key: str) -> str:
    """Map TCP/NTCP site_params_key to UTCP_OAR_MAP key."""
    key = str(site_key or "").upper()
    return _UTCP_SITE_ALIASES.get(key, key)


@dataclass
class UTCPResult:
    """Per-patient UTCP result with full provenance."""

    UTCP: float
    UTCP_weighted: float
    TCP_used: float
    TCP_model: str
    NTCP_product: float
    NTCP_product_weighted: float
    scored_OARs: list[dict]
    n_oars_scored: int
    n_oars_missing: int
    missing_OAR_names: list[str]
    site: str
    AnonPatientID: str = ""
    warnings: list[str] = field(default_factory=list)


def compute_utcp(
    tcp_result: dict,
    ntcp_results: list[dict],
    site_key: str,
    tcp_model: str = "auto",
    ntcp_model: str = "LKB_loglogit",
    custom_oar_map: list[dict] | None = None,
) -> UTCPResult:
    """
    Compute UTCP for one patient (Källman 1992: TCP × Π(1−NTCP_k)).
    """
    warns: list[str] = []
    anon_id = str(tcp_result.get("AnonPatientID", ""))
    site_norm = normalize_utcp_site(site_key)

    if tcp_model == "auto":
        tcp_val = math.nan
        tcp_model_used = "none"
        for col in ("TCP_Poisson", "TCP_gEUD", "TCP_ZM", "TCP_Logistic", "TCP_mean"):
            v = tcp_result.get(col, math.nan)
            if isinstance(v, (int, float)) and not math.isnan(float(v)):
                tcp_val = float(v)
                tcp_model_used = col.replace("TCP_", "")
                break
        else:
            warns.append("No valid TCP value found.")
    else:
        col = f"TCP_{tcp_model}" if not tcp_model.startswith("TCP_") else tcp_model
        tcp_val = float(tcp_result.get(col, math.nan))
        tcp_model_used = tcp_model.replace("TCP_", "")

    ntcp_col_map = {
        "LKB_loglogit": "NTCP_LKB_loglogit",
        "LKB_probit": "NTCP_LKB_probit",
        "RS": "NTCP_RS",
    }
    ntcp_col = ntcp_col_map.get(ntcp_model, "NTCP_LKB_loglogit")

    oar_ntcp: dict[str, float] = {}
    for r in ntcp_results:
        oar = str(r.get("structure", ""))
        val = r.get(ntcp_col, math.nan)
        if oar and isinstance(val, (int, float)) and not math.isnan(float(val)):
            oar_ntcp[oar] = float(val)

    oar_list = custom_oar_map or UTCP_OAR_MAP.get(site_norm, [])
    scored_oars: list[dict] = []
    missing_oars: list[str] = []
    ntcp_product = 1.0
    ntcp_product_weighted = 1.0

    for entry in oar_list:
        oar_name = entry["oar"]
        w_k = float(entry.get("severity_weight", 1.0))

        if oar_name in oar_ntcp:
            ntcp_k = oar_ntcp[oar_name]
            ntcp_product *= 1.0 - ntcp_k
            ntcp_product_weighted *= (1.0 - ntcp_k) ** w_k
            scored_oars.append(
                {
                    "oar": oar_name,
                    "NTCP": ntcp_k,
                    "severity_weight": w_k,
                    "contribution": 1.0 - ntcp_k,
                }
            )
        else:
            missing_oars.append(oar_name)
            warns.append(
                f"OAR '{oar_name}' absent from NTCP results for site {site_key}. "
                f"UTCP product computed over {len(oar_list) - len(missing_oars)} OARs only. "
                f"UTCP may be overestimated if this OAR has high NTCP."
            )

    if math.isnan(tcp_val):
        utcp = utcp_w = math.nan
    else:
        utcp = float(tcp_val * ntcp_product)
        utcp_w = float(tcp_val * ntcp_product_weighted)

    return UTCPResult(
        UTCP=utcp,
        UTCP_weighted=utcp_w,
        TCP_used=tcp_val,
        TCP_model=tcp_model_used,
        NTCP_product=ntcp_product,
        NTCP_product_weighted=ntcp_product_weighted,
        scored_OARs=scored_oars,
        n_oars_scored=len(scored_oars),
        n_oars_missing=len(missing_oars),
        missing_OAR_names=missing_oars,
        site=site_norm,
        AnonPatientID=anon_id,
        warnings=warns,
    )


def compute_utcp_cohort(
    tcp_results: list[dict],
    ntcp_results_by_patient: dict[str, list[dict]],
    site_key: str,
    ntcp_model: str = "LKB_loglogit",
) -> list[UTCPResult]:
    """Compute UTCP for each TCP result row (one per target row in tcp_results)."""
    results: list[UTCPResult] = []
    for tcp_r in tcp_results:
        anon_id = str(tcp_r.get("AnonPatientID", ""))
        ntcp_rs = ntcp_results_by_patient.get(anon_id, [])
        results.append(
            compute_utcp(tcp_r, ntcp_rs, site_key, ntcp_model=ntcp_model)
        )
    return results


def attach_utcp_to_tcp_results(
    tcp_results: list[dict],
    ntcp_results: list[dict],
    site_key: str,
) -> list[UTCPResult]:
    """Group NTCP by patient, compute UTCP, merge fields into tcp_results."""
    from collections import defaultdict

    ntcp_by_patient: dict[str, list[dict]] = defaultdict(list)
    for r in ntcp_results:
        ntcp_by_patient[str(r.get("AnonPatientID", ""))].append(r)

    utcp_list = compute_utcp_cohort(
        tcp_results, dict(ntcp_by_patient), site_key
    )
    utcp_map = {u.AnonPatientID: u for u in utcp_list}
    for r in tcp_results:
        pid = str(r.get("AnonPatientID", ""))
        if pid not in utcp_map:
            continue
        u = utcp_map[pid]
        r["UTCP"] = u.UTCP
        r["UTCP_weighted"] = u.UTCP_weighted
        r["UTCP_NTCP_product"] = u.NTCP_product
        r["UTCP_OARs_scored"] = u.n_oars_scored
        r["UTCP_OARs_missing"] = u.n_oars_missing
        r["UTCP_missing_OARs"] = ", ".join(u.missing_OAR_names)
        r["UTCP_TCP_model"] = u.TCP_model
    return utcp_list
