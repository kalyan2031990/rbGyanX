"""An optional, user-supplied per-patient prescription table (defect #60).

The engine takes one prescription per plan, from the RT Plan's `DoseReferenceSequence`. That is
correct when the plan states the dose it was optimised to. It is wrong whenever an archive writes a
nominal value into every plan while the real per-patient prescription lives somewhere else — and
the prescription is not a cosmetic field: TCP's EQD2 and BED are computed from it directly
(`radiobiology/tcp_calculator.py`), as are the prescription-normalised plan-quality metrics
(V95/V100 coverage, conformity, gradient index). A wrong prescription therefore changes reported
numbers without changing any dose.

This module lets a user state the prescription themselves, per patient, without the engine knowing
anything about their dataset. Nothing here is specific to any archive: it reads a four-column CSV,
validates it, and reports what it matched.

    patient,target_roi,prescription_gy,n_fractions
    PT-0001,PTV70,70,35
    PT-0002,PTVHigh,60,35

* `patient` matches the patient identifier the run uses.
* `target_roi` is the ROI the prescription belongs to. It may be blank, which means "the plan's
  named target"; it is recorded either way so the choice is visible.
* `prescription_gy` and `n_fractions` are the values to use instead of the plan's.

The table is **optional and never inferred**. A patient absent from it keeps the RT Plan value, and
the run manifest records which patients were overridden, so a reader can tell the two apart.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("patient", "target_roi", "prescription_gy", "n_fractions")

# A prescription outside this range is almost certainly a unit error or a typo, and silently
# accepting it would change TCP for that patient without anything saying so.
MIN_PRESCRIPTION_GY = 1.0
MAX_PRESCRIPTION_GY = 120.0
MAX_FRACTIONS = 60


class PrescriptionTableError(ValueError):
    """The table could not be used as given. Raised rather than falling back silently."""


@dataclass(frozen=True)
class PrescriptionEntry:
    patient: str
    target_roi: str
    prescription_gy: float
    n_fractions: int

    @property
    def dose_per_fraction_gy(self) -> float:
        return self.prescription_gy / self.n_fractions if self.n_fractions else math.nan


@dataclass
class PrescriptionTable:
    """Loaded table plus the provenance the run manifest records."""

    path: Path
    sha256: str
    entries: dict[str, PrescriptionEntry] = field(default_factory=dict)
    matched: set[str] = field(default_factory=set)

    def __len__(self) -> int:
        return len(self.entries)

    def lookup(self, patient_id: str) -> PrescriptionEntry | None:
        entry = self.entries.get(str(patient_id).strip())
        if entry is not None:
            self.matched.add(entry.patient)
        return entry

    def manifest_record(self) -> dict:
        """What goes into the run manifest, so a reader can tell overridden from not."""
        unmatched = sorted(set(self.entries) - self.matched)
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "entries": len(self.entries),
            "patients_overridden": sorted(self.matched),
            "n_patients_overridden": len(self.matched),
            "entries_not_matched_to_a_patient": unmatched,
        }


def load_prescription_table(path: str | Path) -> PrescriptionTable:
    """Read and validate the table. Every rejection names the row and the reason."""
    p = Path(path)
    if not p.is_file():
        raise PrescriptionTableError(f"prescription table not found: {p}")

    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()

    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise PrescriptionTableError(f"prescription table is empty: {p}")

    present = {(name or "").strip().lower() for name in reader.fieldnames}
    missing = [c for c in REQUIRED_COLUMNS if c not in present]
    if missing:
        raise PrescriptionTableError(
            f"prescription table {p} is missing column(s) {missing}; "
            f"required: {list(REQUIRED_COLUMNS)}, found: {reader.fieldnames}"
        )

    entries: dict[str, PrescriptionEntry] = {}
    for lineno, row in enumerate(reader, start=2):
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        patient = clean.get("patient", "")
        if not patient:
            raise PrescriptionTableError(f"{p} line {lineno}: empty patient identifier")
        if patient in entries:
            raise PrescriptionTableError(
                f"{p} line {lineno}: patient {patient!r} appears more than once; "
                "a patient must have one prescription in this table"
            )
        try:
            dose = float(clean.get("prescription_gy", ""))
        except ValueError:
            raise PrescriptionTableError(
                f"{p} line {lineno}: prescription_gy "
                f"{clean.get('prescription_gy')!r} is not a number"
            ) from None
        try:
            nfrac = int(float(clean.get("n_fractions", "")))
        except ValueError:
            raise PrescriptionTableError(
                f"{p} line {lineno}: n_fractions {clean.get('n_fractions')!r} is not a number"
            ) from None

        if not math.isfinite(dose) or not (MIN_PRESCRIPTION_GY <= dose <= MAX_PRESCRIPTION_GY):
            raise PrescriptionTableError(
                f"{p} line {lineno}: prescription_gy {dose} is outside "
                f"{MIN_PRESCRIPTION_GY}-{MAX_PRESCRIPTION_GY} Gy. Refusing rather than computing "
                "TCP from a value that is probably a unit error."
            )
        if not 1 <= nfrac <= MAX_FRACTIONS:
            raise PrescriptionTableError(
                f"{p} line {lineno}: n_fractions {nfrac} is outside 1-{MAX_FRACTIONS}"
            )

        entries[patient] = PrescriptionEntry(
            patient=patient,
            target_roi=clean.get("target_roi", ""),
            prescription_gy=dose,
            n_fractions=nfrac,
        )

    if not entries:
        raise PrescriptionTableError(f"{p} has a header but no rows")

    logger.info(
        "prescription table loaded: %d patient(s) from %s (sha256 %s)",
        len(entries),
        p,
        sha[:12],
    )
    return PrescriptionTable(path=p, sha256=sha, entries=entries)


def apply_to_plan_metadata(
    meta: dict,
    patient_id: str,
    table: PrescriptionTable | None,
) -> dict:
    """Return plan metadata with the table's prescription substituted, if it has one.

    The original plan values are kept alongside, under `*_from_rtplan`, so a run never loses what
    the plan actually said. The substitution is logged with both values.
    """
    if table is None or not patient_id:
        return meta
    entry = table.lookup(patient_id)
    if entry is None:
        return meta

    out = dict(meta)
    out["prescription_dose_gy_from_rtplan"] = meta.get("prescription_dose_gy")
    out["n_fractions_from_rtplan"] = meta.get("n_fractions")
    out["prescription_dose_gy"] = entry.prescription_gy
    out["n_fractions"] = entry.n_fractions
    out["dose_per_fraction_gy"] = entry.dose_per_fraction_gy
    out["prescription_source"] = "user_prescription_table"
    out["prescription_target_roi"] = entry.target_roi
    logger.info(
        "prescription overridden for %s: RT Plan %s Gy / %s fx -> table %s Gy / %s fx (%s)",
        patient_id,
        meta.get("prescription_dose_gy"),
        meta.get("n_fractions"),
        entry.prescription_gy,
        entry.n_fractions,
        entry.target_roi or "plan's named target",
    )
    return out
