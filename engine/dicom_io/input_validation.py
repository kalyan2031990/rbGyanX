"""
Fail-fast validators for RT input, with clear, actionable error messages.

These turn malformed input (empty structure sets, no target volume) into an
explicit error at the boundary instead of a silent NaN or empty result downstream.
The NaN-not-zero contract for individual *absent* OARs is unchanged — these guards
only fire on genuinely unusable input.
"""

from __future__ import annotations

from typing import Any

from dicom_io.structure_mapper import get_target_structures


def roi_names(rt_struct_ds: Any) -> list[str]:
    """Return the raw ROI names in an RTSTRUCT (empty list if none)."""
    seq = getattr(rt_struct_ds, "StructureSetROISequence", None) or []
    return [str(getattr(r, "ROIName", "") or "") for r in seq]


def ensure_rtstruct_has_rois(rt_struct_ds: Any) -> None:
    """Raise ValueError if the structure set contains no ROIs at all."""
    if rt_struct_ds is None:
        raise ValueError("RT Structure Set is missing (None)")
    if not roi_names(rt_struct_ds):
        raise ValueError(
            "RT Structure Set has no ROIs (empty StructureSetROISequence); "
            "the file is malformed or not an RTSTRUCT"
        )


def ensure_targets_present(rt_struct_ds: Any) -> list[dict]:
    """Return target structures; raise a clear error if none can be found.

    Use where a target volume is required (e.g. TCP). Names are normalised via the
    TG-263 / alias map first, so arbitrary vendor/centre spellings still resolve.
    """
    ensure_rtstruct_has_rois(rt_struct_ds)
    targets = get_target_structures(rt_struct_ds, {})
    if not targets:
        names = roi_names(rt_struct_ds)
        raise ValueError(
            "no target volume (GTV/CTV/PTV/ITV/BOOST) found among ROIs "
            f"{names[:12]}; rename the target or check the RTSTRUCT"
        )
    return targets
