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
_UNIVERSAL_CANONICALS = frozenset(
    {"SpinalCord", "SpinalCord_PRV", "Heart", "Brainstem", "BrainStem_PRV"}
)

# Defects #9 and #19: a planning-risk volume is the organ grown by a margin, so its DVH is
# colder and larger than the organ's. Scoring it with the organ's published parameters is
# scoring a different structure. ``SpinalCord_05`` and ``BrainStem_03`` carried no alias, fell
# through to fuzzy TG-263 matching and came back as ``SpinalCord`` and ``BrainStem``. Because the
# two then share one ``structure`` label, an organ and its own PRV arrive as indistinguishable
# rows, and which of them was scored changes the number. ``brainstemprv`` was mapped onto the organ
# by the alias table
# outright. A PRV now gets its own canonical key, ``<Organ>_PRV``, with ``is_prv`` True, so it
# is never scored with organ parameters unless the operator maps that key themselves in
# site_params_ntcp_user.yaml.
#
# Matched on the NORMALISED name (separators stripped, lower-cased): an explicit prv/prf marker,
# or a trailing 1-2 digit margin in mm which is how AIRTP and most TPSs spell a PRV expansion.
_PRV_MARKER_RE = re.compile(r"(prv|prf)")
_PRV_MARGIN_RE = re.compile(r"^(?P<base>.*?[a-z])(?P<margin>\d{1,2})(mm)?$")


def _strip_prv_marker(normalised: str) -> str | None:
    """Return the organ part of a PRV name, or None when the name is not a PRV.

    ``spinalcord05`` -> ``spinalcord``; ``brainstemprv`` -> ``brainstem``;
    ``prvcord`` -> ``cord``; ``ptv70`` -> None (a target dose level, not a margin).
    """
    if normalised.startswith(("gtv", "ctv", "ptv", "itv")):
        return None  # a dose level on a target, not a PRV margin
    if _PRV_MARKER_RE.search(normalised):
        base = _PRV_MARKER_RE.sub("", normalised)
        base = re.sub(r"\d{1,2}(mm)?$", "", base)
        return base or None
    margin = _PRV_MARGIN_RE.match(normalised)
    if margin:
        return margin.group("base")
    return None


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


#: A canonical token that commits to a side. Kept narrow on purpose: it matches the trailing
#: ``_L`` / ``_R`` that every lateralised TG-263 key in this project uses.
_LATERAL_TOKEN = re.compile(r"_(L|R)$", re.IGNORECASE)

#: A source name that does assert a side. Deliberately NARROW: a false positive here means the
#: guard believes a side was stated when it was not, and so lets a lateralised mapping through —
#: which is the very thing being prevented. A false negative only means the fuzzy branch declines
#: and the name is left unmapped, visibly, for a curated alias or a human to resolve. So when in
#: doubt this pattern does NOT match. (``SubmandR`` is an example: it is not matched here and is
#: resolved instead by its exact alias in ``config/structure_aliases.py``, which is a human
#: decision rather than an inference.)
_SOURCE_ASSERTS_SIDE = re.compile(
    r"(_(L|R)$|_(left|right)$|\b(left|right)\b|\b(lt|rt)\b|(^|[^a-z])(l|r)$|ips|contra)",
    re.IGNORECASE,
)


def _fuzzy_would_invent_laterality(raw_name: str, token: str) -> bool:
    """True when ``token`` commits to a side that ``raw_name`` does not.

    Guards defect #21 by construction rather than by persuasion: no model output, alias entry or
    configuration can route an unlateralised source name to a lateralised canonical through the
    fuzzy branch. An exact alias or TG-263 match is unaffected — a curated alias asserting the
    side is a human decision, and ``FemHead_R`` -> ``FemoralHead_R`` must keep working.
    """
    if not _LATERAL_TOKEN.search(token):
        return False
    return not _SOURCE_ASSERTS_SIDE.search(raw_name.strip())


def normalize_to_tg263(raw_name: str) -> dict:
    """
    Map a vendor or archive structure name to an AAPM TG-263 token.

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
                if _fuzzy_would_invent_laterality(raw_name, token):
                    # The source name asserts no side and this token does. difflib ties the
                    # "_L" and "_R" keys exactly and breaks the tie lexicographically, so "_R"
                    # always won and the side was chosen by the alphabet, not by anatomy
                    # (defect #21). A side-less name is common in real exports, so the effect is
                    # not a corner case.
                    # Refusing here is also what makes the documented bilateral-name policy in
                    # config/structure_aliases.py actually hold: the alias table honoured it and
                    # this branch bypassed it.
                    logger.warning(
                        "TG-263 fuzzy map REFUSED: %r -> %s would assert a laterality the "
                        "source name does not carry; left unmapped",
                        raw_name,
                        token,
                    )
                    break
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
            "is_prv": False,
        }

    normalised = normalise_name(raw_name)

    prv_base = _strip_prv_marker(normalised)
    if prv_base is not None:
        organ = _resolve_organ(prv_base)
        if organ is not None:
            return {
                "canonical": organ + "_PRV",
                "category": "OAR",
                "site_hint": _site_hint(organ),
                "confidence": "MEDIUM",
                "is_prv": True,
                "prv_of": organ,
                "tg263": normalize_to_tg263(organ),
            }

    match = _lookup_alias(normalised)
    if match:
        tg = normalize_to_tg263(match)
        canonical = tg["tg263"] if tg["mapped"] else match
        return {
            "canonical": canonical,
            "category": _category(match),
            "site_hint": _site_hint(match),
            "confidence": "MEDIUM",
            "is_prv": False,
            "tg263": tg,
        }

    tg = normalize_to_tg263(raw_name)
    if tg["mapped"]:
        return {
            "canonical": tg["tg263"],
            "category": "OAR",
            "site_hint": _site_hint(tg["tg263"]),
            "confidence": "MEDIUM" if tg["method"] == "exact" else "LOW",
            "is_prv": False,
            "tg263": tg,
        }

    return {
        "canonical": raw_name.upper(),
        "category": "UNKNOWN",
        "site_hint": "",
        "confidence": "LOW",
        "is_prv": False,
        "tg263": tg,
    }


def _resolve_organ(normalised_base: str) -> str | None:
    """Canonical OAR key for the organ part of a PRV name, or None if it is not an organ."""
    match = _lookup_alias(normalised_base)
    if match is not None:
        if _category(match) != "OAR":
            return None
        tg = normalize_to_tg263(match)
        return str(tg["tg263"]) if tg["mapped"] else match
    tg = normalize_to_tg263(normalised_base)
    if tg["mapped"]:
        return str(tg["tg263"])
    return None


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
