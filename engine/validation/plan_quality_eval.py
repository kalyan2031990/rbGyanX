"""Evaluate physical dose metrics against site plan-quality index packs."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config.plan_quality import get_site_pack


def _metric_value(row: dict, metric: str) -> float | None:
    val = row.get(metric)
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def evaluate_plan_quality_flags(
    physical_rows: list[dict],
    user_config: Any = None,
) -> pd.DataFrame:
    """Return one row per triggered check (WARNING / INFO)."""
    flags: list[dict] = []
    for row in physical_rows:
        site_key = row.get("site_params_key") or row.get("site") or "DEFAULT"
        profile = row.get("technique_profile") or "conventional"
        pack_key, pack = get_site_pack(site_key, profile, user_config)
        checks = pack.get("checks") or []
        role = row.get("structure_role") or ""
        rx = float(row.get("prescription_gy") or 0.0)
        for chk in checks:
            if chk.get("role") and chk["role"] != role:
                continue
            metric = chk.get("metric")
            if not metric:
                continue
            val = _metric_value(row, metric)
            if val is None:
                continue
            triggered = False
            detail = ""
            if "min_percent_rx" in chk and rx > 0:
                threshold = rx * float(chk["min_percent_rx"]) / 100.0
                if val < threshold:
                    triggered = True
                    detail = f"{metric}={val:.2f} Gy < {chk['min_percent_rx']}% of Rx ({threshold:.2f} Gy)"
            if "max_value" in chk and val > float(chk["max_value"]):
                triggered = True
                detail = f"{metric}={val:.3f} > max {chk['max_value']}"
            if "min_value" in chk and val < float(chk["min_value"]):
                triggered = True
                detail = f"{metric}={val:.3f} < min {chk['min_value']}"
            if not triggered:
                continue
            flags.append(
                {
                    "AnonPatientID": row.get("AnonPatientID"),
                    "site_pack": pack_key,
                    "technique_profile": profile,
                    "structure": row.get("structure"),
                    "structure_role": role,
                    "metric": metric,
                    "value": val,
                    "Severity": chk.get("severity", "WARNING"),
                    "Detail": detail,
                }
            )
    return pd.DataFrame(flags)


def filter_report_columns(
    df: pd.DataFrame,
    site_params_key: str,
    technique_profile: str,
    user_config: Any = None,
) -> pd.DataFrame:
    """Keep index-pack metrics plus identifiers for Target/OAR summary sheets."""
    if df.empty:
        return df
    _, pack = get_site_pack(site_params_key, technique_profile, user_config)
    report = pack.get("report_metrics") or {}
    keep = {
        "AnonPatientID",
        "site",
        "site_params_key",
        "technique_profile",
        "index_pack",
        "structure",
        "structure_role",
        "raw_structure_name",
        "prescription_gy",
        "total_volume_cc",
        "dose_per_fraction_gy",
        "number_of_fractions",
    }
    for role_metrics in report.values():
        if isinstance(role_metrics, list):
            keep.update(role_metrics)
    cols = [c for c in df.columns if c in keep]
    return df[cols] if cols else df
