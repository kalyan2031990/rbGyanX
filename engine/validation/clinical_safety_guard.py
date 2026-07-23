"""
Clinical Safety Guard — pre-reporting gate for ML-derived TCP/NTCP predictions.

TRIPOD (Collins et al. BMJ 2015) + Harrell predictive modelling guidelines.
Annotates results; does NOT block output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class SafetyCheck:
    criterion: str
    passed: bool
    actual: float | None
    threshold: float | None
    message: str
    severity: str


@dataclass
class SafetyReport:
    model_name: str
    overall_status: str
    checks: list[SafetyCheck] = field(default_factory=list)

    def annotation(self) -> str:
        if self.overall_status == "PASS":
            return f"[VALIDATED — {self.model_name}]"
        if self.overall_status == "WARN":
            return f"[USE WITH CAUTION — {self.model_name}]"
        return f"[UNRELIABLE — DO NOT REPORT — {self.model_name}]"


def run_safety_checks(
    model_name: str,
    auc: float,
    cv_auc: float | None = None,
    overfitting_index: float | None = None,
    calibration_slope: float | None = None,
    epv: float | None = None,
    n_patients: int = 0,
    synthetic_data_used: bool = False,
) -> SafetyReport:
    """Safety checklist using TRIPOD + Harrell criteria."""
    checks: list[SafetyCheck] = []
    n_fail = n_warn = 0

    def _add(criterion, passed, actual, threshold, msg, sev):
        nonlocal n_fail, n_warn
        checks.append(
            SafetyCheck(criterion, passed, actual, threshold, msg, sev)
        )
        if sev == "FAIL":
            n_fail += 1
        elif sev == "WARN":
            n_warn += 1

    if math.isfinite(auc):
        if auc <= 0.55:
            _add(
                "AUC",
                False,
                auc,
                0.60,
                f"AUC={auc:.3f} ≤ 0.55: not better than chance.",
                "FAIL",
            )
        elif auc <= 0.65:
            _add(
                "AUC",
                True,
                auc,
                0.65,
                f"AUC={auc:.3f}: marginally above chance.",
                "WARN",
            )
        else:
            _add("AUC", True, auc, 0.60, f"AUC={auc:.3f}: acceptable.", "INFO")

    if overfitting_index is not None and math.isfinite(overfitting_index):
        if overfitting_index > 0.20:
            _add(
                "Overfitting",
                False,
                overfitting_index,
                0.20,
                f"Index={overfitting_index:.3f} > 0.20: likely overfit.",
                "FAIL",
            )
        elif overfitting_index > 0.10:
            _add(
                "Overfitting",
                True,
                overfitting_index,
                0.10,
                f"Index={overfitting_index:.3f}: borderline.",
                "WARN",
            )
        else:
            _add(
                "Overfitting",
                True,
                overfitting_index,
                0.10,
                f"Index={overfitting_index:.3f}: acceptable.",
                "INFO",
            )

    if calibration_slope is not None and math.isfinite(calibration_slope):
        if calibration_slope < 0.50 or calibration_slope > 2.0:
            _add(
                "CalibSlope",
                False,
                calibration_slope,
                None,
                f"Slope={calibration_slope:.3f}: severe miscalibration.",
                "FAIL",
            )
        elif not (0.70 <= calibration_slope <= 1.30):
            _add(
                "CalibSlope",
                True,
                calibration_slope,
                None,
                f"Slope={calibration_slope:.3f}: moderate miscalibration.",
                "WARN",
            )
        else:
            _add(
                "CalibSlope",
                True,
                calibration_slope,
                None,
                f"Slope={calibration_slope:.3f}: acceptable.",
                "INFO",
            )

    if epv is not None and math.isfinite(epv):
        if epv < 5.0:
            _add(
                "EPV",
                False,
                epv,
                10.0,
                f"EPV={epv:.1f} < 5: critically underpowered.",
                "FAIL",
            )
        elif epv < 10.0:
            _add(
                "EPV", True, epv, 10.0, f"EPV={epv:.1f}: borderline (5–10).", "WARN"
            )
        else:
            _add("EPV", True, epv, 10.0, f"EPV={epv:.1f}: sufficient.", "INFO")

    if n_patients < 20:
        _add(
            "SampleSize",
            False,
            float(n_patients),
            30.0,
            f"n={n_patients} < 20: too small for ML.",
            "FAIL",
        )
    elif n_patients < 30:
        _add(
            "SampleSize",
            True,
            float(n_patients),
            30.0,
            f"n={n_patients}: borderline (20–30).",
            "WARN",
        )

    if synthetic_data_used:
        _add(
            "SyntheticData",
            False,
            None,
            None,
            "Synthetic/augmented data: NEVER report ML metrics from synthetic cohorts.",
            "FAIL",
        )

    status = "FAIL" if n_fail > 0 else ("WARN" if n_warn > 0 else "PASS")
    return SafetyReport(model_name=model_name, overall_status=status, checks=checks)
