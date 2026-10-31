"""Orchestrate classical NTCP models per OAR."""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from config.site_ntcp_params import OrganNTCPParams
from radiobiology import dvh_object_to_dataframe
from radiobiology.bdvh import compute_eqd2_dvh, get_alpha_beta_for_organ
from radiobiology.geud_tcp import compute_geud
from radiobiology.model_registry import iter_ntcp_models, register_ntcp_model  # noqa: F401
from radiobiology.ntcp import (
    calculate_ntcp_lkb_loglogit,
    calculate_ntcp_lkb_probit,
    calculate_ntcp_rs_poisson,
)

logger = logging.getLogger(__name__)


def _volume_column(dvh_df: pd.DataFrame) -> str:
    for col in ("volume_cm3", "volume_frac", "volume"):
        if col in dvh_df.columns:
            return col
    raise KeyError("volume")


def _dvh_metrics(dvh_df: pd.DataFrame) -> dict[str, float]:
    if dvh_df is None or dvh_df.empty:
        return {"max_dose": math.nan, "v_effective": math.nan, "mean_dose": math.nan}
    dose_col = "dose_gy" if "dose_gy" in dvh_df.columns else "dose"
    vol_col = _volume_column(dvh_df)
    doses = dvh_df[dose_col].astype(float)
    vols = dvh_df[vol_col].astype(float)
    total = vols.sum()
    if total <= 0:
        logger.warning(
            "DVH for NTCP has zero total volume — returning NaN metrics. "
            "Check OAR contour export."
        )
        return {"max_dose": math.nan, "v_effective": math.nan, "mean_dose": math.nan}
    return {
        "max_dose": float(doses.max()),
        "mean_dose": float((doses * vols).sum() / total),
        "v_effective": float(total),
    }


class NTCPCalculator:
    """Compute LKB and RS NTCP for one OAR DVH."""

    def compute_all(
        self,
        dvh_result: Any,
        plan_metadata: dict,
        organ_params: OrganNTCPParams,
        site_key: str,
    ) -> dict:
        dvh_df = dvh_object_to_dataframe(getattr(dvh_result, "dvh_object", None))
        canonical = getattr(dvh_result, "canonical_name", organ_params.canonical)
        n_fractions_plan = int(plan_metadata.get("n_fractions", 1) or 1)
        # Defect #4/#5: this used to default to 2.0 Gy/fraction when the export said nothing,
        # which quietly decided that no EQD2 conversion was needed. An unstated fractionation is
        # now NaN, so the EQD2 transform is skipped and the NTCP is reported on physical dose,
        # with bdvh_applied False and the reason on the row.
        dpf_raw = plan_metadata.get("dose_per_fraction_gy")
        dpf_plan = float(dpf_raw) if dpf_raw is not None else math.nan
        fractionation_known = math.isfinite(dpf_plan) and dpf_plan > 0

        bdvh_applied = False
        dvh_for_ntcp = dvh_df
        if (
            fractionation_known
            and abs(dpf_plan - 2.0) > 0.3
            and n_fractions_plan >= 1
            and not dvh_df.empty
        ):
            alpha_beta_oar = get_alpha_beta_for_organ(
                canonical, organ_params_alpha_beta=organ_params.alpha_beta_gy
            )
            dvh_for_ntcp = compute_eqd2_dvh(dvh_df, n_fractions_plan, alpha_beta_oar)
            bdvh_applied = True

        metrics = _dvh_metrics(dvh_for_ntcp)
        geud = (
            compute_geud(dvh_for_ntcp, organ_params.geud_a)
            if not dvh_for_ntcp.empty and not math.isnan(metrics.get("mean_dose", math.nan))
            else math.nan
        )

        row: dict = {
            "structure": canonical,
            "site": site_key,
            "gEUD_gy": geud,
            "Dmax_gy": metrics["max_dose"],
            "Dmean_gy": metrics["mean_dose"],
            "NTCP_LKB_loglogit": math.nan,
            "NTCP_LKB_probit": math.nan,
            "NTCP_RS": math.nan,
            "bdvh_applied": bdvh_applied,
            "n_fractions_plan": n_fractions_plan,
            "dose_per_fraction_plan_gy": dpf_plan,
            # "physical" when the export did not state its fractionation, so no EQD2 transform
            # could be applied (#4/#5); "eqd2" when it was, "physical_2gy_equivalent" when the
            # plan is already at 2 Gy/fraction and the transform would be the identity.
            "ntcp_dose_basis": (
                "eqd2"
                if bdvh_applied
                else ("physical_2gy_equivalent" if fractionation_known else "physical")
            ),
        }

        if organ_params.lkb_loglogit and not math.isnan(geud):
            p = organ_params.lkb_loglogit
            row["NTCP_LKB_loglogit"] = calculate_ntcp_lkb_loglogit(
                geud, float(p["TD50_gy"]), float(p["gamma50"])
            )
        if organ_params.lkb_probit and not math.isnan(geud):
            p = organ_params.lkb_probit
            n_lkb = float(p["n"])
            geud_probit = compute_geud(dvh_for_ntcp, a=1.0 / n_lkb) if n_lkb > 0 else math.nan
            row["NTCP_LKB_probit"] = calculate_ntcp_lkb_probit(
                geud_probit,
                float(p["TD50_gy"]),
                float(p["m"]),
            )
            row["gEUD_probit_gy"] = geud_probit
        if organ_params.rs and not dvh_for_ntcp.empty:
            p = organ_params.rs
            row["NTCP_RS"] = calculate_ntcp_rs_poisson(
                dvh_for_ntcp,
                float(p["D50_gy"]),
                float(p["gamma"]),
                float(p["s"]),
            )
        if not dvh_for_ntcp.empty:
            from dicom_io.dvh_shape_features import compute_dvh_shape_features

            organ_name = getattr(organ_params, "canonical", None) or str(
                getattr(organ_params, "name", "")
            )
            row.update(compute_dvh_shape_features(dvh_for_ntcp, organ_name))
        for model_name, model_instance in iter_ntcp_models().items():
            try:
                ext = model_instance.compute_ntcp_dvh(dvh_for_ntcp, organ_params, n_fractions_plan)
                row[f"NTCP_{model_name}"] = float(ext.get("ntcp", math.nan))
            except Exception as exc:
                logger.warning("Registered NTCP model %s failed: %s", model_name, exc)
        row["_dvh_df"] = dvh_for_ntcp
        return row
