"""Load multi-site NTCP organ parameters from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT = Path(__file__).resolve().parent / "site_params_ntcp_default.yaml"
_USER = Path(__file__).resolve().parent / "site_params_ntcp_user.yaml"


#: The three model blocks an organ may carry, as spelled in the YAML.
MODEL_KEYS = ("LKB_loglogit", "LKB_probit", "RS")

#: The provenance fields every model block must declare.
PROVENANCE_REQUIRED = (
    "source",
    "table_page",
    "endpoint",
    "fractionation_basis",
    "structure_definition",
    "illustrative",
)

#: Reason written on a row whose parameters have no published source and whose run is BASIC.
ILLUSTRATIVE_PARAMS_IN_BASIC_MODE = "ILLUSTRATIVE_PARAMS_IN_BASIC_MODE"


def _unsourced_provenance(note: str) -> dict:
    return {
        "source": "unsourced",
        "table_page": "",
        "endpoint": "not stated",
        "fractionation_basis": "not stated",
        "structure_definition": "not stated",
        "as_printed": {},
        "conversion": "",
        "illustrative": True,
        "note": note,
    }


@dataclass
class OrganNTCPParams:
    canonical: str
    geud_a: float = 3.0
    alpha_beta_gy: float = 3.0
    lkb_loglogit: dict[str, float] | None = None
    lkb_probit: dict[str, float] | None = None
    rs: dict[str, float] | None = None
    #: Per-model provenance, keyed by the model names in ``MODEL_KEYS``. A model with no entry is
    #: treated as unsourced, so nothing is published as sourced by omission.
    provenance: dict[str, dict] = field(default_factory=dict)
    #: True when NO model of this organ has a published source. BASIC mode refuses those.
    illustrative: bool = True

    def model_provenance(self, model: str) -> dict:
        """Provenance for one model, defaulting to unsourced rather than to nothing."""
        entry = self.provenance.get(model)
        if isinstance(entry, dict):
            return entry
        return _unsourced_provenance("no provenance block for this model in the parameter YAML")

    def model_is_illustrative(self, model: str) -> bool:
        return bool(self.model_provenance(model).get("illustrative", True))

    @property
    def source(self) -> str:
        """The citation of the first sourced model, or ``"unsourced"``."""
        for model in MODEL_KEYS:
            entry = self.provenance.get(model)
            if isinstance(entry, dict) and not entry.get("illustrative", True):
                return str(entry.get("source", "unsourced"))
        return "unsourced"


@dataclass
class SiteNTCPParams:
    site_key: str
    organs: dict[str, OrganNTCPParams] = field(default_factory=dict)
    params_source: str = "default"


def _parse_organ(name: str, raw: dict[str, Any]) -> OrganNTCPParams:
    provenance = {
        model: block
        for model, block in (raw.get("provenance") or {}).items()
        if isinstance(block, dict)
    }
    present = [m for m in MODEL_KEYS if raw.get(m)]
    declared = raw.get("illustrative")
    if declared is None:
        # No declaration means no source was asserted, so the safe reading is illustrative.
        illustrative = all(
            provenance.get(m, {}).get("illustrative", True) for m in present
        ) if present else True
    else:
        illustrative = bool(declared)
    return OrganNTCPParams(
        canonical=name,
        geud_a=float(raw.get("geud_a", 3.0)),
        alpha_beta_gy=float(raw.get("alpha_beta_gy", 3.0)),
        lkb_loglogit=raw.get("LKB_loglogit"),
        lkb_probit=raw.get("LKB_probit"),
        rs=raw.get("RS"),
        provenance=provenance,
        illustrative=illustrative,
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
            base = dict(base_organs.get(organ) or {})
            combined = {**base, **params}
            # A user who supplies their own numbers must not inherit the shipped provenance: it
            # describes a different value. Any model the user overrides without also giving its
            # provenance becomes unsourced, so BASIC mode refuses it rather than vouching for it.
            overridden = [m for m in MODEL_KEYS if m in params]
            if overridden:
                prov = dict(combined.get("provenance") or {})
                user_prov = (params.get("provenance") or {})
                for model in overridden:
                    if model not in user_prov:
                        prov[model] = _unsourced_provenance(
                            f"overridden in {user_path.name} without a provenance block"
                        )
                combined["provenance"] = prov
                if "illustrative" not in params and any(
                    prov.get(m, {}).get("illustrative", True) for m in overridden
                ):
                    combined["illustrative"] = True
            base_organs[organ] = combined

    organs_raw = merged.get("organs") or {}
    organs = {k: _parse_organ(k, v) for k, v in organs_raw.items()}
    source = "user+default" if user_path.is_file() else "default"
    return SiteNTCPParams(site_key=site_key, organs=organs, params_source=source)


def allowed_oar_names(site_key: str, user_config: Path | None = None) -> frozenset[str]:
    return frozenset(load_site_ntcp_params(site_key, user_config).organs.keys())


#: Real contour names used to check organ-key reachability (defect #22). Absent from a wheel,
#: which is why the corpus check is opt-in and the import-time check does not need it.
CONTOUR_NAME_CORPUS = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "contour_name_corpus.txt"
)


def default_organ_keys() -> dict[str, set[str]]:
    """Organ keys per site in the shipped default NTCP YAML."""
    data = _load_yaml(_DEFAULT)
    return {site: set(block.get("organs") or {}) for site, block in data.items()}


def read_contour_name_corpus(corpus_path: Path | None = None) -> list[str]:
    """Load the contour-name corpus. Blank lines and ``#`` comments are ignored."""
    path = corpus_path or CONTOUR_NAME_CORPUS
    if not path.is_file():
        return []
    names = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return names


def organ_key_corpus_reachability(corpus_path: Path | None = None) -> dict[str, set[str]]:
    """Which real contour names reach each organ key, through ``canon_target``.

    A planning-risk volume never counts: it has its own canonical key and must not stand in for
    the organ (defects #9 and #19).
    """
    from dicom_io.structure_mapper import canon_target

    keys = {k for organs in default_organ_keys().values() for k in organs}
    reach: dict[str, set[str]] = {k: set() for k in keys}
    for name in read_contour_name_corpus(corpus_path):
        mapped = canon_target(name)
        if mapped["category"] != "OAR" or mapped.get("is_prv"):
            continue
        if mapped["canonical"] in reach:
            reach[mapped["canonical"]].add(name)
    return reach


def _validate_default_organ_keys_reachable() -> None:
    """Every organ key in the shipped default NTCP YAML must resolve, through canon_target(),
    to itself as a recognised OAR, and must not be mistaken for a PRV.

    A key that doesn't is silently unreachable: get_oar_structures() (dicom_io/structure_mapper.py)
    drops the corresponding ROI with a bare `continue` before DVH extraction, with no warning and
    no reason code -- a real ROI's NTCP would simply never compute, indistinguishable from that
    patient never having had the structure at all. This found seven such keys (HN/BRAIN_GBM/
    BRAIN_METS "Brainstem", BREAST "Lung_Ipsi"/"Lung_Contra", PROSTATE "FemoralHead_L"/"_R") that
    had shipped silently broken. Runs once at import time -- not per site_key, so it can't stay
    hidden just because a given run never happens to exercise the affected site.

    Defect #22: on its own this is a self-consistency check, not a reachability check. It compares
    the alias table with itself, so it passes however far the table has drifted from the names a
    treatment planning system actually writes -- "PharynxConst", a common export spelling for the
    pharyngeal constrictors, went unmapped while this check was green. Reachability against real
    names lives in ``organ_key_corpus_reachability()`` and is asserted by
    engine/tests/test_v150_organ_key_reachability.py, because the corpus is part of the test
    fixtures and is not shipped in the wheel.
    """
    from dicom_io.structure_mapper import canon_target  # local import: avoids a module-load-order
    # dependency between config.site_ntcp_params and dicom_io at package-init time.

    unreachable = []
    for site, organs in default_organ_keys().items():
        for organ_key in sorted(organs):
            mapped = canon_target(organ_key)
            if (
                mapped["canonical"] != organ_key
                or mapped["category"] != "OAR"
                or mapped.get("is_prv")
            ):
                unreachable.append(
                    f"{site}/{organ_key} -> canon_target gives canonical={mapped['canonical']!r} "
                    f"category={mapped['category']!r} is_prv={mapped.get('is_prv')!r} "
                    f"(needs canonical=={organ_key!r}, category=='OAR', is_prv False)"
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
