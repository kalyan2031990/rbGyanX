"""3D dose grid extraction (§27).

PRODUCTION DOSIOMICS USE REAL RTDOSE ONLY.

A synthetic voxel generator lives here for test fixtures and development, but it can never be reached
implicitly: every caller that wants it must pass ``allow_synthetic=True``, which no production code
path does. When a real dose grid cannot be extracted the extractor returns ``None`` with source
``NOT_AVAILABLE`` rather than fabricating voxels. See docs/DOSIOMICS_DATA_PROVENANCE.md.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Provenance labels attached to every extraction so that no downstream consumer has to guess whether
# a dose array came from the patient's RTDOSE or from a generator.
SOURCE_REAL_RTDOSE = "real_rtdose"
SOURCE_NOT_AVAILABLE = "NOT_AVAILABLE"
SOURCE_SYNTHETIC_TEST = "synthetic_test_fixture"

#: The only source a production analysis may consume.
PRODUCTION_DOSE_SOURCES = frozenset({SOURCE_REAL_RTDOSE})


class SyntheticDoseInProductionError(RuntimeError):
    """Raised when synthetic dose voxels reach a pathway declared as production."""


def assert_production_dose_source(dose_source: str, context: str = "dosiomics") -> None:
    """Hard guard: refuse to let anything but a real RTDOSE grid into a production analysis.

    Fails loudly and immediately. A silent synthetic fallback previously made surrogate features
    indistinguishable from measured ones in the output tables; that failure mode must be impossible.
    """
    if dose_source not in PRODUCTION_DOSE_SOURCES:
        raise SyntheticDoseInProductionError(
            f"{context}: dose_source={dose_source!r} is not permitted in production. "
            f"Production dosiomics require a real RTDOSE grid ({SOURCE_REAL_RTDOSE}). "
            "Synthetic voxels are available only to tests via allow_synthetic=True."
        )

try:
    import pydicom
    from scipy.ndimage import zoom
    from skimage.draw import polygon

    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False


def _check_deps() -> bool:
    if not _DEPS_AVAILABLE:
        logger.debug("dose3d: pydicom/scipy/skimage not installed")
    return _DEPS_AVAILABLE


def synthetic_oar_dose_voxels(
    n_voxels: int = 500,
    mean_dose_gy: float = 45.0,
    std_gy: float = 8.0,
    seed: int = 0,
) -> np.ndarray:
    """TEST FIXTURE ONLY - a generated OAR dose voxel sample, not measured dose.

    These voxels are drawn from a normal distribution around ``mean_dose_gy``; they carry no patient
    dose information and any feature computed from them is a surrogate, not a dosiomic. Nothing in a
    production pathway may call this: use it to exercise the pipeline in tests and development.
    """
    rng = np.random.default_rng(seed)
    d = rng.normal(mean_dose_gy, std_gy, size=n_voxels)
    return np.clip(d, 0.0, 80.0).astype(np.float32)


def load_dose_grid(rtdose_path: Path) -> dict | None:
    if not _check_deps():
        return None
    try:
        ds = pydicom.dcmread(str(rtdose_path))
    except Exception as exc:
        logger.error("Cannot read RTDOSE %s: %s", rtdose_path, exc)
        return None
    scale = float(getattr(ds, "DoseGridScaling", 1.0))
    pixel_array = ds.pixel_array.astype(float) * scale
    ipp = [float(v) for v in ds.ImagePositionPatient]
    row_spacing, col_spacing = float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1])
    slice_offsets = [float(v) for v in ds.GridFrameOffsetVector]
    dz = abs(slice_offsets[1] - slice_offsets[0]) if len(slice_offsets) > 1 else row_spacing
    return {
        "dose_array": pixel_array,
        "origin_mm": tuple(ipp),
        "voxel_size_mm": (col_spacing, row_spacing, dz),
        "shape": pixel_array.shape,
    }


def resample_to_isotropic(dose_dict: dict, target_voxel_mm: float = 3.0) -> dict:
    if not _check_deps():
        return dose_dict
    dx, dy, dz = dose_dict["voxel_size_mm"]
    zoom_factors = (dz / target_voxel_mm, dy / target_voxel_mm, dx / target_voxel_mm)
    resampled = zoom(dose_dict["dose_array"], zoom_factors, order=1, prefilter=False)
    return {
        **dose_dict,
        "dose_array": resampled,
        "voxel_size_mm": (target_voxel_mm, target_voxel_mm, target_voxel_mm),
        "shape": resampled.shape,
    }


def build_oar_mask(contour_sequence, dose_dict: dict) -> np.ndarray:
    if not _check_deps():
        return np.zeros(dose_dict["shape"], dtype=bool)
    shape = dose_dict["shape"]
    nz, ny, nx = shape
    origin = dose_dict["origin_mm"]
    dx, dy, dz = dose_dict["voxel_size_mm"]
    mask = np.zeros(shape, dtype=bool)
    for contour in contour_sequence:
        pts = np.array(contour.ContourData).reshape(-1, 3)
        z_mm = float(pts[0, 2])
        z_idx = int(round((z_mm - origin[2]) / dz))
        if z_idx < 0 or z_idx >= nz:
            continue
        x_idx = ((pts[:, 0] - origin[0]) / dx).astype(float)
        y_idx = ((pts[:, 1] - origin[1]) / dy).astype(float)
        rr, cc = polygon(y_idx, x_idx, shape=(ny, nx))
        mask[z_idx, rr, cc] = True
    return mask


def extract_oar_dose_volume_with_source(
    rtdose_path: Path | None,
    rtstruct_path: Path | None,
    roi_name: str,
    target_voxel_mm: float = 3.0,
    *,
    allow_synthetic: bool = False,
    fallback_mean_dose_gy: float | None = None,
) -> tuple[np.ndarray | None, str]:
    """Return ``(dose_voxels, dose_source)`` for one ROI.

    ``dose_source`` is one of :data:`SOURCE_REAL_RTDOSE`, :data:`SOURCE_NOT_AVAILABLE` or
    :data:`SOURCE_SYNTHETIC_TEST`. Synthetic voxels are produced only when ``allow_synthetic=True``
    is passed explicitly; the default is a hard ``(None, NOT_AVAILABLE)`` so a missing dose grid can
    never masquerade as a measured one.
    """
    if rtdose_path and rtstruct_path and _check_deps():
        dose_dict = load_dose_grid(rtdose_path)
        if dose_dict is not None:
            dose_dict = resample_to_isotropic(dose_dict, target_voxel_mm)
            try:
                struct_ds = pydicom.dcmread(str(rtstruct_path))
            except Exception:
                struct_ds = None
            if struct_ds is not None:
                roi_number = None
                for roi in struct_ds.StructureSetROISequence:
                    if roi.ROIName.strip().lower() == roi_name.strip().lower():
                        roi_number = roi.ROINumber
                        break
                if roi_number is not None:
                    contour_seq = None
                    for roi_contour in struct_ds.ROIContourSequence:
                        if roi_contour.ReferencedROINumber == roi_number:
                            contour_seq = getattr(roi_contour, "ContourSequence", [])
                            break
                    if contour_seq:
                        mask = build_oar_mask(contour_seq, dose_dict)
                        vals = dose_dict["dose_array"][mask]
                        if len(vals) > 0:
                            return vals.astype(np.float32), SOURCE_REAL_RTDOSE

    if not allow_synthetic:
        # C4 FAIL SOFT, LOG LOUD: no real grid means no dosiomics for this ROI, and the caller is
        # told so explicitly instead of being handed generated numbers.
        logger.warning(
            "dose3d: no real RTDOSE-derived voxels for ROI %r (rtdose=%s, rtstruct=%s) - "
            "returning NOT_AVAILABLE. Synthetic dose is disabled outside explicit test mode.",
            roi_name, rtdose_path, rtstruct_path,
        )
        return None, SOURCE_NOT_AVAILABLE

    logger.warning(
        "dose3d: returning SYNTHETIC dose voxels for ROI %r because allow_synthetic=True. "
        "These are a test fixture and must never be reported as dosiomics.",
        roi_name,
    )
    if fallback_mean_dose_gy is not None and not math.isnan(fallback_mean_dose_gy):
        return synthetic_oar_dose_voxels(mean_dose_gy=fallback_mean_dose_gy), SOURCE_SYNTHETIC_TEST
    return synthetic_oar_dose_voxels(), SOURCE_SYNTHETIC_TEST


def extract_oar_dose_volume(
    rtdose_path: Path | None,
    rtstruct_path: Path | None,
    roi_name: str,
    target_voxel_mm: float = 3.0,
    *,
    allow_synthetic: bool = False,
    fallback_mean_dose_gy: float | None = None,
) -> np.ndarray | None:
    """Real RTDOSE-derived voxels for one ROI, or ``None`` when unavailable.

    This used to fall back to :func:`synthetic_oar_dose_voxels` whenever real extraction failed,
    which let generated voxels enter production dosiomics indistinguishably. It no longer does.
    """
    voxels, _source = extract_oar_dose_volume_with_source(
        rtdose_path,
        rtstruct_path,
        roi_name,
        target_voxel_mm,
        allow_synthetic=allow_synthetic,
        fallback_mean_dose_gy=fallback_mean_dose_gy,
    )
    return voxels
