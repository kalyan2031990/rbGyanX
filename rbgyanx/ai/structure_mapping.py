"""LLM-assisted structure-name resolution: propose-only, code-validated, human-approved.

The problem no alias table solves: every department names structures differently. Shipping a
bigger alias list is a treadmill, and refusing everything unrecognised is the control that gets
switched off. That is a language task, not a numeric one -- and it is the only place in this
project where a language model earns its keep.

What this module does, and what it refuses to do
------------------------------------------------
1. Run the **deterministic** mapper. Anything it resolves at high confidence is left alone and is
   never shown to a model.
2. Collect the residue: names landing ``UNKNOWN``, or resolving at ``LOW`` confidence.
3. Ask a model for a canonical key per residual name, with the allowed keys and their clinical
   definitions in the prompt.
4. **Validate the answer in code.** A model is not trusted to obey instructions:
     * the returned key must be in the allowed set, or the row is rejected;
     * **if the source name asserts no laterality, a lateralised key is rejected regardless of
       what the model says** -- defect #21 is impossible by construction, not by persuasion;
     * a name the model calls a planning aid is still checked against the aid patterns.
5. Write a **proposal file**. Nothing is applied. Every row carries the model name, the prompt
   version, the model's own reasoning and its confidence.
6. A human approves. Approved rows are written to the **site alias pack**, the mechanism that
   already exists (``RBGYANX_STRUCTURE_LABELS`` + ``rbgyanx/ai/reference_packs``).

From then on the mapping is deterministic, cached, versioned and diffable, and **the model is not
in the run path and not a runtime dependency**. Re-running with the approved pack on a machine
with no provider and no network gives identical numbers. That property is what makes this
publishable: the evidence does not depend on a model being available, or deterministic.

The model never computes a dose, a DVH, an NTCP or a TCP. It proposes a *label*.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROMPT_VERSION = "structure-mapping/1"

#: A canonical key that commits to an anatomical side.
_LATERAL_KEY = re.compile(r"_(L|R)$", re.IGNORECASE)

#: A source name that genuinely asserts a side. Mirrors the engine's own guard in
#: ``dicom_io/structure_mapper._SOURCE_ASSERTS_SIDE``; a test asserts the two agree.
_SOURCE_ASSERTS_SIDE = re.compile(
    r"(_(L|R)$|_(left|right)$|\b(left|right)\b|\b(lt|rt)\b|(^|[^a-z])(l|r)$|ips|contra)",
    re.IGNORECASE,
)

#: Optimisation helpers and margin expansions, which are not the organ. ``-PTV`` means the organ
#: MINUS the PTV in the AIRTP naming scheme, so its dose is biased low by construction.
_PLANNING_AID = re.compile(
    r"(-\s*PTV$|_PTV$|OPT$|^Ring|Ring[A-Z]|PRV|_\d{1,2}$|\+\s*\d+\s*mm|_exp$|opt[iy]mi)",
    re.IGNORECASE,
)


class ProposalRefused(RuntimeError):
    """A proposal failed a code-side guard. Never downgraded to a warning."""


@dataclass
class Residual:
    """One structure name the deterministic mapper could not resolve confidently."""

    raw_name: str
    site: str
    deterministic_canonical: str
    deterministic_category: str
    deterministic_confidence: str
    n_patients: int = 1


@dataclass
class Proposal:
    """A model's suggestion, plus the verdict code reached about it. Never applied here."""

    raw_name: str
    site: str
    proposed_canonical: str
    model_says_bilateral: bool | None
    model_says_asserts_laterality: bool | None
    model_says_planning_aid: bool | None
    model_confidence: str
    model_reasoning: str
    model_name: str
    prompt_version: str = PROMPT_VERSION
    accepted: bool = False
    rejected_reason: str = ""
    deterministic_confidence: str = ""
    n_patients: int = 1
    guards_applied: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- 1-2. the residue

def collect_residue(raw_names: Iterable[str], site: str, canon_target: Callable) -> list[Residual]:
    """Names the deterministic mapper leaves UNKNOWN or resolves only at LOW confidence.

    ``canon_target`` is injected rather than imported so this module does not drag the engine in,
    and so a test can supply a stub.
    """
    out: list[Residual] = []
    seen: set[str] = set()
    for name in raw_names:
        if name in seen:
            continue
        seen.add(name)
        r = canon_target(name, None)
        cat = str(r.get("category", ""))
        conf = str(r.get("confidence", ""))
        if cat == "UNKNOWN" or conf.upper() == "LOW":
            out.append(Residual(raw_name=name, site=site,
                                deterministic_canonical=str(r.get("canonical", "")),
                                deterministic_category=cat,
                                deterministic_confidence=conf))
    return out


# --------------------------------------------------------------------- 3. the prompt

def build_prompt(residue: list[Residual], site: str,
                 allowed: dict[str, str]) -> list[dict[str, str]]:
    """Messages for the model. ``allowed`` maps canonical key -> clinical definition/endpoint.

    The prompt states the rules, but nothing depends on the model following them: every rule is
    re-checked in :func:`validate_proposal`.
    """
    keys = "\n".join(f"  {k}: {v}" for k, v in sorted(allowed.items()))
    names = "\n".join(f"  {r.raw_name!r}" for r in residue)
    system = (
        "You map radiotherapy structure-set names to canonical organ keys. You never compute a "
        "dose, a DVH or a complication probability; you propose a label, which a medical "
        "physicist will approve or reject.\n"
        "Rules:\n"
        "1. If the source name does not state a side, do NOT return a lateralised key. A "
        "bilateral or side-less contour is not a left or right organ.\n"
        "2. A name meaning the organ MINUS a target volume, or a margin expansion, is a planning "
        "aid, not the organ. Say so instead of guessing an organ.\n"
        "3. If you are not confident, say so. An unmapped structure is a safe outcome; a wrong "
        "label is not.\n"
        "Reply with one JSON object per input name and no other text."
    )
    user = (
        f"Site: {site}\n\nAllowed canonical keys and what each one means:\n{keys}\n\n"
        f"Structure names to resolve:\n{names}\n\n"
        'For each, return: {"raw_name": ..., "canonical": ... or null, "bilateral": true/false, '
        '"asserts_laterality": true/false, "planning_aid": true/false, '
        '"confidence": "HIGH"|"MEDIUM"|"LOW", "reasoning": "one line"}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# --------------------------------------------------------------------- 4. the code-side guards

def source_asserts_laterality(raw_name: str) -> bool:
    return bool(_SOURCE_ASSERTS_SIDE.search(raw_name.strip()))


def looks_like_planning_aid(raw_name: str) -> bool:
    return bool(_PLANNING_AID.search(raw_name.strip()))


def validate_proposal(residual: Residual, answer: dict, allowed: Iterable[str],
                      model_name: str) -> Proposal:
    """Turn one model answer into a Proposal, applying every guard in code.

    The model's own claims are recorded but never relied upon. A rejected row is returned, not
    raised, so one bad answer cannot abort a batch -- but it is never silently dropped either.
    """
    allowed = set(allowed)
    proposed = answer.get("canonical")
    proposed = "" if proposed is None else str(proposed).strip()
    p = Proposal(
        raw_name=residual.raw_name, site=residual.site, proposed_canonical=proposed,
        model_says_bilateral=answer.get("bilateral"),
        model_says_asserts_laterality=answer.get("asserts_laterality"),
        model_says_planning_aid=answer.get("planning_aid"),
        model_confidence=str(answer.get("confidence", "")).upper(),
        model_reasoning=str(answer.get("reasoning", ""))[:500],
        model_name=model_name,
        deterministic_confidence=residual.deterministic_confidence,
        n_patients=residual.n_patients,
    )

    if not proposed:
        p.rejected_reason = "model returned no canonical key"
        p.guards_applied.append("empty")
        return p

    p.guards_applied.append("allowed-set")
    if proposed not in allowed:
        p.rejected_reason = (
            f"{proposed!r} is not in the allowed canonical set for site {residual.site}"
        )
        return p

    # THE non-negotiable one. Defect #21 by construction.
    p.guards_applied.append("laterality")
    if _LATERAL_KEY.search(proposed) and not source_asserts_laterality(residual.raw_name):
        p.rejected_reason = (
            f"{proposed!r} asserts a side that the source name {residual.raw_name!r} does not "
            f"carry; a lateralised key is refused here whatever the model returns"
        )
        return p

    p.guards_applied.append("planning-aid")
    if looks_like_planning_aid(residual.raw_name):
        p.rejected_reason = (
            f"{residual.raw_name!r} matches the planning-aid patterns (organ minus a target, or a "
            f"margin expansion); it is not the organ regardless of the model's answer"
        )
        return p

    p.guards_applied.append("confidence")
    if p.model_confidence not in ("HIGH", "MEDIUM"):
        p.rejected_reason = f"model confidence {p.model_confidence!r} is below the threshold"
        return p

    p.accepted = True
    return p


# --------------------------------------------------------------------- 5. the proposal file

def write_proposals(proposals: list[Proposal], path: Path, *, site: str,
                    provider: str, base_url: str) -> Path:
    """Write the proposal file. NOTHING is applied to any alias pack by this function."""
    payload = {
        "kind": "rbgyanx-structure-mapping-proposal",
        "prompt_version": PROMPT_VERSION,
        "site": site,
        "provider": provider,
        "provider_base_url": base_url,
        "status": "AWAITING_PHYSICIST_APPROVAL",
        "note": ("Nothing here is in effect. Approve rows with approve_to_alias_pack(); until "
                 "then the deterministic refusal stands."),
        "n_proposed": len(proposals),
        "n_accepted_by_guards": sum(1 for p in proposals if p.accepted),
        "n_rejected_by_guards": sum(1 for p in proposals if not p.accepted),
        "proposals": [asdict(p) for p in proposals],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


# --------------------------------------------------------------------- 6. approval -> alias pack

def approve_to_alias_pack(proposal_path: Path, out_path: Path,
                          approved_raw_names: Iterable[str], *,
                          pack_id: str = "site_structure_aliases",
                          pack_version: str = "1") -> dict:
    """Write the approved rows into a site alias pack, re-checking every guard on the way out.

    The pack reuses the format the scrubber already loads (``structure_labels``) and adds
    ``structure_aliases`` for the mapping, so one file serves both and the existing
    ``RBGYANX_STRUCTURE_LABELS`` discovery mechanism is not duplicated.
    """
    data = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
    approved = set(approved_raw_names)
    aliases: dict[str, list[str]] = {}
    labels: list[str] = []
    refused: list[dict] = []
    for row in data.get("proposals", []):
        if row["raw_name"] not in approved:
            continue
        if not row.get("accepted"):
            refused.append({"raw_name": row["raw_name"],
                            "reason": "approved by a human but REJECTED by a code guard: "
                                      + row.get("rejected_reason", "")})
            continue
        # re-check the laterality guard at write time: approval cannot override it
        if _LATERAL_KEY.search(row["proposed_canonical"]) and \
                not source_asserts_laterality(row["raw_name"]):
            refused.append({"raw_name": row["raw_name"],
                            "reason": "laterality guard re-applied at write time"})
            continue
        aliases.setdefault(row["proposed_canonical"], []).append(row["raw_name"])
        labels.append(row["raw_name"])

    pack = {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "site": data.get("site", ""),
        "source": "LLM proposal, physicist-approved, guards re-applied at write time",
        "prompt_version": data.get("prompt_version", ""),
        "provider": data.get("provider", ""),
        "structure_aliases": {k: sorted(v) for k, v in sorted(aliases.items())},
        "structure_labels": sorted(set(labels)),
        "refused_at_write_time": refused,
        "note": ("Deterministic from here on: re-running with this pack needs no model, no "
                 "network and no provider, and gives identical numbers."),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")
    return pack


def load_alias_pack(path: Path) -> dict[str, str]:
    """raw name -> canonical, from an approved pack. No model, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for canonical, names in (data.get("structure_aliases") or {}).items():
        for n in names:
            out[str(n)] = str(canonical)
    return out
