"""pydicom-based RT Plan / Dose / Structure Set loader."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset

logger = logging.getLogger(__name__)

_SETUP_BEAM_KEYWORDS = (
    "cbct",
    "kv",
    "setup",
    "portal",
    "scout",
    "drr",
    "verification",
)

_TPS_VENDOR_MAP = {
    "VARIAN MEDICAL SYSTEMS": "Varian",
    "VARIAN": "Varian",
    "ELEKTA": "Elekta",
    "RAYSEARCH LABORATORIES": "RayStation",
    "PHILIPS": "Pinnacle",
    "ADAC": "Pinnacle",
    "ACCURAY": "TomoTherapy_or_CyberKnife",
    "BRAINLAB": "Brainlab",
}


def _anonymise_patient_name(name: str) -> str:
    """Return initials only, e.g. 'PARUL SINGHA' -> 'P.S.'."""
    if not name:
        return ""
    parts = re.split(r"[\^,\s]+", str(name).strip())
    initials = []
    for part in parts:
        cleaned = re.sub(r"[^A-Za-z]", "", part)
        if cleaned:
            initials.append(cleaned[0].upper())
    return ".".join(initials) + ("." if initials else "")


def _detect_tps_vendor(manufacturer: str) -> str:
    key = str(manufacturer or "").strip().upper()
    for prefix, vendor in _TPS_VENDOR_MAP.items():
        if key == prefix or key.startswith(prefix):
            return vendor
    return "Unknown"


def _is_setup_beam(beam: Dataset) -> bool:
    beam_name = str(getattr(beam, "BeamName", "") or "").lower()
    if any(keyword in beam_name for keyword in _SETUP_BEAM_KEYWORDS):
        return True
    delivery_type = str(getattr(beam, "TreatmentDeliveryType", "") or "").upper()
    return delivery_type == "TREATMENT_CONTINUATION"


def _treatment_beams(rt_plan_ds: Dataset) -> list[Dataset]:
    beams = list(getattr(rt_plan_ds, "BeamSequence", []) or [])
    return [beam for beam in beams if not _is_setup_beam(beam)]


def _beam_mu(beam: Dataset) -> float:
    mu = 0.0
    for cp in getattr(beam, "ControlPointSequence", []) or []:
        for ref in getattr(cp, "ReferencedBeamSequence", []) or []:
            if hasattr(ref, "BeamMeterset"):
                mu = max(mu, float(ref.BeamMeterset))
        if hasattr(cp, "CumulativeMetersetWeight"):
            mu = max(mu, float(cp.CumulativeMetersetWeight))
    if hasattr(beam, "BeamMeterset"):
        mu = max(mu, float(beam.BeamMeterset))
    return mu


def _is_vmat_beam(beam: Dataset) -> bool:
    cps = list(getattr(beam, "ControlPointSequence", []) or [])
    if len(cps) <= 50:
        return False
    angles = [
        float(getattr(cp, "GantryAngle", 0.0))
        for cp in cps
        if hasattr(cp, "GantryAngle")
    ]
    if len(angles) < 2:
        return False
    return (max(angles) - min(angles)) > 180.0


def _radiation_type(beam: Dataset) -> str:
    rtype = str(getattr(beam, "RadiationType", "") or "").upper()
    if rtype in {"PHOTON", "PROTON", "ELECTRON"}:
        return rtype
    return "Unknown"


def _classify_beam_type(
    n_fractions: int, dose_per_fraction: float, treatment_beams: list[Dataset]
) -> str:
    if n_fractions == 1 and dose_per_fraction >= 8:
        return "SRS"
    if n_fractions <= 8 and dose_per_fraction >= 4:
        return "SBRT"
    if any(_is_vmat_beam(beam) for beam in treatment_beams):
        return "VMAT"
    if any(str(getattr(b, "BeamType", "")).upper() == "DYNAMIC" for b in treatment_beams):
        return "IMRT"
    return "3DCRT"


def _prescription_dose_gy(rt_plan_ds: Dataset) -> float | None:
    sequence = getattr(rt_plan_ds, "DoseReferenceSequence", None)
    if not sequence:
        logger.warning("DoseReferenceSequence missing in RT Plan")
        return None

    entries = list(sequence)
    target_entries = [
        ref
        for ref in entries
        if str(getattr(ref, "DoseReferenceType", "")).upper() == "TARGET"
    ]
    candidates = target_entries or entries

    for ref in candidates:
        if hasattr(ref, "TargetPrescriptionDose"):
            return float(ref.TargetPrescriptionDose)
        if hasattr(ref, "DeliveryMaximumDose"):
            return float(ref.DeliveryMaximumDose)

    logger.warning("No TargetPrescriptionDose or DeliveryMaximumDose found")
    return None


class DicomPlanReader:
    """Load RT DICOM data and extract plan metadata."""

    def load_patient_dicom(
        self,
        folder_path: str | Path,
        patient_id: str | None = None,
    ) -> dict:
        folder = Path(folder_path)
        if not folder.is_dir():
            raise FileNotFoundError(f"Patient folder not found: {folder}")

        rt_plan: Dataset | None = None
        rt_dose: Dataset | None = None
        rt_struct: Dataset | None = None
        pid_filter = str(patient_id).strip() if patient_id else None

        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            try:
                ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
            except Exception:
                continue
            if pid_filter:
                file_pid = str(getattr(ds, "PatientID", "") or "").strip()
                if file_pid and file_pid != pid_filter:
                    continue
            modality = str(getattr(ds, "Modality", "")).upper()
            if modality == "RTPLAN" and rt_plan is None:
                rt_plan = ds
            elif modality == "RTDOSE" and rt_dose is None:
                rt_dose = ds
            elif modality == "RTSTRUCT" and rt_struct is None:
                rt_struct = ds

        missing = [
            name
            for name, ds in (
                ("RT Plan", rt_plan),
                ("RT Dose", rt_dose),
                ("RT Structure Set", rt_struct),
            )
            if ds is None
        ]
        if missing:
            raise FileNotFoundError(
                f"Missing required DICOM modalities in {folder}: {', '.join(missing)}"
            )

        plan_id = str(getattr(rt_plan, "PatientID", ""))
        dose_id = str(getattr(rt_dose, "PatientID", ""))
        if plan_id and dose_id and plan_id != dose_id:
            raise ValueError(
                f"PatientID mismatch between RT Plan ({plan_id}) and RT Dose ({dose_id})"
            )

        manufacturer = str(getattr(rt_plan, "Manufacturer", "") or "")
        software = str(getattr(rt_plan, "SoftwareVersions", "") or "")
        if software and isinstance(software, (list, tuple)):
            software = ";".join(str(v) for v in software)

        return {
            "rt_plan": rt_plan,
            "rt_dose": rt_dose,
            "rt_struct": rt_struct,
            "patient_id": plan_id,
            "patient_name": _anonymise_patient_name(
                str(getattr(rt_plan, "PatientName", "") or "")
            ),
            "patient_sex": str(getattr(rt_plan, "PatientSex", "") or "O")[:1] or "O",
            "patient_dob": str(getattr(rt_plan, "PatientBirthDate", "") or ""),
            "study_date": str(getattr(rt_plan, "StudyDate", "") or ""),
            "institution": str(getattr(rt_plan, "InstitutionName", "") or ""),
            "tps_vendor": _detect_tps_vendor(manufacturer),
            "tps_version": software,
            "folder_path": str(folder.resolve()),
        }

    def load_cohort(self, parent_folder: str | Path) -> list[dict]:
        parent = Path(parent_folder)
        patients: list[dict] = []
        for subfolder in sorted(parent.iterdir()):
            if not subfolder.is_dir():
                continue
            try:
                patients.append(self.load_patient_dicom(subfolder))
            except Exception as exc:
                logger.warning("Skipping %s: %s", subfolder.name, exc)
        patients.sort(key=lambda item: item.get("patient_id", ""))
        return patients

    def extract_plan_metadata(self, rt_plan_ds) -> dict:
        prescription = _prescription_dose_gy(rt_plan_ds)
        fraction_groups = list(getattr(rt_plan_ds, "FractionGroupSequence", []) or [])
        n_fractions = 1
        if fraction_groups:
            n_fractions = int(getattr(fraction_groups[0], "NumberOfFractionsPlanned", 1))

        dose_per_fraction = (
            prescription / n_fractions if prescription and n_fractions else 0.0
        )
        treatment_beams = _treatment_beams(rt_plan_ds)
        beam_type = _classify_beam_type(n_fractions, dose_per_fraction, treatment_beams)

        nominal_energy = 0.0
        if treatment_beams:
            for cp in getattr(treatment_beams[0], "ControlPointSequence", []) or []:
                if hasattr(cp, "NominalBeamEnergy"):
                    nominal_energy = float(cp.NominalBeamEnergy)
                    break

        total_mu = sum(_beam_mu(beam) for beam in treatment_beams)
        radiation = _radiation_type(treatment_beams[0]) if treatment_beams else "Unknown"

        return {
            "plan_label": str(getattr(rt_plan_ds, "RTPlanLabel", "") or ""),
            "prescription_dose_gy": prescription,
            "n_fractions": n_fractions,
            "dose_per_fraction_gy": dose_per_fraction,
            "n_beams": len(treatment_beams),
            "beam_type": beam_type,
            "radiation_type": radiation,
            "nominal_energy_mv": nominal_energy,
            "total_mu": total_mu,
            "is_stereotactic": beam_type in {"SBRT", "SRS"},
            "lq_model_caution": dose_per_fraction > 10.0,
        }
