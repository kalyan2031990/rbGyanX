"""Orchestrate classical NTCP models per OAR."""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from config.site_ntcp_params import (
    ILLUSTRATIVE_PARAMS_IN_BASIC_MODE,
    MODEL_KEYS,
    OrganNTCPParams,
)
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

#: Which attribute of OrganNTCPParams holds each model's values.
_MODEL_ATTR = {"LKB_loglogit": "lkb_loglogit", "LKB_probit": "lkb_probit", "RS": "rs"}


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
        mode: str = "advanced",
    ) -> dict:
        """Classical NTCP for one OAR.

        ``mode`` is the run mode. In ``"basic"`` a model whose parameters have no published
        source is refused rather than computed: the column is NaN and the row carries
        ``ILLUSTRATIVE_PARAMS_IN_BASIC_MODE``. ADVANCED computes it and labels it.
        """
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
        alpha_beta_oar = math.nan
        dvh_for_ntcp = dvh_df
        # Defect #63: this used to skip the EQD2 transform whenever the PLAN was near 2 Gy per
        # fraction (|dpf_plan - 2| <= 0.3), on the grounds that the transform is "the identity".
        # It is the identity only for a bin that is itself at 2 Gy per fraction, and a DVH is not
        # one dose. In a 70 Gy / 35 fraction plan a larynx bin at 35 Gy receives 1 Gy per
        # fraction, which is 28 Gy EQD2 at alpha/beta = 3 -- a 20 % shift, in the direction that
        # matters. The published fits these parameters come from (Rancati larynx, Bakhshandeh
        # thyroid) were made on EQD2 DVHs, so skipping the transform scored those organs on
        # physical dose against EQD2 parameters. The conversion now runs whenever the
        # fractionation is known, which is the only condition it ever needed.
        if fractionation_known and n_fractions_plan >= 1 and not dvh_df.empty:
            alpha_beta_oar = get_alpha_beta_for_organ(
                canonical, organ_params_alpha_beta=organ_params.alpha_beta_gy
            )
            dvh_for_ntcp = compute_eqd2_dvh(dvh_df, n_fractions_plan, alpha_beta_oar)
            bdvh_applied = True

        # The reported dose statistics stay PHYSICAL, measured on the DVH as delivered. Only the
        # NTCP input is converted: gEUD below is the gEUD of `dvh_for_ntcp`, which is the EQD2 DVH
        # whenever one was built. Reporting an EQD2 Dmean in a column named Dmean_gy would quietly
        # change what every downstream reader of that column means.
        metrics = _dvh_metrics(dvh_df)
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
            # Two values only, since #63. "eqd2": the DVH was converted bin-wise and gEUD_gy below
            # is the gEUD of that converted DVH. "physical": the export did not state its
            # fractionation, so no transform could be applied (#4/#5) and the NTCP is on physical
            # dose. The third value this column used to take, "physical_2gy_equivalent", asserted
            # that a plan at 2 Gy per fraction needs no conversion; that was defect #63.
            "ntcp_dose_basis": "eqd2" if bdvh_applied else "physical",
            # The alpha/beta the conversion used, so a reader can reproduce it. NaN when no
            # conversion ran.
            "alpha_beta_gy_used": alpha_beta_oar,
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
        if not dvh_df.empty:
            from dicom_io.dvh_shape_features import compute_dvh_shape_features

            organ_name = getattr(organ_params, "canonical", None) or str(
                getattr(organ_params, "name", "")
            )
            # PHYSICAL, like Dmean and Dmax beside them (#63). D2/D50/D98 are reported dose
            # statistics, not NTCP inputs; computing them on the EQD2 histogram would silently
            # change what those columns mean for every reader downstream.
            row.update(compute_dvh_shape_features(dvh_df, organ_name))
        row["param_illustrative"] = bool(organ_params.illustrative)
        row["param_source"] = organ_params.source
        row["param_provenance"] = {
            model: organ_params.model_provenance(model)
            for model in MODEL_KEYS
            if getattr(organ_params, _MODEL_ATTR[model], None)
        }

        if str(mode).lower() == "basic":
            refused = []
            for model in MODEL_KEYS:
                if not getattr(organ_params, _MODEL_ATTR[model], None):
                    continue
                if organ_params.model_is_illustrative(model):
                    row[f"NTCP_{model}"] = math.nan
                    refused.append(model)
            if refused:
                row["ntcp_refusal_reason"] = ILLUSTRATIVE_PARAMS_IN_BASIC_MODE
                row["ntcp_refused_models"] = ";".join(refused)
                if organ_params.illustrative:
                    row["definition_ok"] = False
                logger.warning(
                    "BASIC mode: %s/%s refused for %s - those parameters have no published "
                    "source (%s). Run in ADVANCED mode to compute them, labelled.",
                    site_key,
                    canonical,
                    ", ".join(refused),
                    ILLUSTRATIVE_PARAMS_IN_BASIC_MODE,
                )

        for model_name, model_instance in iter_ntcp_models().items():
            try:
                ext = model_instance.compute_ntcp_dvh(dvh_for_ntcp, organ_params, n_fractions_plan)
                row[f"NTCP_{model_name}"] = float(ext.get("ntcp", math.nan))
            except Exception as exc:
                logger.warning("Registered NTCP model %s failed: %s", model_name, exc)
        # Two histograms, each going where it belongs (#63).
        #   _dvh_df      -- physical. QUANTEC constraints are stated on physical dose for
        #                   conventional fractionation, so the constraint checker must see the
        #                   dose as delivered. Before #63 this was physical for a 2 Gy/fraction
        #                   plan and EQD2 otherwise, which meant the QUANTEC basis depended on
        #                   the fractionation without saying so.
        #   _dvh_df_ntcp -- the histogram the NTCP was actually computed from, for anything that
        #                   must fit on the same basis the model used (the LKB calibration).
        row["_dvh_df"] = dvh_df
        row["_dvh_df_ntcp"] = dvh_for_ntcp
        return row
