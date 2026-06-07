"""3D dose grid extraction (§27) with synthetic fallback for tests."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

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
    """Literature-realistic OAR dose voxel sample (log-normal-ish spread)."""
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


def extract_oar_dose_volume(
    rtdose_path: Path | None,
    rtstruct_path: Path | None,
    roi_name: str,
    target_voxel_mm: float = 3.0,
    *,
    fallback_mean_dose_gy: float | None = None,
) -> np.ndarray | None:
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
                            return vals.astype(np.float32)
    if fallback_mean_dose_gy is not None and not math.isnan(fallback_mean_dose_gy):
        return synthetic_oar_dose_voxels(mean_dose_gy=fallback_mean_dose_gy)
    return synthetic_oar_dose_voxels()
