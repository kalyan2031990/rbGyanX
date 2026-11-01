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

from radiobiology.ntcp_row import select_ntcp

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


#: Reason written when P+ cannot be formed because a listed OAR was never scored (#20).
UTCP_INCOMPLETE_OAR_SET = "UTCP_INCOMPLETE_OAR_SET"

#: Reason written when the site has no NTCP parameter block at all, so no OAR of it can ever be
#: scored and P+ is undefined rather than merely incomplete. PELVIS is the one shipped example:
#: its UTCP map lists six OARs and site_params_ntcp_default.yaml has no PELVIS block. Inventing
#: parameters for them is a scientific decision, not a code fix.
UTCP_SITE_UNSUPPORTED = "UTCP_SITE_UNSUPPORTED"


def site_has_ntcp_parameters(site_key: str) -> bool:
    """Whether the NTCP parameter library has any organ for this site."""
    from config.site_ntcp_params import load_site_ntcp_params

    try:
        return bool(load_site_ntcp_params(site_key).organs)
    except Exception:  # pragma: no cover - a missing block is the answer, not an error
        return False


def normalize_utcp_site(site_key: str) -> str:
    """Map TCP/NTCP site_params_key to UTCP_OAR_MAP key."""
    key = str(site_key or "").upper()
    return _UTCP_SITE_ALIASES.get(key, key)


def resolve_oar_map(oar_list: list[dict]) -> list[dict]:
    """Canonicalise every OAR name in a UTCP map through ``canon_target`` (defect #20).

    The map was written by hand against the canonical vocabulary and drifted from it: the HN,
    BRAIN_GBM and BRAIN_METS entries said ``Brainstem`` while the NTCP parameter library and the
    structure mapper both use ``BrainStem``, so the brainstem was reported missing from P+ on
    every patient at three sites. BREAST listed ``Lung_Ipsi`` and ``Lung_Contra``, which both
    canonicalise to ``LungTotal`` -- one organ entered the product twice.

    Entries are resolved and de-duplicated, keeping the highest severity weight (the
    conservative choice). ``oar`` becomes the canonical key; ``oar_listed`` keeps what the map
    actually said, so the drift stays visible.
    """
    from dicom_io.structure_mapper import canon_target

    resolved: dict[str, dict] = {}
    for entry in oar_list:
        listed = str(entry["oar"])
        canonical = canon_target(listed)["canonical"]
        weight = float(entry.get("severity_weight", 1.0))
        existing = resolved.get(canonical)
        if existing is None:
            resolved[canonical] = {**entry, "oar": canonical, "oar_listed": listed}
            continue
        existing["oar_listed"] = existing["oar_listed"] + ", " + listed
        if weight > float(existing.get("severity_weight", 1.0)):
            existing["severity_weight"] = weight
    return list(resolved.values())


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
    #: ``UTCP_INCOMPLETE_OAR_SET`` when P+ was refused for an incomplete OAR set (#20).
    reason: str = ""
    #: Canonical names of the OARs that entered the product.
    scored_OAR_names: list[str] = field(default_factory=list)
    #: Which NTCP model supplied each scored OAR's value, in the same order.
    scored_OAR_models: list[str] = field(default_factory=list)
    #: True when more than one NTCP model contributed to this product. Not an error -- since
    #: v1.5.0 the organs of a site are split between model forms, so a complete P+ usually needs
    #: both -- but it is a property of the number a reader must be able to see.
    mixed_ntcp_models: bool = False


def compute_utcp(
    tcp_result: dict,
    ntcp_results: list[dict],
    site_key: str,
    tcp_model: str = "auto",
    ntcp_model: str = "LKB_loglogit",
    custom_oar_map: list[dict] | None = None,
    allow_partial: bool = False,
) -> UTCPResult:
    """
    Compute UTCP for one patient (Källman 1992: TCP × Π(1−NTCP_k)).

    P+ is a product over *all* the OARs of the site, so dropping one raises the product.
    An incomplete set is therefore refused: UTCP is NaN, ``reason`` is
    ``UTCP_INCOMPLETE_OAR_SET`` and the missing organs are named (defect #20).
    ``allow_partial=True`` computes the partial product anyway, and the row still
    records what was missing.
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

    # The NTCP is read per organ rather than from one fixed column. Since v1.5.0 the organs are
    # split between the log-logistic and probit forms -- an organ whose unsourced log-logistic
    # block was replaced by a published probit fit has NTCP_LKB_loglogit = NaN -- so no single
    # column scores a whole OAR set. At the head-and-neck site four of the eight OARs in the map
    # carry only a probit fit and four only a log-logistic one, and reading either column alone
    # reported the other four as missing and refused P+ outright. ``ntcp_model`` is still honoured
    # as the preference; what changed is that it is a preference and not the only option.
    oar_ntcp: dict[str, float] = {}
    oar_model: dict[str, str] = {}
    for r in ntcp_results:
        oar = str(r.get("structure", ""))
        if not oar:
            continue
        value, model = select_ntcp(r, preferred=ntcp_model)
        if not math.isnan(value):
            oar_ntcp[oar] = value
            oar_model[oar] = model

    oar_list = resolve_oar_map(custom_oar_map or UTCP_OAR_MAP.get(site_norm, []))
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
                    "oar_listed": entry.get("oar_listed", oar_name),
                    "ntcp_model": oar_model.get(oar_name, ""),
                }
            )
        else:
            missing_oars.append(oar_name)
            warns.append(
                f"OAR '{oar_name}' absent from NTCP results for site {site_key}. "
                f"UTCP product computed over {len(oar_list) - len(missing_oars)} OARs only. "
                f"UTCP may be overestimated if this OAR has high NTCP."
            )

    reason = ""
    if not oar_list:
        reason = UTCP_INCOMPLETE_OAR_SET
        warns.append(
            "No UTCP OAR map for site " + str(site_key) + "; P+ is undefined without an OAR set."
        )
    elif missing_oars and not site_has_ntcp_parameters(site_norm):
        # The site has an OAR map but no NTCP parameters at all, so no amount of data would fill
        # the product. That is a different statement from "this patient was missing an organ".
        reason = UTCP_SITE_UNSUPPORTED
        warns.append(
            "Site " + str(site_key) + " has no NTCP parameter block, so none of its OARs can be "
            "scored and P+ is undefined. allow_partial does not apply."
        )
    elif missing_oars:
        reason = UTCP_INCOMPLETE_OAR_SET

    unsupported = reason == UTCP_SITE_UNSUPPORTED
    if math.isnan(tcp_val) or unsupported or (reason and not allow_partial):
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
        reason=reason,
        scored_OAR_names=[d["oar"] for d in scored_oars],
        scored_OAR_models=[d.get("ntcp_model", "") for d in scored_oars],
        mixed_ntcp_models=len({d.get("ntcp_model", "") for d in scored_oars if d.get("ntcp_model")})
        > 1,
    )


def compute_utcp_cohort(
    tcp_results: list[dict],
    ntcp_results_by_patient: dict[str, list[dict]],
    site_key: str,
    ntcp_model: str = "LKB_loglogit",
    allow_partial: bool = False,
) -> list[UTCPResult]:
    """Compute UTCP for each TCP result row (one per target row in tcp_results)."""
    results: list[UTCPResult] = []
    for tcp_r in tcp_results:
        anon_id = str(tcp_r.get("AnonPatientID", ""))
        ntcp_rs = ntcp_results_by_patient.get(anon_id, [])
        results.append(
            compute_utcp(
                tcp_r,
                ntcp_rs,
                site_key,
                ntcp_model=ntcp_model,
                allow_partial=allow_partial,
            )
        )
    return results


def attach_utcp_to_tcp_results(
    tcp_results: list[dict],
    ntcp_results: list[dict],
    site_key: str,
    allow_partial: bool = False,
) -> list[UTCPResult]:
    """Group NTCP by patient, compute UTCP, merge fields into tcp_results.

    Every row gets ``UTCP_OARs_scored`` and ``UTCP_OARs_missing`` (defect #20), including rows
    for which no UTCP could be formed at all: a blank column is indistinguishable from a
    complete OAR set.
    """
    from collections import defaultdict

    ntcp_by_patient: dict[str, list[dict]] = defaultdict(list)
    for r in ntcp_results:
        ntcp_by_patient[str(r.get("AnonPatientID", ""))].append(r)

    utcp_list = compute_utcp_cohort(
        tcp_results, dict(ntcp_by_patient), site_key, allow_partial=allow_partial
    )
    utcp_map = {u.AnonPatientID: u for u in utcp_list}
    n_listed = len(resolve_oar_map(UTCP_OAR_MAP.get(normalize_utcp_site(site_key), [])))
    for r in tcp_results:
        pid = str(r.get("AnonPatientID", ""))
        u = utcp_map.get(pid)
        r["UTCP_OARs_listed"] = n_listed
        if u is None:
            r["UTCP"] = math.nan
            r["UTCP_weighted"] = math.nan
            r["UTCP_NTCP_product"] = math.nan
            r["UTCP_OARs_scored"] = 0
            r["UTCP_OARs_missing"] = n_listed
            r["UTCP_missing_OARs"] = ""
            r["UTCP_TCP_model"] = ""
            r["UTCP_reason"] = UTCP_INCOMPLETE_OAR_SET
            r["UTCP_NTCP_models"] = ""
            r["UTCP_mixed_NTCP_models"] = False
            continue
        r["UTCP"] = u.UTCP
        r["UTCP_weighted"] = u.UTCP_weighted
        r["UTCP_NTCP_product"] = u.NTCP_product
        r["UTCP_OARs_scored"] = u.n_oars_scored
        r["UTCP_OARs_missing"] = u.n_oars_missing
        r["UTCP_missing_OARs"] = ", ".join(u.missing_OAR_names)
        r["UTCP_TCP_model"] = u.TCP_model
        r["UTCP_reason"] = u.reason
        r["UTCP_NTCP_models"] = ", ".join(sorted({m for m in u.scored_OAR_models if m}))
        r["UTCP_mixed_NTCP_models"] = u.mixed_ntcp_models
    return utcp_list
