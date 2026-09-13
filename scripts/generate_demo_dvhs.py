"""
Generate the shipped SYNTHETIC demo DVHs (examples/data/dvh_txt).

Real TPS DVHs have hundreds of dose bins and smooth shoulders. These are generated analytically
at 1 Gy resolution as physically valid CUMULATIVE curves — dose ascending, volume monotonically
non-increasing, ending at exactly 0 — so the shipped examples are a positive control for the
reader/validator, not a liability. No patient data: every curve is a closed-form function.

Format matches the commercial-TPS text export the reader expects (cGy dose column, cm^3 volume).
"""

from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "examples" / "data" / "dvh_txt"

# Per-patient multiplicative variation so EX-001..004 differ but stay realistic.
PATIENTS = {
    "EX-001": {"dose": 1.00, "vol": 1.00},
    "EX-002": {"dose": 0.97, "vol": 1.08},
    "EX-003": {"dose": 1.03, "vol": 0.92},
    "EX-004": {"dose": 0.99, "vol": 1.15},
}


def _logistic_survival(d: float, d50: float, width: float) -> float:
    """Cumulative survival S(d) = V(>=d)/V0 for a PTV-like curve (flat then steep fall)."""
    return 1.0 / (1.0 + math.exp((d - d50) / width))


def _erfc_survival(d: float, centre: float, scale: float) -> float:
    """Smooth OAR survival S(d): ~1 at low dose, monotone fall to 0. Mean dose ≈ centre."""
    return 0.5 * math.erfc((d - centre) / (math.sqrt(2.0) * scale))


def _curve(kind: str, dose_scale: float, dmax: int) -> list[tuple[int, float]]:
    """Return [(dose_Gy, survival_frac)] at 1 Gy bins, ending at 0."""
    pts: list[tuple[int, float]] = []
    for d in range(0, dmax + 1):
        if kind == "ptv":
            s = _logistic_survival(d, 71.5 * dose_scale, 1.2)
        elif kind == "parotid_l":
            s = _erfc_survival(d, 24.0 * dose_scale, 9.0)
        elif kind == "parotid_r":
            s = _erfc_survival(d, 22.0 * dose_scale, 9.0)
        elif kind == "cord":
            s = _erfc_survival(d, 17.0 * dose_scale, 8.0)
        else:  # pragma: no cover
            raise ValueError(kind)
        pts.append((d, max(0.0, min(1.0, s))))
    # Force the tail to exactly zero so the curve ends at 0 volume.
    while pts and pts[-1][1] < 5e-4:
        pts.pop()
    pts.append((pts[-1][0] + 1, 0.0))
    return pts


def _mean_dose_gy(pts: list[tuple[int, float]]) -> float:
    """Mean dose = ∫ S(d) dd (trapezoid) for a cumulative survival curve normalised to 1 at d=0."""
    s0 = pts[0][1] or 1.0
    area = 0.0
    for (d0, v0), (d1, v1) in zip(pts, pts[1:], strict=False):
        area += 0.5 * (v0 + v1) / s0 * (d1 - d0)
    return area


STRUCTS = [
    ("PTV70", "ptv", 78, 100.0, True),
    ("Parotid_L", "parotid_l", 60, 30.0, False),
    ("Parotid_R", "parotid_r", 60, 30.0, False),
    ("SpinalCord", "cord", 50, 30.0, False),
]


def _write(pid: str, struct: str, kind: str, dmax: int, v0: float, is_ptv: bool) -> None:
    p = PATIENTS[pid]
    pts = _curve(kind, p["dose"], dmax)
    vol0 = v0 * p["vol"]
    mean_gy = _mean_dose_gy(pts)
    lines = [f"Patient ID          : {pid}"]
    if is_ptv:
        lines.append(f"Prescribed dose [cGy]: {round(7000 * p['dose'])}")
    lines += [
        f"Mean Dose [cGy]: {round(mean_gy * 100)}",
        f"Structure: {struct}",
        "Number of fractions: 35",
        "Dose per fraction [cGy]: 200",
        "SYNTHETIC - analytically generated demo DVH (no patient data)",
        "",
        "Dose [cGy]  Structure Volume [cm3]",
    ]
    for d_gy, s in pts:
        lines.append(f"{d_gy * 100}  {vol0 * s:.4f}")
    (OUT / f"{pid}_{struct}_dvh.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for pid in PATIENTS:
        for struct, kind, dmax, v0, is_ptv in STRUCTS:
            _write(pid, struct, kind, dmax, v0, is_ptv)
            n += 1
    print(f"wrote {n} synthetic DVH files to {OUT}")


if __name__ == "__main__":
    main()
