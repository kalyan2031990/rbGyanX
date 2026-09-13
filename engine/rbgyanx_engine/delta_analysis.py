"""ΔNTCP / ΔTCP plan comparison (two DICOM plan directories)."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import pandas as pd

from rbgyanx_engine.engine import run_analysis
from rbgyanx_engine.run_config import RunConfig

logger = logging.getLogger(__name__)

DELTA_NTCP_THRESHOLD_PCT = 5.0


def compare_plans(
    plan_a_dir: Path,
    plan_b_dir: Path,
    output_dir: Path,
    plan_a_label: str = "Plan_A",
    plan_b_label: str = "Plan_B",
    site: str | None = None,
    delta_threshold_pct: float = DELTA_NTCP_THRESHOLD_PCT,
    no_uncertainty: bool = True,
) -> tuple[pd.DataFrame, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg_a = RunConfig(
        endpoint="both",
        input_kind="dicom",
        input_dir=Path(plan_a_dir),
        output_dir=output_dir / "plan_a",
        site=site,
        no_uncertainty=no_uncertainty,
        cohort=True,
    )
    cfg_b = RunConfig(
        endpoint="both",
        input_kind="dicom",
        input_dir=Path(plan_b_dir),
        output_dir=output_dir / "plan_b",
        site=site,
        no_uncertainty=no_uncertainty,
        cohort=True,
    )

    logger.info("Running engine for %s ...", plan_a_label)
    result_a = run_analysis(cfg_a)
    logger.info("Running engine for %s ...", plan_b_label)
    result_b = run_analysis(cfg_b)

    if not result_a.ntcp_results or not result_b.ntcp_results:
        logger.warning("No NTCP results for one or both plans.")
        out_path = output_dir / "delta_ntcp.xlsx"
        pd.DataFrame().to_excel(out_path, index=False)
        return pd.DataFrame(), out_path

    df_a = pd.DataFrame(result_a.ntcp_results).rename(
        columns={
            "NTCP_LKB_loglogit": "NTCP_LKB_loglogit_A",
            "NTCP_LKB_probit": "NTCP_LKB_probit_A",
            "NTCP_RS": "NTCP_RS_A",
        }
    )
    df_b = pd.DataFrame(result_b.ntcp_results).rename(
        columns={
            "NTCP_LKB_loglogit": "NTCP_LKB_loglogit_B",
            "NTCP_LKB_probit": "NTCP_LKB_probit_B",
            "NTCP_RS": "NTCP_RS_B",
        }
    )
    merge_keys = ["AnonPatientID", "structure", "site"]
    delta = df_a[
        merge_keys + ["NTCP_LKB_loglogit_A", "NTCP_LKB_probit_A", "NTCP_RS_A"]
    ].merge(
        df_b[merge_keys + ["NTCP_LKB_loglogit_B", "NTCP_LKB_probit_B", "NTCP_RS_B"]],
        on=merge_keys,
        how="outer",
    )
    delta["delta_NTCP_loglogit_pct"] = (
        (delta["NTCP_LKB_loglogit_A"] - delta["NTCP_LKB_loglogit_B"]) * 100
    ).round(2)

    def _recommend(row):
        d = row.get("delta_NTCP_loglogit_pct", math.nan)
        if math.isnan(d):
            return "review"
        if d > delta_threshold_pct:
            return f"prefer_{plan_b_label}"
        if d < -delta_threshold_pct:
            return f"prefer_{plan_a_label}"
        return "equivalent"

    delta["recommendation"] = delta.apply(_recommend, axis=1)
    delta["plan_a_label"] = plan_a_label
    delta["plan_b_label"] = plan_b_label

    if result_a.tcp_results and result_b.tcp_results:
        tcp_a = pd.DataFrame(result_a.tcp_results)[
            ["AnonPatientID", "TCP_Poisson", "TCP_mean", "UTCP"]
        ].rename(columns={"TCP_Poisson": "TCP_Poisson_A", "TCP_mean": "TCP_mean_A", "UTCP": "UTCP_A"})
        tcp_b = pd.DataFrame(result_b.tcp_results)[
            ["AnonPatientID", "TCP_Poisson", "TCP_mean", "UTCP"]
        ].rename(columns={"TCP_Poisson": "TCP_Poisson_B", "TCP_mean": "TCP_mean_B", "UTCP": "UTCP_B"})
        tcp_delta = tcp_a.merge(tcp_b, on="AnonPatientID", how="outer")
        tcp_delta["delta_TCP_mean"] = (tcp_delta["TCP_mean_A"] - tcp_delta["TCP_mean_B"]).round(4)
        tcp_delta.to_excel(output_dir / "delta_tcp.xlsx", index=False)

    out_path = output_dir / "delta_ntcp.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        delta.to_excel(xw, sheet_name="delta_NTCP", index=False)
    logger.info("ΔNTCP comparison written to %s", out_path)
    return delta, out_path
