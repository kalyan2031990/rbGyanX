"""
NTCP applicability & parameter-definition guard (Phase 3.3).

Two semantic guarantees for NTCP, kept OUT of the numeric kernels (this module decides *whether* a model
may be applied, never *what value* it returns):

  1. A structure classified as a TARGET (or SUPPORT/UNKNOWN) must never receive an NTCP. The pipeline
     already enforces this structurally (NTCP runs only over ``get_oar_structures``); this module makes
     the rule explicit and testable.
  2. An NTCP model's published parameters assume a specific structure *definition* (e.g. single parotid
     gland, not a merged bilateral "Parotids"). When the definition of the actual ROI cannot be
     established, or contradicts the parameters' assumption, we FLAG it and record the assumed
     definition rather than silently trusting the number (constraint C1 / audit item S2).

Nothing here changes a radiobiological calculation; it emits an applicability verdict + reason code that
the cohort runner (Phase 5) records in the QA log and — in strict mode — uses to withhold NTCP.
"""

from __future__ import annotations

# Paired / bilateral organs whose single-structure NTCP parameters (QUANTEC/HyTEC-era) are defined for
# ONE gland. Applying them to a merged bilateral contour is a definition mismatch.
_SINGLE_GLAND_STEMS = {
    "parotid",
    "submandibular",
    "lung",
    "kidney",
    "cochlea",
    "opticnerve",
    "hippocampus",
    "lacrimal",
    "temporallobe",
}
# Tokens in a raw ROI name that indicate a MERGED / bilateral / combined structure.
_MERGED_TOKENS = (
    "bilat",
    "combined",
    "total",
    "both",
    "whole",
    "pair",
    "glands",
    "parotids",
    "submandibulars",
    "lungs",
    "_lr",
    "_rl",
    "l+r",
    "lr_",
)
_SIDE_TOKENS = ("_l", "_r", "-l", "-r", " l", " r", "left", "right", "lt", "rt")


def ntcp_allowed(category: str) -> tuple[bool, str]:
    """A TARGET/SUPPORT/UNKNOWN structure must never receive NTCP."""
    if category == "OAR":
        return True, ""
    if category in ("TARGET",):
        return False, "NTCP_ON_TARGET_BLOCKED"
    if category in ("SUPPORT",):
        return False, "NTCP_ON_SUPPORT_BLOCKED"
    return False, "NTCP_ON_UNKNOWN_BLOCKED"


def _stem(canonical: str) -> str:
    return canonical.lower().replace("_l", "").replace("_r", "").replace("_", "")


def classify_definition(canonical: str, raw_name: str) -> str:
    """single_gland | merged_bilateral | unspecified — inferred from canonical laterality and raw name."""
    stem = _stem(canonical)
    if stem not in _SINGLE_GLAND_STEMS:
        return "unspecified"  # not a paired organ we track a definition assumption for
    raw = raw_name.lower()
    canon = canonical.lower()
    raw_has_side = any(t in raw for t in _SIDE_TOKENS)
    is_merged = any(t in raw for t in _MERGED_TOKENS)
    # A merged/bilateral RAW name wins even if the canonical was mis-assigned a side — that IS the hazard.
    if is_merged and not raw_has_side:
        return "merged_bilateral"
    # Laterality counts as established only when it is present in the ROI's OWN name. A side that
    # appears only in the canonical was *inferred* by the alias mapper (a side-less "Parotid" resolves
    # to Parotid_R purely by lookup order), which is not evidence about the contour — so it stays
    # unspecified and the caller flags NTCP_DEFINITION_UNVERIFIED rather than assuming a single gland.
    if raw_has_side:
        return "single_gland"
    _ = canon  # canonical laterality deliberately NOT treated as evidence
    return "unspecified"  # paired organ but side not established → cannot confirm single-gland


def evaluate_ntcp_applicability(
    canonical: str,
    category: str,
    raw_name: str,
    param_assumed_definition: str = "single_gland",
) -> dict:
    """Full verdict for applying an NTCP model to one structure.

    Returns:
      allowed: may NTCP be applied at all (False for TARGET/SUPPORT/UNKNOWN)
      structure_definition / assumed_definition: what the ROI is vs what the params assume
      definition_ok: True / False / None(=unverifiable)
      reason_codes: machine-readable flags for the QA log
    """
    allowed, block_code = ntcp_allowed(category)
    reason_codes: list[str] = []
    if not allowed:
        return {
            "allowed": False,
            "structure_definition": "n/a",
            "assumed_definition": param_assumed_definition,
            "definition_ok": False,
            "reason_codes": [block_code],
        }

    definition = classify_definition(canonical, raw_name)
    if definition == "unspecified" and _stem(canonical) not in _SINGLE_GLAND_STEMS:
        # organ with no tracked definition assumption — nothing to verify
        definition_ok: bool | None = True
    elif definition == "unspecified":
        definition_ok = None
        reason_codes.append("NTCP_DEFINITION_UNVERIFIED")
    elif definition == param_assumed_definition:
        definition_ok = True
    else:
        definition_ok = False
        reason_codes.append("NTCP_DEFINITION_MISMATCH")

    return {
        "allowed": True,
        "structure_definition": definition,
        "assumed_definition": param_assumed_definition,
        "definition_ok": definition_ok,
        "reason_codes": reason_codes,
    }
