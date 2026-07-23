"""Per-cohort PDF summary (physical + radiobiology pointers)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd


def _fmt(val: Any, digits: int = 2) -> str:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(f):
        return "—"
    return f"{f:.{digits}f}"


def save_patient_summary_pdf(
    output_dir: Path,
    physical_rows: list[dict] | None = None,
    tcp_results: list[dict] | None = None,
    ntcp_results: list[dict] | None = None,
    quantec_df: pd.DataFrame | None = None,
) -> Path:
    """Write ``patient_plan_summary.pdf`` into *output_dir*."""
    output_dir = Path(output_dir)
    pdf_path = output_dir / "patient_plan_summary.pdf"

    phys_df = pd.DataFrame(physical_rows or [])
    tcp_df = pd.DataFrame(
        [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in (tcp_results or [])]
    )
    ntcp_df = pd.DataFrame(
        [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in (ntcp_results or [])]
    )

    patients: list[str] = []
    for df in (phys_df, tcp_df, ntcp_df):
        if not df.empty and "AnonPatientID" in df.columns:
            patients.extend(df["AnonPatientID"].astype(str).tolist())
    patient_ids = sorted(set(patients))

    with PdfPages(pdf_path) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.1, 0.92, "rbGyanX — Plan summary (physical + radiobiology)", fontsize=14, weight="bold")
        fig.text(
            0.1,
            0.86,
            f"Patients: {len(patient_ids)} | Outputs: {output_dir.name}",
            fontsize=10,
        )
        fig.text(
            0.1,
            0.80,
            "Physical: plan_quality_summary.xlsx | TCP: tcp_benchmarking.xlsx | "
            "NTCP: ntcp_benchmarking.xlsx",
            fontsize=9,
        )
        if quantec_df is not None and not quantec_df.empty:
            n_v = int((quantec_df.get("Severity", pd.Series()) == "VIOLATION").sum())
            n_w = int((quantec_df.get("Severity", pd.Series()) == "WARNING").sum())
            fig.text(0.1, 0.74, f"QUANTEC: {n_v} violation(s), {n_w} warning(s)", fontsize=10)
        ax = fig.add_subplot(111)
        ax.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        for pid in patient_ids:
            fig = plt.figure(figsize=(8.5, 11))
            y = 0.94
            fig.text(0.1, y, f"Patient: {pid}", fontsize=13, weight="bold")
            y -= 0.05

            if not phys_df.empty:
                sub = phys_df[phys_df["AnonPatientID"].astype(str) == pid]
                if not sub.empty:
                    fig.text(0.1, y, "Physical dose (selected)", fontsize=11, weight="bold")
                    y -= 0.04
                    for _, row in sub.iterrows():
                        role = row.get("structure_role", "")
                        name = row.get("structure", "")
                        line = (
                            f"  {name} ({role}): D95={_fmt(row.get('D95_gy'))} Gy, "
                            f"Dmean={_fmt(row.get('Dmean_gy'))} Gy, "
                            f"ID={_fmt(row.get('integral_dose_gy_cm3'), 1)} Gy·cm³"
                        )
                        if role == "TARGET":
                            line += f", HI={_fmt(row.get('HI'), 3)}, CI={_fmt(row.get('CI'), 3)}"
                        fig.text(0.1, y, line, fontsize=8, family="monospace")
                        y -= 0.035
                        if y < 0.12:
                            break
                    y -= 0.02

            if not tcp_df.empty:
                tsub = tcp_df[tcp_df["AnonPatientID"].astype(str) == pid]
                if not tsub.empty:
                    fig.text(0.1, y, "TCP / UTCP", fontsize=11, weight="bold")
                    y -= 0.04
                    for _, row in tsub.iterrows():
                        tcp_val = row.get("TCP_Poisson", row.get("TCP_mean", row.get("TCP")))
                        utcp = row.get("UTCP")
                        tgt = row.get("TargetType", row.get("target_type", "target"))
                        fig.text(
                            0.1,
                            y,
                            f"  {tgt}: TCP={_fmt(tcp_val, 3)}"
                            + (f", UTCP={_fmt(utcp, 3)}" if utcp is not None else ""),
                            fontsize=8,
                            family="monospace",
                        )
                        y -= 0.035

            if not ntcp_df.empty:
                nsub = ntcp_df[ntcp_df["AnonPatientID"].astype(str) == pid]
                if not nsub.empty:
                    fig.text(0.1, y, "NTCP (top OARs)", fontsize=11, weight="bold")
                    y -= 0.04
                    oar_col = "OAR" if "OAR" in nsub.columns else "structure"
                    ntcp_col = next(
                        (c for c in ("NTCP_LKB_loglogit", "NTCP_RS", "NTCP") if c in nsub.columns),
                        None,
                    )
                    if oar_col and ntcp_col:
                        nsub = nsub.copy()
                        nsub["_ntcp"] = pd.to_numeric(nsub[ntcp_col], errors="coerce")
                        for _, row in nsub.nlargest(5, "_ntcp").iterrows():
                            fig.text(
                                0.1,
                                y,
                                f"  {row[oar_col]}: NTCP={_fmt(row['_ntcp'], 3)}",
                                fontsize=8,
                                family="monospace",
                            )
                            y -= 0.035

            fig.text(
                0.1,
                0.04,
                "Decision support only — verify against TPS and institutional protocols.",
                fontsize=7,
                style="italic",
            )
            ax = fig.add_subplot(111)
            ax.axis("off")
            pdf.savefig(fig)
            plt.close(fig)

    return pdf_path
