"""
Analytic synthetic DICOM-RT factory (RTSTRUCT + RTDOSE + RTPLAN).

Builds a minimal, self-consistent RT triple that ``dicompyler-core`` can consume,
with a **uniform** dose grid so DVH metrics have an exact closed form:

    every voxel inside any in-grid ROI receives exactly ``dose_gy`` →
    Dmin = Dmean = Dmax = D95 = D2 = dose_gy   (independent of rasterisation).

This is the CI-safe stand-in for real patient DICOM (which is never committed).
A second, out-of-grid ROI exercises the NaN-not-zero degenerate contract.

References for the DICOM attributes required by dvhcalc:
- RTDOSE: ImagePositionPatient/Orientation, PixelSpacing, GridFrameOffsetVector,
  DoseGridScaling, uint16 PixelData, shared FrameOfReferenceUID.
- RTSTRUCT: StructureSetROISequence + ROIContourSequence (CLOSED_PLANAR contours
  whose z-planes coincide with dose planes) + RTROIObservationsSequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import (
    CTImageStorage,
    ExplicitVRLittleEndian,
    RTDoseStorage,
    RTPlanStorage,
    RTStructureSetStorage,
    generate_uid,
)


@dataclass
class SyntheticROI:
    name: str
    roi_type: str  # PTV / ORGAN
    x0_mm: float
    x1_mm: float
    y0_mm: float
    y1_mm: float
    z0_mm: float
    z1_mm: float


def _file_meta(sop_class_uid: str, sop_instance_uid: str) -> FileMetaDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class_uid
    meta.MediaStorageSOPInstanceUID = sop_instance_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    return meta


def _base(ds: Dataset, patient_id: str, modality: str, frame_uid: str) -> None:
    ds.PatientName = f"SYN^{patient_id}"
    ds.PatientID = patient_id
    ds.PatientSex = "O"
    ds.PatientBirthDate = "20000101"
    ds.StudyInstanceUID = f"1.2.826.0.1.{abs(hash(patient_id)) % (10**12)}"
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyDate = "20240101"
    ds.Modality = modality
    ds.FrameOfReferenceUID = frame_uid
    ds.InstitutionName = "SYNTH"


def build_rt_triple(
    patient_id: str = "SYN-001",
    dose_gy: float = 70.0,
    n_fractions: int = 35,
    rois: list[SyntheticROI] | None = None,
    *,
    columns: int = 40,
    rows: int = 40,
    n_frames: int = 20,
    spacing_mm: float = 3.0,
) -> tuple[Dataset, Dataset, Dataset]:
    """Return (rt_struct_ds, rt_dose_ds, rt_plan_ds) sharing a frame of reference."""
    frame_uid = generate_uid()
    origin = (0.0, 0.0, 0.0)

    if rois is None:
        # In-grid PTV + in-grid dysphagia OAR (uniform dose) + out-of-grid OAR (NaN contract).
        rois = [
            SyntheticROI("PTV70", "PTV", 15.0, 45.0, 15.0, 45.0, 0.0, 27.0),
            SyntheticROI("Larynx", "ORGAN", 18.0, 36.0, 18.0, 36.0, 6.0, 21.0),
            SyntheticROI("OutOfGrid", "ORGAN", 500.0, 530.0, 500.0, 530.0, 0.0, 9.0),
        ]

    rt_dose = _build_rtdose(
        patient_id, frame_uid, origin, dose_gy, columns, rows, n_frames, spacing_mm
    )
    rt_struct = _build_rtstruct(patient_id, frame_uid, rois)
    rt_plan = _build_rtplan(patient_id, frame_uid, dose_gy, n_fractions)
    return rt_struct, rt_dose, rt_plan


def _build_rtdose(
    patient_id: str,
    frame_uid: str,
    origin: tuple[float, float, float],
    dose_gy: float,
    columns: int,
    rows: int,
    n_frames: int,
    spacing_mm: float,
) -> Dataset:
    sop_uid = generate_uid()
    ds = FileDataset(None, {}, file_meta=_file_meta(RTDoseStorage, sop_uid), preamble=b"\x00" * 128)
    ds.SOPClassUID = RTDoseStorage
    ds.SOPInstanceUID = sop_uid
    _base(ds, patient_id, "RTDOSE", frame_uid)

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.Rows = rows
    ds.Columns = columns
    ds.NumberOfFrames = n_frames
    ds.FrameIncrementPointer = pydicom.tag.Tag(0x3004, 0x000C)
    ds.ImagePositionPatient = [origin[0], origin[1], origin[2]]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelSpacing = [spacing_mm, spacing_mm]
    ds.SliceThickness = spacing_mm
    ds.GridFrameOffsetVector = [float(i * spacing_mm) for i in range(n_frames)]

    ds.DoseUnits = "GY"
    ds.DoseType = "PHYSICAL"
    ds.DoseSummationType = "PLAN"
    scaling = dose_gy / 30000.0  # keep pixel values mid-uint16 range
    ds.DoseGridScaling = scaling
    pixel_value = int(round(dose_gy / scaling))
    grid = np.full((n_frames, rows, columns), pixel_value, dtype=np.uint16)
    ds.PixelData = grid.tobytes()
    return ds


def _contour_data(roi: SyntheticROI, z: float) -> list[float]:
    """CLOSED_PLANAR rectangle at plane z (x,y,z triplets)."""
    corners = [
        (roi.x0_mm, roi.y0_mm),
        (roi.x1_mm, roi.y0_mm),
        (roi.x1_mm, roi.y1_mm),
        (roi.x0_mm, roi.y1_mm),
    ]
    data: list[float] = []
    for x, y in corners:
        data += [float(x), float(y), float(z)]
    return data


def _build_rtstruct(patient_id: str, frame_uid: str, rois: list[SyntheticROI]) -> Dataset:
    sop_uid = generate_uid()
    ds = FileDataset(
        None, {}, file_meta=_file_meta(RTStructureSetStorage, sop_uid), preamble=b"\x00" * 128
    )
    ds.SOPClassUID = RTStructureSetStorage
    ds.SOPInstanceUID = sop_uid
    _base(ds, patient_id, "RTSTRUCT", frame_uid)
    ds.StructureSetLabel = "SYNTH"

    ref_for = Dataset()
    ref_for.FrameOfReferenceUID = frame_uid
    ds.ReferencedFrameOfReferenceSequence = [ref_for]

    set_seq, contour_seq, obs_seq = [], [], []
    for i, roi in enumerate(rois, start=1):
        roi_ds = Dataset()
        roi_ds.ROINumber = i
        roi_ds.ReferencedFrameOfReferenceUID = frame_uid
        roi_ds.ROIName = roi.name
        roi_ds.ROIGenerationAlgorithm = "MANUAL"
        set_seq.append(roi_ds)

        planes = []
        z = roi.z0_mm
        while z <= roi.z1_mm + 1e-6:
            c = Dataset()
            c.ContourGeometricType = "CLOSED_PLANAR"
            c.NumberOfContourPoints = 4
            c.ContourData = _contour_data(roi, z)
            planes.append(c)
            z += 3.0
        roi_contour = Dataset()
        roi_contour.ReferencedROINumber = i
        roi_contour.ROIDisplayColor = [255, 0, 0]
        roi_contour.ContourSequence = planes
        contour_seq.append(roi_contour)

        obs = Dataset()
        obs.ObservationNumber = i
        obs.ReferencedROINumber = i
        obs.RTROIInterpretedType = roi.roi_type
        obs.ROIObservationLabel = roi.name
        obs_seq.append(obs)

    ds.StructureSetROISequence = set_seq
    ds.ROIContourSequence = contour_seq
    ds.RTROIObservationsSequence = obs_seq
    return ds


def _build_rtplan(patient_id: str, frame_uid: str, dose_gy: float, n_fractions: int) -> Dataset:
    sop_uid = generate_uid()
    ds = FileDataset(None, {}, file_meta=_file_meta(RTPlanStorage, sop_uid), preamble=b"\x00" * 128)
    ds.SOPClassUID = RTPlanStorage
    ds.SOPInstanceUID = sop_uid
    _base(ds, patient_id, "RTPLAN", frame_uid)
    ds.RTPlanLabel = "SYNTH"
    ds.ApprovalStatus = "UNAPPROVED"

    dref = Dataset()
    dref.DoseReferenceNumber = 1
    dref.DoseReferenceStructureType = "SITE"
    dref.DoseReferenceType = "TARGET"
    dref.TargetPrescriptionDose = float(dose_gy)
    ds.DoseReferenceSequence = [dref]

    fg = Dataset()
    fg.FractionGroupNumber = 1
    fg.NumberOfFractionsPlanned = int(n_fractions)
    fg.NumberOfBeams = 1
    ds.FractionGroupSequence = [fg]
    return ds


def save_dataset(ds: Dataset, dst: Any) -> None:
    """Write a Part-10 DICOM file, compatible with pydicom 2.x and 3.x."""
    try:
        ds.save_as(dst, write_like_original=False)  # pydicom <3.0
    except TypeError:
        ds.save_as(dst, enforce_file_format=True)  # pydicom >=3.0


def write_rt_triple(out_dir: Path, **kwargs) -> dict[str, Path]:
    """Build a triple and write the three DICOM files; return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rt_struct, rt_dose, rt_plan = build_rt_triple(**kwargs)
    paths = {
        "rt_struct": out_dir / "RS.dcm",
        "rt_dose": out_dir / "RD.dcm",
        "rt_plan": out_dir / "RP.dcm",
    }
    save_dataset(rt_struct, paths["rt_struct"])
    save_dataset(rt_dose, paths["rt_dose"])
    save_dataset(rt_plan, paths["rt_plan"])
    return paths


# Suppress unused-import lint for re-exported UIDs used by callers/tests.
_ = (CTImageStorage,)
