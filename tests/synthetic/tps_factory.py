"""Generate TPS-style DVH text exports for pipeline e2e tests (PHI-free)."""

from __future__ import annotations

from pathlib import Path


def write_ptv_dvh(
    out_dir: Path,
    patient_id: str = "SYN-001",
    prescription_cgy: float = 7000.0,
) -> Path:
    """Uniform-ish PTV cumulative DVH (Eclipse-style header)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    content = f"""\
Patient ID           : {patient_id}
Prescribed dose [cGy]: {prescription_cgy}
Mean Dose [cGy]: {prescription_cgy + 100}
Structure: PTV70
Number of fractions: 35
Dose per fraction [cGy]: 200

Dose [cGy]  Structure Volume [cm³]
{prescription_cgy:.0f}  100.0
{prescription_cgy - 1000:.0f}  95.0
{prescription_cgy - 2000:.0f}  80.0
{prescription_cgy - 3000:.0f}  50.0
"""
    path = out_dir / f"{patient_id}_PTV_dvh.txt"
    path.write_text(content, encoding="utf-8")
    return path


def write_parotid_dvh(
    out_dir: Path,
    patient_id: str = "SYN-001",
    mean_cgy: float = 2600.0,
) -> Path:
    """OAR differential-style DVH for NTCP path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    content = f"""\
Patient ID           : {patient_id}
Mean Dose [cGy]: {mean_cgy}
Structure: Parotid_L
Number of fractions: 35
Dose per fraction [cGy]: 200

Dose [cGy]  Structure Volume [cm³]
1000  5.0
2000  15.0
{mean_cgy:.0f}  40.0
4000  30.0
5000  10.0
"""
    path = out_dir / f"{patient_id}_Parotid_L_dvh.txt"
    path.write_text(content, encoding="utf-8")
    return path


def write_synthetic_cohort(out_dir: Path) -> dict[str, list[Path]]:
    """One patient with PTV + Parotid DVH files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pid = "SYN-001"
    return {
        "patient_id": pid,
        "files": [
            write_ptv_dvh(out_dir, pid),
            write_parotid_dvh(out_dir, pid),
        ],
    }
