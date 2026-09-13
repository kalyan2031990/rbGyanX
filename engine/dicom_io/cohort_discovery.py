"""
Deterministic cohort discovery and modality selection for arbitrary DICOM-RT trees (Phase 2).

Additive to ``DicomPlanReader`` (which is left unchanged for backward compatibility). This module
traverses an arbitrary folder of arbitrary DICOM, groups instances by **PatientID + FrameOfReferenceUID**
(not folder name), and applies a **documented, deterministic** selection rule when a patient has multiple
RTPLAN / RTDOSE / RTSTRUCT. It never raises on one bad patient: every degradation is recorded as a
machine-readable reason code and the traversal continues (constraints C4, C5).

Selection rules (deterministic; ties broken by SOPInstanceUID string order):
  RTPLAN   : APPROVED before UNAPPROVED, then latest (RTPlanDate/Time, then InstanceCreationDate/Time).
  RTSTRUCT : the structure set referenced by the chosen plan; else the latest RTSTRUCT sharing the plan's
             Frame Of Reference; else the latest RTSTRUCT overall.
  RTDOSE   : DoseSummationType == PLAN and referencing the chosen plan; else a PLAN-summation dose sharing
             the Frame Of Reference; else the latest RTDOSE.
  CT       : counted (presence only) for reduced-mode signalling; never required.

Reason codes (machine-readable, stable): MISSING_RTPLAN, MISSING_RTDOSE, MISSING_RTSTRUCT, MISSING_CT,
MULTIPLE_RTPLAN, MULTIPLE_RTDOSE, MULTIPLE_RTSTRUCT, DOSE_NOT_PLAN_LINKED, STRUCT_NOT_PLAN_LINKED,
FRAME_OF_REFERENCE_MISMATCH, UNREADABLE_FILES, NO_PATIENT_ID.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pydicom

logger = logging.getLogger(__name__)

_RT_MODALITIES = {"RTPLAN", "RTDOSE", "RTSTRUCT"}


@dataclass
class _Instance:
    """One readable DICOM instance, header-only."""

    path: Path
    modality: str
    patient_id: str
    for_uid: str
    sop_uid: str
    ds: pydicom.Dataset  # header (stop_before_pixels)


@dataclass
class PatientManifest:
    """Deterministic per-patient selection result. `patient_key` is the raw PatientID held internally;
    callers must pseudonymise it before writing any output (constraint C2)."""

    patient_key: str
    frame_of_reference: str = ""
    rtplan_path: Path | None = None
    rtdose_path: Path | None = None
    rtstruct_path: Path | None = None
    ct_instance_count: int = 0
    degraded_mode: str = "FULL"  # FULL | NO_DOSE | NO_STRUCT | NO_PLAN | INSUFFICIENT
    reason_codes: list[str] = field(default_factory=list)
    selection_notes: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)

    def add_reason(self, code: str) -> None:
        if code not in self.reason_codes:
            self.reason_codes.append(code)


def _s(ds, tag: str, default: str = "") -> str:
    return str(getattr(ds, tag, default) or default).strip()


def _plan_datetime_key(ds) -> str:
    """Sortable string; larger = later. Missing dates sort earliest (empty string)."""
    d = _s(ds, "RTPlanDate") or _s(ds, "InstanceCreationDate") or _s(ds, "StudyDate")
    t = _s(ds, "RTPlanTime") or _s(ds, "InstanceCreationTime") or "000000"
    return f"{d}{t}"


def _approved_key(ds) -> int:
    return 1 if _s(ds, "ApprovalStatus").upper() == "APPROVED" else 0


def _referenced_sop(seq_owner, seq_name: str) -> set[str]:
    out: set[str] = set()
    for item in getattr(seq_owner, seq_name, []) or []:
        uid = getattr(item, "ReferencedSOPInstanceUID", None)
        if uid:
            out.add(str(uid))
    return out


def _iter_instances(root: Path) -> tuple[list[_Instance], int]:
    """Read headers of every DICOM under root. Returns (instances, unreadable_count). Never raises."""
    instances: list[_Instance] = []
    unreadable = 0
    for path in sorted(root.rglob("*")):  # sorted → deterministic traversal
        if not path.is_file():
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        except Exception:
            continue  # not a DICOM file (or corrupt header) — silently skip non-DICOM
        modality = _s(ds, "Modality").upper()
        if not modality:
            continue
        if modality not in _RT_MODALITIES and modality != "CT":
            continue
        sop = _s(ds, "SOPInstanceUID") or str(path)
        try:
            instances.append(
                _Instance(
                    path=path,
                    modality=modality,
                    patient_id=_s(ds, "PatientID"),
                    for_uid=_s(ds, "FrameOfReferenceUID"),
                    sop_uid=sop,
                    ds=ds,
                )
            )
        except Exception:  # a header so malformed even attribute access fails
            unreadable += 1
    return instances, unreadable


def _struct_for_uid(ds) -> str:
    """FrameOfReferenceUID of an RTSTRUCT (via ReferencedFrameOfReferenceSequence)."""
    for item in getattr(ds, "ReferencedFrameOfReferenceSequence", []) or []:
        uid = getattr(item, "FrameOfReferenceUID", None)
        if uid:
            return str(uid)
    return _s(ds, "FrameOfReferenceUID")


def _select_for_patient(patient_key: str, insts: list[_Instance], unreadable: int) -> PatientManifest:
    plans = sorted(
        [i for i in insts if i.modality == "RTPLAN"],
        key=lambda i: (_approved_key(i.ds), _plan_datetime_key(i.ds), i.sop_uid),
        reverse=True,
    )
    doses = sorted([i for i in insts if i.modality == "RTDOSE"], key=lambda i: i.sop_uid, reverse=True)
    structs = sorted([i for i in insts if i.modality == "RTSTRUCT"], key=lambda i: i.sop_uid, reverse=True)
    cts = [i for i in insts if i.modality == "CT"]

    m = PatientManifest(patient_key=patient_key)
    m.counts = {"RTPLAN": len(plans), "RTDOSE": len(doses), "RTSTRUCT": len(structs), "CT": len(cts)}
    m.ct_instance_count = len(cts)
    if not patient_key:
        m.add_reason("NO_PATIENT_ID")
    if unreadable:
        m.add_reason("UNREADABLE_FILES")

    # --- RTPLAN ---
    plan = plans[0] if plans else None
    if plan is None:
        m.add_reason("MISSING_RTPLAN")
    else:
        m.frame_of_reference = plan.for_uid
        if len(plans) > 1:
            m.add_reason("MULTIPLE_RTPLAN")
            m.selection_notes["RTPLAN"] = (
                f"{len(plans)} plans; chose {'APPROVED ' if _approved_key(plan.ds) else ''}latest "
                f"(sop …{plan.sop_uid[-8:]})"
            )
        m.rtplan_path = plan.path

    plan_sop = plan.sop_uid if plan else None
    struct_refs = _referenced_sop(plan.ds, "ReferencedStructureSetSequence") if plan else set()

    # --- RTSTRUCT: referenced by plan > shares FoR > latest ---
    if structs:
        chosen = next((s for s in structs if s.sop_uid in struct_refs), None)
        if chosen is None and m.frame_of_reference:
            chosen = next((s for s in structs if _struct_for_uid(s.ds) == m.frame_of_reference), None)
            if chosen is not None and plan is not None:
                m.add_reason("STRUCT_NOT_PLAN_LINKED")
        if chosen is None:
            chosen = structs[0]
            if plan is not None:
                m.add_reason("STRUCT_NOT_PLAN_LINKED")
        m.rtstruct_path = chosen.path
        if not m.frame_of_reference:
            m.frame_of_reference = _struct_for_uid(chosen.ds)
        if len(structs) > 1:
            m.add_reason("MULTIPLE_RTSTRUCT")
    else:
        m.add_reason("MISSING_RTSTRUCT")

    # --- RTDOSE: PLAN-summation referencing plan > PLAN-summation same FoR > latest ---
    if doses:
        def refs_plan(d):
            return plan_sop is not None and plan_sop in _referenced_sop(d.ds, "ReferencedRTPlanSequence")

        def is_plan_sum(d):
            return _s(d.ds, "DoseSummationType").upper() in ("PLAN", "")

        chosen = next((d for d in doses if refs_plan(d) and is_plan_sum(d)), None)
        if chosen is None:
            chosen = next((d for d in doses if is_plan_sum(d) and d.for_uid == m.frame_of_reference), None)
            if chosen is not None and plan is not None:
                m.add_reason("DOSE_NOT_PLAN_LINKED")
        if chosen is None:
            chosen = doses[0]
            if plan is not None:
                m.add_reason("DOSE_NOT_PLAN_LINKED")
        m.rtdose_path = chosen.path
        if m.frame_of_reference and chosen.for_uid and chosen.for_uid != m.frame_of_reference:
            m.add_reason("FRAME_OF_REFERENCE_MISMATCH")
        if len(doses) > 1:
            m.add_reason("MULTIPLE_RTDOSE")
    else:
        m.add_reason("MISSING_RTDOSE")

    if not cts:
        m.add_reason("MISSING_CT")  # not required — TCIA-lung style; DVH still computable from dose+struct

    # --- degraded mode (what outputs are still possible) ---
    if m.rtdose_path and m.rtstruct_path:
        m.degraded_mode = "FULL" if m.rtplan_path else "NO_PLAN"
    elif m.rtstruct_path and not m.rtdose_path:
        m.degraded_mode = "NO_DOSE"      # structures only; no DVH
    elif m.rtdose_path and not m.rtstruct_path:
        m.degraded_mode = "NO_STRUCT"    # dose grid only; no per-structure DVH
    else:
        m.degraded_mode = "INSUFFICIENT"
    return m


def discover_cohort(root: str | Path) -> list[PatientManifest]:
    """Discover and deterministically select modalities for every patient under ``root``.

    Groups by PatientID (empty IDs grouped by FrameOfReferenceUID as a fallback). Returns one
    ``PatientManifest`` per patient, sorted by patient_key, each with reason codes. Never raises.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Cohort root not found: {root}")  # a missing ROOT is a caller error

    instances, unreadable = _iter_instances(root)

    # group by PatientID; fall back to FrameOfReferenceUID when PatientID is empty
    groups: dict[str, list[_Instance]] = {}
    for inst in instances:
        key = inst.patient_id or f"__NOID__{inst.for_uid or 'unknown'}"
        groups.setdefault(key, []).append(inst)

    manifests = [
        _select_for_patient("" if k.startswith("__NOID__") else k, insts, unreadable)
        for k, insts in groups.items()
    ]
    manifests.sort(key=lambda m: (m.patient_key or "~", m.frame_of_reference))
    return manifests
