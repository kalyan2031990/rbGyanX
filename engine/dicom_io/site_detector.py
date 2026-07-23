"""Auto-detect treatment site (anatomy / histology) — not delivery technique."""

from __future__ import annotations

from dicom_io.structure_mapper import canon_target

# --- Anatomical site keywords (plan label / header) ---
_BRAIN_ANATOMY = frozenset(
    {
        "BRAIN",
        "GBM",
        "GLIOMA",
        "GLIOBLAST",
        "WBRT",
        "WHOLEBRAIN",
        "MENINGIOMA",
        "PITUITARY",
        "HYPOPH",
        "CRANI",
        "CNS",
    }
)
_BRAIN_METS_HINTS = frozenset(
    {"METS", "METASTAS", "METASTASIS", "METASTATIC", "BRAINMET", "BMETS"}
)
_BRAIN_GBM_HINTS = frozenset(
    {"GBM", "GLIOMA", "GLIOBLAST", "GLIOBLASTOMA", "ASTROCYTOMA"}
)
_HN_KEYWORDS = frozenset(
    {
        "HN",
        "HEAD",
        "NECK",
        "OROPHARYNX",
        "NASOPHARYNX",
        "HYPOPHARYNX",
        "LARYNX",
        "TONGUE",
        "ORAL",
        "PAROTID",
        "TONSIL",
        "NPC",
        "ORL",
        "HNSCC",
    }
)
_LUNG_KEYWORDS = frozenset(
    {"LUNG", "NSCLC", "SCLC", "BRONCH", "PULMONARY", "THORAX", "MEDIASTIN"}
)
_BREAST_KEYWORDS = frozenset(
    {"BREAST", "MAMMA", "CHESTWALL", "MASTECTOMY", "LUMECTOMY", "PMRT"}
)
_PROSTATE_KEYWORDS = frozenset(
    {"PROSTATE", "PROSTATA", "PCA", "PROSTATECTOMY", "SBRT_PROSTATE", "PROST", "CAP"}
)
_PELVIS_KEYWORDS = frozenset(
    {
        "PELVIS",
        "CERVIX",
        "UTERUS",
        "ENDOMETRIUM",
        "RECTUM",
        "BLADDER",
        "GYNECOL",
        "GYNAECOL",
        "VULVA",
        "VAGINA",
        "COLO",
        "ANAL",
    }
)
_LIVER_KEYWORDS = frozenset({"LIVER", "FOIE", "HCC", "HEPATO", "HEPATIC", "SBRT_LIVER"})


def _label_contains_keyword(plan_label: str, keywords: frozenset[str]) -> set[str]:
    upper = plan_label.upper()
    return {kw for kw in keywords if kw in upper}


def _match_anatomical_site(plan_label: str) -> tuple[str | None, list[str]]:
    """Infer treated anatomical site from text — not IMRT/VMAT/SRS/SBRT."""
    evidence: list[str] = []
    brain = _label_contains_keyword(plan_label, _BRAIN_ANATOMY | _BRAIN_METS_HINTS)
    if brain:
        evidence.append(f"Brain-related keyword(s): {brain}")
        return "BRAIN", evidence
    hn = _label_contains_keyword(plan_label, _HN_KEYWORDS)
    if hn:
        evidence.append(f"H&N keyword(s): {hn}")
        return "HN", evidence
    lung = _label_contains_keyword(plan_label, _LUNG_KEYWORDS)
    if lung:
        evidence.append(f"Lung/thorax keyword(s): {lung}")
        return "LUNG", evidence
    breast = _label_contains_keyword(plan_label, _BREAST_KEYWORDS)
    if breast:
        evidence.append(f"Breast keyword(s): {breast}")
        return "BREAST", evidence
    prostate = _label_contains_keyword(plan_label, _PROSTATE_KEYWORDS)
    if prostate:
        evidence.append(f"Prostate keyword(s): {prostate}")
        return "PROSTATE", evidence
    pelvis = _label_contains_keyword(plan_label, _PELVIS_KEYWORDS)
    if pelvis:
        evidence.append(f"Pelvic keyword(s): {pelvis}")
        return "PELVIS", evidence
    liver = _label_contains_keyword(plan_label, _LIVER_KEYWORDS)
    if liver:
        evidence.append(f"Liver keyword(s): {liver}")
        return "LIVER", evidence
    return None, evidence


def _brain_histology(plan_label: str) -> tuple[str, list[str]]:
    """
    Brain histology from disease keywords only (GBM vs metastases).

    Does not use fractionation or SRS/SBRT technique.
    """
    upper = plan_label.upper()
    evidence: list[str] = []
    mets_hits = _label_contains_keyword(upper, _BRAIN_METS_HINTS)
    gbm_hits = _label_contains_keyword(upper, _BRAIN_GBM_HINTS)
    if mets_hits and not gbm_hits:
        evidence.append(f"Metastasis keyword(s): {mets_hits}")
        return "METS", evidence
    if gbm_hits and not mets_hits:
        evidence.append(f"Primary brain tumour keyword(s): {gbm_hits}")
        return "GBM", evidence
    if mets_hits and gbm_hits:
        evidence.append(f"Conflicting keywords METS={mets_hits} GBM={gbm_hits}; default GBM")
        return "GBM", evidence
    evidence.append("No brain histology keyword; default GBM (override with --site BRAIN_METS)")
    return "GBM", evidence


def _fractionation_regime(plan: dict) -> tuple[str, list[str]]:
    """
    Describe fractionation for reporting only — does not select anatomical site.

    IMRT/VMAT/SRS/SBRT are not inferred here.
    """
    n_frac = int(plan.get("n_fractions") or 0)
    dpf = float(plan.get("dose_per_fraction_gy") or 0.0)
    evidence: list[str] = []

    if n_frac <= 0:
        return "", evidence

    if n_frac == 1:
        evidence.append(f"Single fraction ({dpf:.1f} Gy)")
        return "SINGLE_FRACTION", evidence
    if n_frac <= 8 and dpf >= 4.0:
        evidence.append(f"Hypofractionated: {n_frac} fx, {dpf:.1f} Gy/fx")
        return "HYPOFRACTIONATED", evidence
    if n_frac >= 25 and 1.8 <= dpf <= 2.2:
        evidence.append(f"Conventional: {n_frac} fx, {dpf:.1f} Gy/fx")
        return "CONVENTIONAL", evidence
    evidence.append(f"Other fractionation: {n_frac} fx, {dpf:.1f} Gy/fx")
    return "OTHER", evidence


def _oar_site(structure_list: list[dict]) -> tuple[str | None, list[str]]:
    canonicals = {s.get("canonical", "") for s in structure_list}
    evidence: list[str] = []

    hn_markers = {"Parotid_L", "Parotid_R", "Mandible", "Pharynx", "OralCavity"}
    if canonicals & hn_markers:
        evidence.append(f"H&N OAR structures: {canonicals & hn_markers}")
        return "HN", evidence

    lung_markers = {"Lung_R", "Lung_L", "LungTotal"}
    if lung_markers.issubset(canonicals):
        evidence.append("Bilateral lung OAR structures present")
        return "LUNG", evidence

    if canonicals & {"Breast_Contra", "LAD"}:
        evidence.append(f"Breast OAR structures: {canonicals & {'Breast_Contra', 'LAD'}}")
        return "BREAST", evidence

    brain_markers = {
        "Brain",
        "Hippocampus_L",
        "Hippocampus_R",
        "OpticNerve_L",
        "OpticNerve_R",
        "OpticChiasm",
    }
    if canonicals & brain_markers:
        evidence.append(f"Brain OAR structures: {canonicals & brain_markers}")
        return "BRAIN", evidence

    prostate_markers = {"Rectum", "Bladder", "FemoralHead_L", "FemoralHead_R", "Urethra"}
    if len(canonicals & prostate_markers) >= 2:
        evidence.append(f"Pelvic OAR structures: {canonicals & prostate_markers}")
        return "PROSTATE", evidence

    if canonicals & {"Liver"}:
        evidence.append("Liver OAR structure present")
        return "LIVER", evidence

    return None, evidence


def params_site_key(site: str, histology: str = "") -> str:
    """
    Map detected anatomy (+ brain histology) to YAML parameter keys.

    YAML keys reflect tumour type, not delivery technique.
    """
    s = str(site or "").upper().strip()
    h = str(histology or "").upper().strip()

    if s in ("BRAIN_GBM", "GBM", "GLIOMA"):
        return "BRAIN_GBM"
    if s in ("BRAIN_METS", "METS"):
        return "BRAIN_METS"
    if s == "BRAIN":
        if h in ("METS", "METASTASIS", "METASTASES", "METASTATIC"):
            return "BRAIN_METS"
        return "BRAIN_GBM"
    if s in ("LUNG", "LUNG_SBRT", "NSCLC"):
        return "LUNG"
    if s == "HN":
        return "HN"
    if s == "BREAST":
        return "BREAST"
    if s in ("PROSTATE", "CAP"):
        return "PROSTATE"
    if s in ("PELVIS", "CERVIX", "ENDOMETRIUM"):
        return "PELVIS"
    if s in ("LIVER", "HCC"):
        return "LIVER"
    if s == "UNKNOWN":
        return "UNKNOWN"
    return _SITE_KEY_MAP_FALLBACK.get(s, s)


_SITE_KEY_MAP_FALLBACK: dict[str, str] = {
    "BRAIN_GBM": "BRAIN_GBM",
    "BRAIN_METS": "BRAIN_METS",
    "LUNG_SBRT": "LUNG",
}


def detect_site(plan_metadata: dict, structure_list: list[dict]) -> dict:
    """
    Detect anatomical site and (for brain) histology.

    Returns:
        site: BRAIN | LUNG | HN | BREAST | UNKNOWN
        histology: GBM | METS | "" (brain only)
        subtype: fractionation_regime (informational; legacy field name)
        fractionation: same as subtype
    """
    plan_label = str(plan_metadata.get("plan_label", ""))
    evidence: list[str] = []
    site: str | None = None
    histology = ""
    confidence = "LOW"
    step_used = 0

    label_site, label_evidence = _match_anatomical_site(plan_label)
    if label_site:
        site = label_site
        evidence.extend(label_evidence)
        confidence = "HIGH"
        step_used = 1

    oar_site, oar_evidence = _oar_site(structure_list)
    if oar_site and (step_used == 0 or confidence == "MEDIUM"):
        site = oar_site
        evidence.extend(oar_evidence)
        confidence = "HIGH"
        step_used = 2

    fractionation, frac_evidence = _fractionation_regime(plan_metadata)
    evidence.extend(frac_evidence)

    if site == "BRAIN" or (
        site is None and _label_contains_keyword(plan_label, _BRAIN_METS_HINTS)
    ):
        if site is None:
            site = "BRAIN"
            evidence.append("Brain inferred from metastasis keywords in label")
        hist, hist_ev = _brain_histology(plan_label)
        histology = hist
        evidence.extend(hist_ev)

    if site is None:
        rx = float(plan_metadata.get("prescription_dose_gy") or 0)
        n_frac = int(plan_metadata.get("n_fractions") or 0)
        dpf = float(plan_metadata.get("dose_per_fraction_gy") or 0)
        label_upper = plan_label.upper()
        has_target = any(
            tok in label_upper
            for tok in ("PTV", "CTV", "GTV", "ITV")
        ) or any(
            s.get("canonical") in ("PTV", "CTV", "GTV", "ITV")
            for s in structure_list
        )
        if has_target and 54 <= rx <= 80 and 25 <= n_frac <= 42 and 1.8 <= dpf <= 2.2:
            evidence.append(
                f"Curative-range plan ({rx:.0f} Gy, {n_frac}×{dpf:.1f} Gy) detected but "
                "anatomical site is ambiguous (HN/prostate/cervix/rectum all possible). "
                "Pass --site to override."
            )
            confidence = "LOW"

    if site is None:
        site = "UNKNOWN"

    return {
        "site": site,
        "histology": histology,
        "subtype": fractionation,
        "fractionation": fractionation,
        "confidence": confidence,
        "evidence": evidence,
    }


def detect_site_from_text(
    plan_metadata: dict,
    structure_name: str,
    header_text: str = "",
) -> dict:
    """Detect site from TPS DVH text export."""
    pseudo: list[dict] = []
    mapped = canon_target(structure_name)
    canonical = mapped.get("canonical", "")
    if canonical in ("GTV", "CTV", "PTV", "ITV", "BOOST"):
        pseudo.append({"canonical": canonical})

    plan_label = str(plan_metadata.get("plan_label", structure_name))
    if header_text:
        plan_label = f"{plan_label} {header_text[:2000]}"
    meta = dict(plan_metadata)
    meta["plan_label"] = plan_label
    return detect_site(meta, pseudo)


def resolve_pipeline_site(
    site_override: str | None,
    detection: dict,
) -> tuple[str, dict]:
    """Choose YAML parameter key from auto-detection or --site override."""
    if site_override:
        key = params_site_key(site_override, detection.get("histology", ""))
        info = {
            "site": site_override.upper(),
            "histology": detection.get("histology", ""),
            "subtype": detection.get("fractionation", ""),
            "fractionation": detection.get("fractionation", ""),
            "confidence": "USER",
            "evidence": [f"User override --site {site_override}"],
            "params_site_key": key,
        }
        return key, info

    site = detection.get("site", "UNKNOWN")
    if site == "UNKNOWN":
        import logging

        logging.getLogger(__name__).warning(
            "Site auto-detection returned UNKNOWN. Provide --site (BRAIN, BRAIN_GBM, "
            "BRAIN_METS, HN, LUNG, BREAST, PROSTATE) or the engine will abort."
        )
        raise ValueError(
            "Could not auto-detect tumor site from DICOM/DVH text. "
            "Pass --site (BRAIN, BRAIN_GBM, BRAIN_METS, HN, LUNG, BREAST, PROSTATE)."
        )
    key = params_site_key(site, detection.get("histology", ""))
    info = {**detection, "params_site_key": key}
    return key, info
