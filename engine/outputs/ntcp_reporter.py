"""NTCP benchmarking Excel workbook with OAR-level summary."""

from __future__ import annotations

import pathlib

import pandas as pd


def build_ntcp_table(ntcp_results: list[dict]) -> pd.DataFrame:
    """Flatten NTCP dictionaries to per-patient per-OAR rows."""
    rows = []
    for r in ntcp_results:
        mc_ll = r.get("uNTCP_LKB_loglogit") or {}
        mc_pb = r.get("uNTCP_LKB_probit") or {}
        mc_rs = r.get("uNTCP_RS") or {}
        rows.append(
            {
                "AnonPatientID": r.get("AnonPatientID", ""),
                "Site": r.get("site", ""),
                "OAR": r.get("structure", ""),
                "gEUD_Gy": r.get("gEUD_gy", float("nan")),
                "Dmax_Gy": r.get("Dmax_gy", float("nan")),
                "Dmean_Gy": r.get("Dmean_gy", float("nan")),
                "bDVH_Applied": r.get("bdvh_applied", False),
                "DPF_plan_Gy": r.get("dose_per_fraction_plan_gy", float("nan")),
                "NTCP_LKB_loglogit": r.get("NTCP_LKB_loglogit", float("nan")),
                "NTCP_LKB_probit": r.get("NTCP_LKB_probit", float("nan")),
                "NTCP_RS": r.get("NTCP_RS", float("nan")),
                "uNTCP_loglogit_mean": mc_ll.get("mean", float("nan")),
                "uNTCP_loglogit_P5": mc_ll.get("p5", float("nan")),
                "uNTCP_loglogit_P95": mc_ll.get("p95", float("nan")),
                "uNTCP_probit_mean": mc_pb.get("mean", float("nan")),
                "uNTCP_probit_P5": mc_pb.get("p5", float("nan")),
                "uNTCP_probit_P95": mc_pb.get("p95", float("nan")),
                "uNTCP_RS_mean": mc_rs.get("mean", float("nan")),
                "uNTCP_RS_P5": mc_rs.get("p5", float("nan")),
                "uNTCP_RS_P95": mc_rs.get("p95", float("nan")),
            }
        )
    return pd.DataFrame(rows)


def save_ntcp_excel(
    ntcp_results: list[dict],
    output_path: str | pathlib.Path,
    quantec_df: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Save NTCP summary workbook, bDVH subset, and optional QUANTEC flags."""
    ntcp_df = build_ntcp_table(ntcp_results)
    bdvh_df = ntcp_df[ntcp_df["bDVH_Applied"] == True][
        ["AnonPatientID", "Site", "OAR", "DPF_plan_Gy", "NTCP_LKB_loglogit", "uNTCP_loglogit_mean"]
    ].copy()
    if quantec_df is None:
        from validation.quantec_checker import check_cohort_quantec

        quantec_df = check_cohort_quantec(ntcp_results)

    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        ntcp_df.to_excel(writer, sheet_name="NTCP_Summary", index=False)
        bdvh_df.to_excel(writer, sheet_name="bDVH_Corrected", index=False)
        quantec_df.to_excel(writer, sheet_name="QUANTEC_Flags", index=False)
        for sname in writer.sheets:
            ws = writer.sheets[sname]
            for col in ws.columns:
                max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)
    return out
