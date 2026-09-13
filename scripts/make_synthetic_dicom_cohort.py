"""Generate a synthetic DICOM-RT cohort so the documented smoke test actually exercises the pipeline.

`test_data/dicom_input/` shipped empty, so the smoke test in the README completed with
``attempted: 0`` and looked like a pass. This script writes a complete, self-consistent DICOM-RT study
- CT series, RTSTRUCT, RTPLAN, RTDOSE - with the UID cross-references the ingest layer resolves, so the
run has something real to process.

The data are entirely synthetic: a phantom of nested ellipsoids in a water background, no patient
origin of any kind. DICOM output stays gitignored (``*.dcm``) by design, because a repository that
tracks .dcm files is one accident away from tracking real ones.

    python scripts/make_synthetic_dicom_cohort.py --out test_data/dicom_input --patients 2
"""

from __future__ import annotations

import argparse
from pathlib import Path

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

ROWS = COLS = 64
PIXEL_MM = 4.0
SLICE_MM = 4.0
N_SLICES = 24
N_FRACTIONS = 25
RX_GY = 50.0

# name, centre (x, y, z) in mm relative to the volume centre, radii (x, y, z) in mm, HU
STRUCTURES = [
    ("PTV", (0.0, 0.0, 0.0), (28.0, 24.0, 20.0), 40),
    ("Parotid_L", (-52.0, 10.0, 0.0), (16.0, 14.0, 18.0), 20),
    ("Parotid_R", (52.0, 10.0, 0.0), (16.0, 14.0, 18.0), 20),
    ("SpinalCord", (0.0, 46.0, 0.0), (7.0, 7.0, 44.0), 35),
]


def _save(ds: FileDataset, path: Path) -> None:
    """Write a conformant Part-10 file across the pydicom 2.x / 3.x API change.

    The repo pins pydicom <3.0 (dicompyler-core needs it), where the flag is
    `write_like_original=False`; 3.x renamed it to `enforce_file_format=True`."""
    try:
        ds.save_as(path, enforce_file_format=True)
    except TypeError:
        ds.save_as(path, write_like_original=False)


def _meta(sop_class: str, sop_uid: str) -> FileMetaDataset:
    m = FileMetaDataset()
    m.MediaStorageSOPClassUID = sop_class
    m.MediaStorageSOPInstanceUID = sop_uid
    m.TransferSyntaxUID = ExplicitVRLittleEndian
    m.ImplementationClassUID = generate_uid()
    return m


def _base(ds: Dataset, patient_id: str, study_uid: str, for_uid: str) -> None:
    ds.PatientName = f"SYNTHETIC^{patient_id}"
    ds.PatientID = patient_id
    ds.PatientBirthDate = ""
    ds.PatientSex = "O"
    ds.StudyInstanceUID = study_uid
    ds.FrameOfReferenceUID = for_uid
    ds.StudyDate = "20200101"
    ds.StudyTime = "120000"
    ds.AccessionNumber = ""
    ds.ReferringPhysicianName = ""
    ds.Manufacturer = "rbGyanX synthetic phantom"
    ds.is_little_endian = True
    ds.is_implicit_VR = False


def _grid(shape=(N_SLICES, ROWS, COLS)):
    nz, ny, nx = shape
    z = (np.arange(nz) - (nz - 1) / 2) * SLICE_MM
    y = (np.arange(ny) - (ny - 1) / 2) * PIXEL_MM
    x = (np.arange(nx) - (nx - 1) / 2) * PIXEL_MM
    return np.meshgrid(z, y, x, indexing="ij")


def _masks():
    Z, Y, X = _grid()
    out = {}
    for name, (cx, cy, cz), (rx, ry, rz), _hu in STRUCTURES:
        out[name] = (((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2) <= 1.0
    return out


def write_ct(out: Path, patient_id: str, study_uid: str, for_uid: str, rng) -> tuple[str, list[str]]:
    """Water-background phantom with the structures embedded; returns (series_uid, sop_uids)."""
    series_uid = generate_uid()
    masks = _masks()
    hu = np.full((N_SLICES, ROWS, COLS), -1000, dtype=np.int16)          # air
    Z, Y, X = _grid()
    body = ((X / 110.0) ** 2 + (Y / 80.0) ** 2) <= 1.0
    hu[body] = 0                                                          # water
    for name, _c, _r, val in STRUCTURES:
        hu[masks[name]] = val
    hu = hu + rng.normal(0, 8, hu.shape).astype(np.int16)                 # mild texture

    sop_uids = []
    for k in range(N_SLICES):
        sop = generate_uid()
        ds = FileDataset(str(out / f"CT_{k:03d}.dcm"), Dataset(),
                         file_meta=_meta(CTImageStorage, sop), preamble=b"\0" * 128)
        _base(ds, patient_id, study_uid, for_uid)
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = sop
        ds.SeriesInstanceUID = series_uid
        ds.Modality = "CT"
        ds.SeriesDescription = "Synthetic phantom CT"
        ds.InstanceNumber = k + 1
        ds.ImagePositionPatient = [-(COLS - 1) / 2 * PIXEL_MM,
                                   -(ROWS - 1) / 2 * PIXEL_MM,
                                   (k - (N_SLICES - 1) / 2) * SLICE_MM]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.PixelSpacing = [PIXEL_MM, PIXEL_MM]
        ds.SliceThickness = SLICE_MM
        ds.Rows, ds.Columns = ROWS, COLS
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.RescaleIntercept = 0
        ds.RescaleSlope = 1
        ds.PixelData = hu[k].astype(np.int16).tobytes()
        _save(ds, out / f"CT_{k:03d}.dcm")
        sop_uids.append(sop)
    return series_uid, sop_uids


def write_rtstruct(out: Path, patient_id: str, study_uid: str, for_uid: str,
                   ct_series_uid: str, ct_sops: list[str]) -> str:
    sop = generate_uid()
    ds = FileDataset(str(out / "RTSTRUCT.dcm"), Dataset(),
                     file_meta=_meta(RTStructureSetStorage, sop), preamble=b"\0" * 128)
    _base(ds, patient_id, study_uid, for_uid)
    ds.SOPClassUID = RTStructureSetStorage
    ds.SOPInstanceUID = sop
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "RTSTRUCT"
    ds.StructureSetLabel = "SyntheticStructures"

    ref_series = Dataset()
    ref_series.SeriesInstanceUID = ct_series_uid
    ref_series.ContourImageSequence = []
    for s in ct_sops:
        ci = Dataset()
        ci.ReferencedSOPClassUID = CTImageStorage
        ci.ReferencedSOPInstanceUID = s
        ref_series.ContourImageSequence.append(ci)
    ref_study = Dataset()
    ref_study.ReferencedSOPClassUID = "1.2.840.10008.3.1.2.3.1"
    ref_study.ReferencedSOPInstanceUID = study_uid
    ref_study.RTReferencedSeriesSequence = [ref_series]
    rfor = Dataset()
    rfor.FrameOfReferenceUID = for_uid
    rfor.RTReferencedStudySequence = [ref_study]
    ds.ReferencedFrameOfReferenceSequence = [rfor]

    ds.StructureSetROISequence = []
    ds.ROIContourSequence = []
    ds.RTROIObservationsSequence = []
    for i, (name, (cx, cy, cz), (rx, ry, rz), _hu) in enumerate(STRUCTURES, start=1):
        roi = Dataset()
        roi.ROINumber = i
        roi.ReferencedFrameOfReferenceUID = for_uid
        roi.ROIName = name
        roi.ROIGenerationAlgorithm = "MANUAL"
        ds.StructureSetROISequence.append(roi)

        contours = []
        for k in range(N_SLICES):
            z = (k - (N_SLICES - 1) / 2) * SLICE_MM
            t = 1.0 - ((z - cz) / rz) ** 2
            if t <= 0:
                continue
            a, b = rx * np.sqrt(t), ry * np.sqrt(t)
            ang = np.linspace(0, 2 * np.pi, 33)[:-1]
            pts = np.column_stack([cx + a * np.cos(ang), cy + b * np.sin(ang),
                                   np.full(ang.shape, z)])
            c = Dataset()
            ci = Dataset()
            ci.ReferencedSOPClassUID = CTImageStorage
            ci.ReferencedSOPInstanceUID = ct_sops[k]
            c.ContourImageSequence = [ci]
            c.ContourGeometricType = "CLOSED_PLANAR"
            c.NumberOfContourPoints = len(pts)
            c.ContourData = [float(v) for v in pts.ravel()]
            contours.append(c)
        rc = Dataset()
        rc.ReferencedROINumber = i
        rc.ROIDisplayColor = [255, 0, 0]
        rc.ContourSequence = contours
        ds.ROIContourSequence.append(rc)

        obs = Dataset()
        obs.ObservationNumber = i
        obs.ReferencedROINumber = i
        obs.RTROIInterpretedType = "PTV" if name == "PTV" else "ORGAN"
        obs.ROIInterpreter = ""
        ds.RTROIObservationsSequence.append(obs)

    _save(ds, out / "RTSTRUCT.dcm")
    return sop


def write_rtplan(out: Path, patient_id: str, study_uid: str, for_uid: str,
                 struct_sop: str) -> str:
    sop = generate_uid()
    ds = FileDataset(str(out / "RTPLAN.dcm"), Dataset(),
                     file_meta=_meta(RTPlanStorage, sop), preamble=b"\0" * 128)
    _base(ds, patient_id, study_uid, for_uid)
    ds.SOPClassUID = RTPlanStorage
    ds.SOPInstanceUID = sop
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "RTPLAN"
    ds.RTPlanLabel = "SyntheticPlan"
    ds.RTPlanGeometry = "PATIENT"
    ds.ApprovalStatus = "UNAPPROVED"

    rs = Dataset()
    rs.ReferencedSOPClassUID = RTStructureSetStorage
    rs.ReferencedSOPInstanceUID = struct_sop
    ds.ReferencedStructureSetSequence = [rs]

    dr = Dataset()
    dr.DoseReferenceNumber = 1
    dr.DoseReferenceStructureType = "SITE"
    dr.DoseReferenceDescription = "PTV"
    dr.DoseReferenceType = "TARGET"
    dr.TargetPrescriptionDose = RX_GY
    ds.DoseReferenceSequence = [dr]

    beam = Dataset()
    beam.ReferencedBeamNumber = 1
    beam.BeamDose = RX_GY / N_FRACTIONS
    beam.BeamMeterset = 100.0
    fg = Dataset()
    fg.FractionGroupNumber = 1
    fg.NumberOfFractionsPlanned = N_FRACTIONS
    fg.NumberOfBeams = 1
    fg.ReferencedBeamSequence = [beam]
    ds.FractionGroupSequence = [fg]

    b = Dataset()
    b.BeamNumber = 1
    b.BeamName = "SYNTH1"
    b.BeamType = "STATIC"
    b.RadiationType = "PHOTON"
    b.TreatmentMachineName = "SYNTH"
    ds.BeamSequence = [b]

    _save(ds, out / "RTPLAN.dcm")
    return sop


def write_rtdose(out: Path, patient_id: str, study_uid: str, for_uid: str,
                 plan_sop: str) -> str:
    """Dose falling off from the PTV, so DVHs and NTCP have real structure to work on."""
    sop = generate_uid()
    masks = _masks()
    Z, Y, X = _grid()
    ptv_c, ptv_r = STRUCTURES[0][1], STRUCTURES[0][2]
    r = np.sqrt(((X - ptv_c[0]) / ptv_r[0]) ** 2 + ((Y - ptv_c[1]) / ptv_r[1]) ** 2
                + ((Z - ptv_c[2]) / ptv_r[2]) ** 2)
    dose = RX_GY * np.exp(-np.clip(r - 1.0, 0, None) ** 2 / 0.9)
    dose[masks["PTV"]] = RX_GY * 1.02
    # DoseGridScaling must be derived from the actual dose range: a fixed 1e-4 made 51 Gy map to
    # 510 000, which saturates uint16 at 65535 and silently caps the grid at 6.55 Gy. Real TPS
    # exports scale to fill the integer range, so do the same.
    scaling = float(dose.max()) / 60000.0
    grid = np.clip(np.round(dose / scaling), 0, 65535).astype(np.uint16)

    ds = FileDataset(str(out / "RTDOSE.dcm"), Dataset(),
                     file_meta=_meta(RTDoseStorage, sop), preamble=b"\0" * 128)
    _base(ds, patient_id, study_uid, for_uid)
    ds.SOPClassUID = RTDoseStorage
    ds.SOPInstanceUID = sop
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = "RTDOSE"
    ds.DoseUnits = "GY"
    ds.DoseType = "PHYSICAL"
    ds.DoseSummationType = "PLAN"
    ds.DoseGridScaling = scaling
    ds.ImagePositionPatient = [-(COLS - 1) / 2 * PIXEL_MM,
                               -(ROWS - 1) / 2 * PIXEL_MM,
                               -(N_SLICES - 1) / 2 * SLICE_MM]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelSpacing = [PIXEL_MM, PIXEL_MM]
    ds.SliceThickness = SLICE_MM
    ds.GridFrameOffsetVector = [float(k * SLICE_MM) for k in range(N_SLICES)]
    ds.NumberOfFrames = N_SLICES
    ds.FrameIncrementPointer = pydicom.tag.Tag(0x3004, 0x000C)
    ds.Rows, ds.Columns = ROWS, COLS
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = grid.astype(np.uint16).tobytes()

    rp = Dataset()
    rp.ReferencedSOPClassUID = RTPlanStorage
    rp.ReferencedSOPInstanceUID = plan_sop
    ds.ReferencedRTPlanSequence = [rp]

    _save(ds, out / "RTDOSE.dcm")
    return sop


def make_patient(root: Path, patient_id: str, seed: int) -> Path:
    d = root / patient_id
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    study_uid, for_uid = generate_uid(), generate_uid()
    ct_series, ct_sops = write_ct(d, patient_id, study_uid, for_uid, rng)
    struct_sop = write_rtstruct(d, patient_id, study_uid, for_uid, ct_series, ct_sops)
    plan_sop = write_rtplan(d, patient_id, study_uid, for_uid, struct_sop)
    write_rtdose(d, patient_id, study_uid, for_uid, plan_sop)
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("test_data/dicom_input"))
    ap.add_argument("--patients", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    made = [make_patient(a.out, f"SYNTH{i + 1:03d}", a.seed + i) for i in range(a.patients)]
    n = sum(1 for p in a.out.rglob("*.dcm"))
    print(f"wrote {len(made)} synthetic patients, {n} DICOM files, to {a.out}")
    for d in made:
        print(f"  {d.name}: {len(list(d.glob('CT_*.dcm')))} CT + RTSTRUCT + RTPLAN + RTDOSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
