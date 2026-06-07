"""Physical dose metrics and plan-quality Excel/CSV outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from validation.plan_quality_eval import evaluate_plan_quality_flags, filter_report_columns


def save_physical_outputs(
    physical_rows: list[dict],
    output_dir: Path,
    user_config: Any = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(physical_rows)
    csv_path = output_dir / "physical_dose_metrics.csv"
    df.to_csv(csv_path, index=False)

    flags_df = evaluate_plan_quality_flags(physical_rows, user_config)
    flags_path = output_dir / "plan_quality_flags.csv"
    flags_df.to_csv(flags_path, index=False)

    xlsx_path = output_dir / "plan_quality_summary.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        if not df.empty:
            targets = df[df["structure_role"] == "TARGET"].copy()
            oars = df[df["structure_role"] == "OAR"].copy()
            integral = df[
                ["AnonPatientID", "structure", "structure_role", "total_volume_cc", "integral_dose_gy_cm3"]
            ].copy()

            for subset, sheet, site_col in (
                (targets, "Target_Indices", "site_params_key"),
                (oars, "OAR_Indices", "site_params_key"),
            ):
                if subset.empty:
                    pd.DataFrame().to_excel(writer, sheet_name=sheet, index=False)
                    continue
                rows_out = []
                for (patient, site, profile), grp in subset.groupby(
                    ["AnonPatientID", site_col, "technique_profile"]
                ):
                    filtered = filter_report_columns(grp, str(site), str(profile), user_config)
                    rows_out.append(filtered)
                out = pd.concat(rows_out, ignore_index=True) if rows_out else subset
                out.to_excel(writer, sheet_name=sheet, index=False)

            integral.to_excel(writer, sheet_name="Integral_Dose", index=False)

            pack_rows = (
                df[["AnonPatientID", "site_params_key", "technique_profile", "index_pack"]]
                .drop_duplicates()
                .sort_values(["AnonPatientID", "site_params_key"])
            )
            pack_rows.to_excel(writer, sheet_name="Index_Pack_Used", index=False)
        else:
            pd.DataFrame({"note": ["No physical metrics"]}).to_excel(
                writer, sheet_name="Target_Indices", index=False
            )

        if not flags_df.empty:
            flags_df.to_excel(writer, sheet_name="Plan_Quality_Flags", index=False)
        else:
            pd.DataFrame(
                columns=[
                    "AnonPatientID",
                    "site_pack",
                    "technique_profile",
                    "structure",
                    "metric",
                    "Severity",
                    "Detail",
                ]
            ).to_excel(writer, sheet_name="Plan_Quality_Flags", index=False)

    return {
        "physical_dose_metrics_csv": csv_path,
        "plan_quality_flags_csv": flags_path,
        "plan_quality_summary_xlsx": xlsx_path,
    }
