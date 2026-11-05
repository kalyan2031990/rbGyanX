"""Defect #52 -- the DVH end-caps volume but not the dose range.

Found by the Nelms et al. 2015 analytical comparison during v1.5.0 (Tier D1).

``dicompylercore.dvhcalc`` weights **every** contour plane by a full plane thickness, the outermost
included, so the volume it reports covers half a slice beyond each end contour -- an end-cap. That
matches the convention of the Nelms analytical tables, and the measured volume reproduces them.

But the **dose** it histograms is sampled only *at* contour planes. Nothing is sampled inside the
end-cap. So the reported dose range spans the outermost contours rather than the capped extent, and
the two halves of the convention disagree with each other.

Where a dose gradient runs along the slice axis, the consequence has a closed form: D_max is low by
half a slice thickness times the local gradient, and D_min high by the same. Against the Nelms
analytical values this held for 32 of 32 along-axis comparisons to within 0.005 Gy at contour
spacings of 0.2, 1, 2 and 3 mm. At a 3 mm slice and 1 Gy/mm that is 1.5 Gy -- not negligible for a
serial organ scored on D_max.

**This is not a fix and these tests do not assert one.** Changing how dose is sampled would alter
every DVH the project has ever produced, which is not a change to make without a decision. The
tests pin the present behaviour, with its magnitude, so that a future change to it is noticed
rather than silent, and so the limitation stays measured rather than remembered.
"""

from __future__ import annotations

import math

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    RTDoseStorage,
    RTStructureSetStorage,
    generate_uid,
)

pytest.importorskip("dicompylercore")

# dose grid: fine along z so the quantisation cannot be mistaken for the effect under test
DZ_MM = 0.5
IN_PLANE_MM = 1.0
N_FRAMES = 101  # z = 0 .. 50 mm
N_ROWS = N_COLS = 40  # x, y = 0 .. 39 mm
GRADIENT_GY_PER_MM = 1.0

# the box ROI, well inside the grid in every direction
X0, X1 = 10.0, 30.0
Y0, Y1 = 10.0, 30.0
Z0 = 10.0
N_PLANES = 5


def _file_meta(sop_class_uid: str, sop_instance_uid: str) -> FileMetaDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class_uid
    meta.MediaStorageSOPInstanceUID = sop_instance_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()
    return meta


def _base(ds: Dataset, modality: str, frame_uid: str) -> None:
    ds.PatientID = "SYN-ENDCAP"
    ds.PatientName = "Synthetic^Phantom"
    ds.Modality = modality
    ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.11111111111111111111111111"
    ds.SeriesInstanceUID = generate_uid()
    ds.FrameOfReferenceUID = frame_uid
    ds.SpecificCharacterSet = "ISO_IR 100"


def _linear_dose(frame_uid: str, axis: str) -> Dataset:
    """RTDOSE with a 1 Gy/mm linear ramp along ``axis`` ('z' or 'y')."""
    sop_uid = generate_uid()
    ds = FileDataset(None, {}, file_meta=_file_meta(RTDoseStorage, sop_uid), preamble=b"\x00" * 128)
    ds.SOPClassUID = RTDoseStorage
    ds.SOPInstanceUID = sop_uid
    _base(ds, "RTDOSE", frame_uid)

    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.Rows = N_ROWS
    ds.Columns = N_COLS
    ds.NumberOfFrames = N_FRAMES
    ds.FrameIncrementPointer = pydicom.tag.Tag(0x3004, 0x000C)
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelSpacing = [IN_PLANE_MM, IN_PLANE_MM]
    ds.SliceThickness = DZ_MM
    ds.GridFrameOffsetVector = [float(i * DZ_MM) for i in range(N_FRAMES)]
    ds.DoseUnits = "GY"
    ds.DoseType = "PHYSICAL"
    ds.DoseSummationType = "PLAN"

    # dose in Gy equals the coordinate in mm, exactly
    scaling = 0.01
    ds.DoseGridScaling = scaling
    if axis == "z":
        ramp = np.arange(N_FRAMES, dtype=float) * DZ_MM * GRADIENT_GY_PER_MM
        grid = np.broadcast_to(ramp[:, None, None], (N_FRAMES, N_ROWS, N_COLS))
    elif axis == "y":
        ramp = np.arange(N_ROWS, dtype=float) * IN_PLANE_MM * GRADIENT_GY_PER_MM
        grid = np.broadcast_to(ramp[None, :, None], (N_FRAMES, N_ROWS, N_COLS))
    else:  # pragma: no cover - guards a typo in a parametrisation
        raise ValueError(axis)
    ds.PixelData = np.ascontiguousarray(np.rint(grid / scaling).astype(np.uint16)).tobytes()
    return ds


def _box_struct(frame_uid: str, spacing_mm: float, n_planes: int = N_PLANES) -> Dataset:
    """RTSTRUCT holding one box ROI contoured on planes ``spacing_mm`` apart."""
    sop_uid = generate_uid()
    ds = FileDataset(
        None, {}, file_meta=_file_meta(RTStructureSetStorage, sop_uid), preamble=b"\x00" * 128
    )
    ds.SOPClassUID = RTStructureSetStorage
    ds.SOPInstanceUID = sop_uid
    _base(ds, "RTSTRUCT", frame_uid)
    ds.StructureSetLabel = "ENDCAP"

    ref = Dataset()
    ref.FrameOfReferenceUID = frame_uid
    ds.ReferencedFrameOfReferenceSequence = [ref]

    roi = Dataset()
    roi.ROINumber = 1
    roi.ReferencedFrameOfReferenceUID = frame_uid
    roi.ROIName = "Box"
    roi.ROIGenerationAlgorithm = "MANUAL"
    ds.StructureSetROISequence = [roi]

    planes = []
    for i in range(n_planes):
        z = Z0 + i * spacing_mm
        contour = Dataset()
        contour.ContourGeometricType = "CLOSED_PLANAR"
        contour.NumberOfContourPoints = 4
        contour.ContourData = [
            X0,
            Y0,
            z,
            X1,
            Y0,
            z,
            X1,
            Y1,
            z,
            X0,
            Y1,
            z,
        ]
        planes.append(contour)
    roi_contour = Dataset()
    roi_contour.ReferencedROINumber = 1
    roi_contour.ROIDisplayColor = [255, 0, 0]
    roi_contour.ContourSequence = planes
    ds.ROIContourSequence = [roi_contour]

    obs = Dataset()
    obs.ObservationNumber = 1
    obs.ReferencedROINumber = 1
    obs.RTROIInterpretedType = "ORGAN"
    obs.ROIObservationLabel = "Box"
    ds.RTROIObservationsSequence = [obs]
    return ds


def _dvh(spacing_mm: float, axis: str, n_planes: int = N_PLANES):
    from dicompylercore import dvhcalc

    frame_uid = generate_uid()
    struct = _box_struct(frame_uid, spacing_mm, n_planes)
    dose = _linear_dose(frame_uid, axis)
    return dvhcalc.get_dvh(struct, dose, 1)


SPACINGS = [2.0, 4.0, 6.0]


# ------------------------------------------------------------ volume: the cap IS applied


@pytest.mark.parametrize("spacing_mm", SPACINGS)
def test_volume_includes_the_end_cap(spacing_mm: float) -> None:
    """Half a slice beyond each end contour, so N planes weigh N*t, not (N-1)*t.

    Tested as the ratio between two plane counts at the same spacing. That cancels the in-plane
    area, which is not what this test is about: a contour from 10 to 30 mm on a 1 mm grid covers
    21 voxel centres, not 20, so an absolute volume would be asserting a rasterisation convention
    at the same time as the end-cap and would not distinguish the two.
    """
    few, many = 5, 9
    v_few = _dvh(spacing_mm, "z", few).volume
    v_many = _dvh(spacing_mm, "z", many).volume

    capped_ratio = many / few  # N * t
    uncapped_ratio = (many - 1) / (few - 1)  # (N - 1) * t

    assert v_many / v_few == pytest.approx(capped_ratio, rel=0.01), (
        f"volume ratio {v_many / v_few:.4f} between {many} and {few} planes at "
        f"t = {spacing_mm} mm is not the end-capped {capped_ratio:.4f} "
        f"(uncapped would be {uncapped_ratio:.4f})"
    )
    # the two predictions must be far enough apart for that to mean something
    assert abs(capped_ratio - uncapped_ratio) > 0.05 * uncapped_ratio


# -------------------------------------------------- dose range: the cap is NOT applied


@pytest.mark.parametrize("spacing_mm", SPACINGS)
def test_dose_range_stops_at_the_outermost_contour_not_the_cap(spacing_mm: float) -> None:
    """Defect #52. D_max is the dose at the last contour, not at the capped edge."""
    dvh = _dvh(spacing_mm, "z")
    z_last = Z0 + (N_PLANES - 1) * spacing_mm
    at_contour = z_last * GRADIENT_GY_PER_MM
    at_capped_edge = (z_last + spacing_mm / 2.0) * GRADIENT_GY_PER_MM
    tol = DZ_MM * GRADIENT_GY_PER_MM  # one dose voxel along the gradient

    assert float(dvh.max) == pytest.approx(at_contour, abs=tol), (
        f"D_max {dvh.max:.3f} Gy is not the dose at the outermost contour " f"({at_contour:.3f} Gy)"
    )
    assert float(dvh.max) < at_capped_edge - 0.5 * spacing_mm + tol, (
        f"D_max {dvh.max:.3f} Gy reaches the capped edge ({at_capped_edge:.3f} Gy); "
        "the dose range would then be end-capped too and this defect fixed -- "
        "update KNOWN_LIMITATIONS.md and the Nelms comparison before relaxing this test"
    )


@pytest.mark.parametrize("spacing_mm", SPACINGS)
def test_the_shortfall_is_exactly_half_a_slice(spacing_mm: float) -> None:
    """The quantitative claim: the deviation scales with slice thickness, as t/2."""
    dvh = _dvh(spacing_mm, "z")
    z_last = Z0 + (N_PLANES - 1) * spacing_mm
    at_capped_edge = (z_last + spacing_mm / 2.0) * GRADIENT_GY_PER_MM
    shortfall = at_capped_edge - float(dvh.max)
    predicted = (spacing_mm / 2.0) * GRADIENT_GY_PER_MM

    assert shortfall == pytest.approx(predicted, abs=DZ_MM * GRADIENT_GY_PER_MM), (
        f"at t = {spacing_mm} mm the D_max shortfall is {shortfall:.3f} Gy, "
        f"not the predicted half-slice {predicted:.3f} Gy"
    )


@pytest.mark.parametrize("spacing_mm", SPACINGS)
def test_dmin_is_high_by_the_same_half_slice(spacing_mm: float) -> None:
    """The cap is symmetric, so D_min errs the other way by the same amount."""
    dvh = _dvh(spacing_mm, "z")
    at_capped_edge = (Z0 - spacing_mm / 2.0) * GRADIENT_GY_PER_MM
    excess = float(dvh.min) - at_capped_edge
    predicted = (spacing_mm / 2.0) * GRADIENT_GY_PER_MM

    assert excess == pytest.approx(predicted, abs=DZ_MM * GRADIENT_GY_PER_MM), (
        f"at t = {spacing_mm} mm D_min exceeds the capped edge by {excess:.3f} Gy, "
        f"not the predicted half-slice {predicted:.3f} Gy"
    )


# --------------------------------------------- in-plane gradient: the cap cannot matter


@pytest.mark.parametrize("spacing_mm", SPACINGS)
def test_an_in_plane_gradient_is_independent_of_contour_spacing(spacing_mm: float) -> None:
    """The cap extends along z, so a gradient across y must not see it at all.

    This is the other half of the finding, and it is what makes the half-slice result above
    attributable to the cap rather than to contour spacing in general: here the spacing changes by
    a factor of three and the dose range does not move.
    """
    dvh = _dvh(spacing_mm, "y")
    # one in-plane voxel -- the only bound claimed -- plus one DVH bin, since dicompyler-core
    # reports D_min and D_max at a bin edge and its bins are 1 cGy wide
    tol = IN_PLANE_MM * GRADIENT_GY_PER_MM + 0.02

    assert float(dvh.max) == pytest.approx(Y1 * GRADIENT_GY_PER_MM, abs=tol)
    assert float(dvh.min) == pytest.approx(Y0 * GRADIENT_GY_PER_MM, abs=tol)


def test_the_in_plane_dose_range_does_not_scale_with_slice_thickness() -> None:
    """Stated as a comparison across spacings, which is the claim the report makes."""
    ranges = {}
    for spacing_mm in SPACINGS:
        dvh = _dvh(spacing_mm, "y")
        ranges[spacing_mm] = float(dvh.max) - float(dvh.min)
    spread = max(ranges.values()) - min(ranges.values())
    assert spread <= IN_PLANE_MM * GRADIENT_GY_PER_MM, (
        f"in-plane dose range varies by {spread:.3f} Gy across contour spacings "
        f"{sorted(ranges)}: {ranges}. It should not depend on slice thickness at all."
    )


def test_mean_dose_is_barely_affected() -> None:
    """Scope of the defect: it bounds the range, and leaves the bulk of the DVH alone.

    Worth pinning, because it is the reason the defect is a documented limitation rather than
    something that invalidates existing mean-dose and gEUD results.
    """
    for spacing_mm in SPACINGS:
        dvh = _dvh(spacing_mm, "z")
        z_last = Z0 + (N_PLANES - 1) * spacing_mm
        centre = 0.5 * (Z0 + z_last) * GRADIENT_GY_PER_MM
        assert math.isfinite(float(dvh.mean))
        assert float(dvh.mean) == pytest.approx(centre, abs=0.5), (
            f"at t = {spacing_mm} mm the mean dose {dvh.mean:.3f} Gy is not the geometric "
            f"centre {centre:.3f} Gy; the cap would have to be asymmetric"
        )
