"""Structure name normalisation and canonical mapping."""

import logging
import re
from difflib import get_close_matches

from config.structure_aliases import STRUCTURE_ALIASES
from config.tg263_aliases import TG263_ALIASES

logger = logging.getLogger(__name__)

TARGET_CANONICALS = frozenset({"GTV", "CTV", "PTV", "ITV", "BOOST"})
SUPPORT_CANONICALS = frozenset({"BODY", "COUCH", "BOLUS", "PROSTHESIS"})

_ALIAS_SEARCH_ORDER = [
    "ITV",
    "BOOST",
    "GTV",
    "CTV",
    "PTV",
] + [
    c
    for c in STRUCTURE_ALIASES
    if c not in {"ITV", "BOOST", "GTV", "CTV", "PTV"}
]

_HN_CANONICALS = frozenset(
    {
        "Parotid_L",
        "Parotid_R",
        "Submandibular_L",
        "Submandibular_R",
        "Mandible",
        "Larynx",
        "OralCavity",
        "Pharynx",
    }
)
_LUNG_CANONICALS = frozenset({"Lung_R", "Lung_L", "LungTotal", "Esophagus", "Trachea"})
_BREAST_CANONICALS = frozenset({"Breast_Contra", "LAD", "Lung_Ipsi"})
_BRAIN_CANONICALS = frozenset(
    {
        "Brain",
        "Hippocampus_L",
        "Hippocampus_R",
        "OpticNerve_L",
        "OpticNerve_R",
        "OpticChiasm",
        "Pituitary",
        "Cochlea_L",
        "Cochlea_R",
    }
)
_UNIVERSAL_CANONICALS = frozenset({"SpinalCord", "PRV_Cord", "Heart", "Brainstem"})

def normalise_name(raw: str) -> str:
    """Strip separators and lowercase."""
    return re.sub(r"[\s_\-/]+", "", raw.strip()).lower()


def _site_hint(canonical: str) -> str:
    if canonical in _HN_CANONICALS:
        return "HN"
    if canonical in _LUNG_CANONICALS:
        return "LUNG"
    if canonical in _BREAST_CANONICALS:
        return "BREAST"
    if canonical in _BRAIN_CANONICALS:
        return "BRAIN"
    if canonical in _UNIVERSAL_CANONICALS:
        return "UNIVERSAL"
    return ""


def _category(canonical: str) -> str:
    if canonical in TARGET_CANONICALS:
        return "TARGET"
    if canonical in SUPPORT_CANONICALS:
        return "SUPPORT"
    return "OAR"


def normalize_to_tg263(raw_name: str) -> dict:
    """
    Map vendor/TCIA structure name to AAPM TG-263 token.

    Unmapped names are preserved (uppercase) and flagged — never silently dropped.
    Idempotent when input is already a TG-263 token.
    """
    normalised = normalise_name(raw_name)
    for token, aliases in TG263_ALIASES.items():
        if normalised == normalise_name(token) or normalised in aliases:
            return {
                "tg263": token,
                "raw": raw_name,
                "mapped": True,
                "method": "exact",
            }
    keys = [normalise_name(k) for k in TG263_ALIASES]
    close = get_close_matches(normalised, keys, n=1, cutoff=0.88)
    if close:
        for token in TG263_ALIASES:
            if normalise_name(token) == close[0]:
                logger.info("TG-263 fuzzy map: %r -> %s", raw_name, token)
                return {
                    "tg263": token,
                    "raw": raw_name,
                    "mapped": True,
                    "method": "fuzzy",
                }
    token = raw_name.strip()
    logger.warning("TG-263 unmapped structure: %r (passthrough)", raw_name)
    return {
        "tg263": token,
        "raw": raw_name,
        "mapped": False,
        "method": "passthrough",
    }


def _lookup_alias(normalised: str) -> str | None:
    for canonical in _ALIAS_SEARCH_ORDER:
        aliases = STRUCTURE_ALIASES.get(canonical, [])
        if normalised in aliases or normalised == canonical.lower():
            return canonical
    # Dose-embedded names (e.g. PTV 46GY, GTV PRIMARY) after exact alias pass
    for prefix, canonical in (("gtv", "GTV"), ("ctv", "CTV"), ("ptv", "PTV")):
        if normalised.startswith(prefix):
            return canonical
    return None


def canon_target(raw_name: str, roi_interpreted_type: str | None = None) -> dict:
    """Map a structure name to canonical form with category and confidence."""
    if roi_interpreted_type in {"GTV", "CTV", "PTV"}:
        canonical = roi_interpreted_type
        return {
            "canonical": canonical,
            "category": _category(canonical),
            "site_hint": _site_hint(canonical),
            "confidence": "HIGH",
        }

    normalised = normalise_name(raw_name)
    match = _lookup_alias(normalised)
    if match:
        tg = normalize_to_tg263(match)
        canonical = tg["tg263"] if tg["mapped"] else match
        return {
            "canonical": canonical,
            "category": _category(match),
            "site_hint": _site_hint(match),
            "confidence": "MEDIUM",
            "tg263": tg,
        }

    tg = normalize_to_tg263(raw_name)
    if tg["mapped"]:
        return {
            "canonical": tg["tg263"],
            "category": "OAR",
            "site_hint": _site_hint(tg["tg263"]),
            "confidence": "MEDIUM" if tg["method"] == "exact" else "LOW",
            "tg263": tg,
        }

    return {
        "canonical": raw_name.upper(),
        "category": "UNKNOWN",
        "site_hint": "",
        "confidence": "LOW",
        "tg263": tg,
    }


def get_target_structures(rt_struct_ds, plan_metadata: dict) -> list[dict]:
    """Return target structures (GTV, CTV, PTV, ITV, BOOST) from RT Structure Set."""
    del plan_metadata  # reserved for future plan-driven filtering

    roi_by_number: dict[int, dict] = {}
    if hasattr(rt_struct_ds, "StructureSetROISequence"):
        for roi in rt_struct_ds.StructureSetROISequence:
            roi_by_number[int(roi.ROINumber)] = {
                "name": str(roi.ROIName),
                "type": str(getattr(roi, "RTROIInterpretedType", "") or ""),
            }

    targets: list[dict] = []
    for roi_number, info in sorted(roi_by_number.items()):
        mapped = canon_target(info["name"], info["type"] or None)
        if mapped["canonical"] not in TARGET_CANONICALS:
            continue
        targets.append(
            {
                "roi_number": roi_number,
                "raw_name": info["name"],
                "canonical": mapped["canonical"],
                "roi_type": info["type"],
                "confidence": mapped["confidence"],
            }
        )

    order = {"GTV": 0, "CTV": 1, "PTV": 2, "ITV": 3, "BOOST": 4}
    targets.sort(key=lambda item: (order.get(item["canonical"], 99), item["roi_number"]))
    return targets


def get_oar_structures(
    rt_struct_ds,
    allowed_canonicals: frozenset[str] | None = None,
) -> list[dict]:
    """Return OAR structures from RT Structure Set, optionally filtered by name."""
    roi_by_number: dict[int, dict] = {}
    if hasattr(rt_struct_ds, "StructureSetROISequence"):
        for roi in rt_struct_ds.StructureSetROISequence:
            roi_by_number[int(roi.ROINumber)] = {
                "name": str(roi.ROIName),
                "type": str(getattr(roi, "RTROIInterpretedType", "") or ""),
            }

    oars: list[dict] = []
    for roi_number, info in sorted(roi_by_number.items()):
        mapped = canon_target(info["name"], info["type"] or None)
        if mapped["category"] != "OAR":
            continue
        canonical = mapped["canonical"]
        if allowed_canonicals is not None and canonical not in allowed_canonicals:
            continue
        oars.append(
            {
                "roi_number": roi_number,
                "raw_name": info["name"],
                "canonical": canonical,
                "roi_type": info["type"],
                "confidence": mapped["confidence"],
            }
        )
    oars.sort(key=lambda item: item["canonical"])
    return oars
