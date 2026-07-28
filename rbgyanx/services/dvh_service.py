"""
DVH data handling — headless, UI-independent (v2 Phase 4 · Slice 1).

Extracted VERBATIM from ``rbgyanx_gui.rbGyanX_GUI`` so the desktop app becomes a thin view
over this service. The bodies are unchanged apart from dropping ``self`` and de-indenting;
``tests/test_gui_service_equivalence.py`` asserts these functions return results identical to
the GUI methods they came from, so the extraction cannot silently change behaviour.

Pure functions: no I/O, no widgets, no globals, no patient data retained.
"""

from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: F401  (used by callers passing DataFrames)

__all__ = ["build_canonical_dvh", "normalize_dvh", "validate_dvh_integrity"]


def build_canonical_dvh(dose, volume, dvh_type):
    """
    Build canonical cumulative and differential DVH.
    Pure function with no side effects. Does NOT modify input arrays.

    Parameters
    ----------
    dose : np.ndarray
        Dose values
    volume : np.ndarray
        Volume values
    dvh_type : str
        'cumulative' or 'differential'

    Returns
    -------
    dict
        {
            "dose": dose_sorted,
            "cumulative": cumulative_volume,
            "differential": differential_volume
        }
    """
    # Convert to numpy arrays (copy to avoid modifying input)
    dose = np.asarray(dose).copy()
    volume = np.asarray(volume).copy()

    # Sort by dose ascending
    sort_idx = np.argsort(dose)
    dose = dose[sort_idx]
    volume = volume[sort_idx]

    if dvh_type == "cumulative":
        # Convert cumulative to differential via finite differences
        # Differential = -d(cumulative)/d(dose)
        if len(volume) > 1:
            # Use negative gradient (volume decreases with dose)
            differential = -np.diff(volume)
            # Pad with zero for last bin
            differential = np.append(differential, 0.0)

            # Normalize differential so integral = 100%
            total_integral = np.sum(differential)
            if total_integral > 0:
                differential = differential / total_integral * 100.0
        else:
            differential = np.array([100.0] if len(volume) == 1 else [])

        # Normalize cumulative to percentage if needed
        cumulative = volume.copy()
        if cumulative[0] > 0:
            if cumulative[0] > 105:  # Absolute volume
                cumulative = cumulative / cumulative[0] * 100.0
            elif cumulative[0] <= 105:  # Likely already percentage
                pass  # Keep as is

        return {"dose": dose, "cumulative": cumulative, "differential": differential}

    elif dvh_type == "differential":
        # Normalize differential so integral = 100%
        total_integral = np.sum(volume)
        if total_integral > 0:
            differential = volume / total_integral * 100.0
        else:
            differential = volume.copy()

        # Reconstruct cumulative DVH ONLY from differential
        # Cumulative at dose D = sum of volumes at doses >= D
        cumulative = np.cumsum(differential[::-1])[::-1]

        return {"dose": dose, "cumulative": cumulative, "differential": differential}

    else:
        # Unknown type - assume cumulative
        cumulative = volume.copy()
        if cumulative[0] > 0 and cumulative[0] > 105:
            cumulative = cumulative / cumulative[0] * 100.0

        differential = np.zeros_like(cumulative)
        if len(cumulative) > 1:
            differential[:-1] = -np.diff(cumulative)

        return {"dose": dose, "cumulative": cumulative, "differential": differential}


def normalize_dvh(dose, volume, dvh_type):
    """
    Normalize DVH: convert differential to cumulative, sort dose axis.

    Always returns cumulative DVH with sorted dose axis.

    Parameters
    ----------
    dose : np.ndarray
        Dose values
    volume : np.ndarray
        Volume values
    dvh_type : str
        'cumulative' or 'differential'

    Returns
    -------
    tuple
        (dose_sorted, volume_cumulative, 'cumulative')
    """
    # Convert to numpy arrays if needed
    dose = np.asarray(dose)
    volume = np.asarray(volume)

    # Sort by dose axis first
    sort_idx = np.argsort(dose)
    dose = dose[sort_idx]
    volume = volume[sort_idx]

    if dvh_type == "differential":
        # Convert differential to cumulative
        # Cumulative at dose D = sum of volumes at doses >= D
        cumulative = np.cumsum(volume[::-1])[::-1]

        # Normalize to percentage if needed
        if cumulative[0] > 0:
            cumulative = cumulative / cumulative[0] * 100.0

        return dose, cumulative, "cumulative"

    # Already cumulative - normalize to percentage if needed
    if volume[0] > 0 and volume[0] <= 105:
        # Likely already percentage, keep as is
        return dose, volume, "cumulative"
    elif volume[0] > 0:
        # Absolute volume - normalize to percentage
        volume = volume / volume[0] * 100.0

    return dose, volume, "cumulative"


def validate_dvh_integrity(dvh_df, dvh_type, structure_name, patient_id):
    """
    Validate DVH integrity (read-only, non-blocking).

    Pure function with no side effects. Returns validation results only.

    Parameters
    ----------
    dvh_df : pd.DataFrame
        DVH data with columns 'Dose[Gy]' and 'Volume[cm3]'
    dvh_type : str
        'cumulative' or 'differential'
    structure_name : str
        Structure name
    patient_id : str
        Patient ID

    Returns
    -------
    dict
        Validation result dictionary with status, failed_checks, warnings
    """
    failed_checks = []
    warnings = []

    if dvh_df is None or len(dvh_df) == 0:
        return {
            "status": "FLAG",
            "failed_checks": ["Empty DVH data"],
            "warnings": [],
            "structure": structure_name,
            "patient_id": patient_id,
            "dvh_type": dvh_type,
        }

    # Check for required columns
    if "Dose[Gy]" not in dvh_df.columns or "Volume[cm3]" not in dvh_df.columns:
        return {
            "status": "FLAG",
            "failed_checks": ["Missing required columns (Dose[Gy] or Volume[cm3])"],
            "warnings": [],
            "structure": structure_name,
            "patient_id": patient_id,
            "dvh_type": dvh_type,
        }

    # CRITICAL: Build canonical DVH first (ensures proper physics)
    doses_raw = dvh_df["Dose[Gy]"].values
    volumes_raw = dvh_df["Volume[cm3]"].values

    # Build canonical DVH (returns both cumulative and differential)
    canonical = build_canonical_dvh(doses_raw, volumes_raw, dvh_type)
    doses = canonical["dose"]
    volumes = canonical["cumulative"]  # Use canonical cumulative for validation
    differential = canonical["differential"]

    # C. Structural Sanity Checks
    if len(dvh_df) <= 10:
        failed_checks.append(f"DVH length too short ({len(dvh_df)} points, minimum 10)")

    if np.any(np.isnan(doses)) or np.any(np.isnan(volumes)):
        failed_checks.append("NaN values found in DVH data")

    if np.any(np.isinf(doses)) or np.any(np.isinf(volumes)):
        failed_checks.append("Infinite values found in DVH data")

    # Check dose axis is strictly increasing (after canonicalization, should always be)
    if len(doses) > 1:
        dose_diff = np.diff(doses)
        if not np.all(dose_diff > 0):
            # This should not happen after canonicalization, but check anyway
            failed_checks.append("Dose axis not strictly increasing after canonicalization")

    # Check differential DVH integral ≈ 100%
    if len(differential) > 0:
        diff_integral = np.sum(differential)
        if not (98 <= diff_integral <= 102):
            warnings.append(f"Differential DVH integral ({diff_integral:.1f}%) not near 100%")

    # Always validate as cumulative (since normalize_dvh always returns cumulative)
    # A. Cumulative DVH Physical Rules (after normalization)
    first_vol = volumes[0] if len(volumes) > 0 else 0
    last_vol = volumes[-1] if len(volumes) > 0 else 0

    # Enforce: Volume range 0-100%
    if first_vol < 0 or first_vol > 105:
        failed_checks.append(f"First volume ({first_vol:.1f}%) outside valid range [0, 100%]")
    elif first_vol > 100:
        warnings.append(f"First volume ({first_vol:.1f}%) exceeds 100%")

    if last_vol < -1 or last_vol > 5:  # Allow small negative due to numerical errors
        warnings.append(f"Last volume ({last_vol:.1f}%) not near 0% (expected: 0-5%)")

    # Enforce: Monotonically non-increasing
    if len(volumes) > 1:
        vol_diff = np.diff(volumes)
        non_increasing_count = np.sum(vol_diff > 1e-6)  # Allow small numerical errors
        if non_increasing_count > len(volumes) * 0.1:  # More than 10% violations
            failed_checks.append(
                f"Volume not monotonically non-increasing ({non_increasing_count} violations)"
            )
        elif non_increasing_count > 0:
            warnings.append(f"Minor non-monotonicity detected ({non_increasing_count} points)")

    # Enforce: Last bin ≈ 0%
    if len(volumes) > 0 and not (0 <= last_vol <= 5):
        warnings.append(f"Last bin volume ({last_vol:.1f}%) not near 0% (expected: 0-5%)")

    # Check first volume is near 100% (for normalized percentage DVH)
    if 95 <= first_vol <= 105:
        if abs(first_vol - 100) > 1:
            warnings.append(f"First volume ({first_vol:.1f}%) not exactly 100%")

    # Note: Differential DVH checks removed - validation now operates on normalized cumulative only

    # Determine overall status (use FLAG instead of FAIL for clarity)
    status = "PASS" if len(failed_checks) == 0 else "FLAG"

    return {
        "status": status,
        "failed_checks": failed_checks,
        "warnings": warnings,
        "structure": structure_name,
        "patient_id": patient_id,
        "dvh_type": dvh_type,
    }
