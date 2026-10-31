"""Unified TCP orchestrator for all four radiobiological models."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from radiobiology import dvh_object_to_dataframe, lq_model
from radiobiology.geud_tcp import GEUDTCPCalculator
from radiobiology.logistic_tcp import LogisticTCPCalculator
from radiobiology.model_registry import iter_tcp_models, register_tcp_model  # noqa: F401
from radiobiology.poisson_tcp import PoissonTCPCalculator, _dvh_dmean
from radiobiology.zaider_minerbo import ZMTCPCalculator

if TYPE_CHECKING:
    from config.site_params import TCPSiteParams

logger = logging.getLogger(__name__)

#: Reason written when the dose per fraction is outside the LQ model's validity range.
LQ_INVALID_DPF = "LQ_INVALID_DPF"


class TCPCalculator:
    """Orchestrates Poisson, Z-M, gEUD, and Logistic TCP models."""

    def __init__(self, zm_dead_fraction: float = 0.85, zm_t_obs_days: float = 730.0):
        self._poisson = PoissonTCPCalculator()
        self._zm = ZMTCPCalculator(dead_fraction=zm_dead_fraction, t_obs_days=zm_t_obs_days)
        self._geud = GEUDTCPCalculator()
        self._logistic = LogisticTCPCalculator()

    def compute_all(
        self,
        dvh_result: Any,
        plan_metadata: dict,
        site_params: TCPSiteParams,
        target_type: str | None = None,
        allow_lq_extrapolation: bool = False,
    ) -> dict:
        """Compute every TCP model for one target.

        Defect #10: a dose per fraction above ``site_params.lq_valid_max_dpf_gy`` used only to
        raise ``lq_caution``, and the numbers were written anyway. Outside its validity range the
        LQ model is being extrapolated, so TCP is now refused with ``LQ_INVALID_DPF`` unless the
        caller asks for the extrapolation by passing ``allow_lq_extrapolation=True``.
        """
        canonical = getattr(dvh_result, "canonical_name", "GTV")
        target = target_type or canonical
        if target not in ("GTV", "CTV", "PTV"):
            target = canonical if canonical in ("GTV", "CTV", "PTV") else "GTV"

        total_dose = float(plan_metadata.get("prescription_dose_gy") or 0.0)
        n_fractions = int(plan_metadata.get("n_fractions") or 1)
        dpf = float(plan_metadata.get("dose_per_fraction_gy") or 0.0)
        lq_caution = dpf > site_params.lq_valid_max_dpf_gy

        dvh_df = dvh_object_to_dataframe(getattr(dvh_result, "dvh_object", None))
        dmean = _dvh_dmean(dvh_df)
        if math.isnan(dmean) and hasattr(dvh_result, "dmean_gy"):
            dmean = float(dvh_result.dmean_gy)

        if lq_caution:
            eqd2_gy = lq_model.eqd2_usc(
                total_dose, dpf, site_params.alpha_beta_gy, site_params.lq_valid_max_dpf_gy
            )
        else:
            eqd2_gy = lq_model.eqd2(total_dose, dpf, site_params.alpha_beta_gy)
        bed_gy = lq_model.bed(total_dose, dpf, site_params.alpha_beta_gy)

        result = {
            "canonical_name": canonical,
            "site": site_params.site,
            "target_type": target,
            "total_dose_gy": total_dose,
            "n_fractions": n_fractions,
            "dose_per_fraction": dpf,
            "lq_caution": lq_caution,
            "tcp_refused": False,
            "tcp_refusal_reason": "",
            "lq_extrapolation_allowed": bool(allow_lq_extrapolation),
            "BED_gy": bed_gy,
            "EQD2_gy": eqd2_gy,
            "Dmean_gy": dmean,
            "TCP_Poisson": math.nan,
            "N_eff_Poisson": math.nan,
            "SF_total": math.nan,
            "repop_factor": math.nan,
            "TCP_ZM": math.nan,
            "p0_single_cell": math.nan,
            "TCP_gEUD": math.nan,
            "gEUD_gy": math.nan,
            "gEUD_reason": "",
            "TCP_Logistic": math.nan,
            "TCP_mean": math.nan,
            "TCP_range": math.nan,
        }

        if getattr(dvh_result, "quality_flag", "OK") != "OK":
            logger.warning(
                "DVH quality flag %s for %s; TCP models may return NaN",
                dvh_result.quality_flag,
                canonical,
            )

        upstream = [str(r) for r in (plan_metadata.get("tcp_refusal_reasons") or []) if r]
        if upstream:
            # #4/#5: the TPS export stated no prescription and/or no fractionation, and nothing
            # is invented in its place. NTCP from physical dose is unaffected.
            result["tcp_refused"] = True
            result["tcp_refusal_reason"] = ";".join(upstream)
            logger.warning(
                "TCP refused for %s: %s. Supply the prescription and fractionation to compute it.",
                canonical,
                ";".join(upstream),
            )
            result["_dvh_df"] = dvh_df
            return result

        if lq_caution and not allow_lq_extrapolation:
            # #10: refuse rather than publish an extrapolated number with a flag beside it.
            result["tcp_refused"] = True
            result["tcp_refusal_reason"] = LQ_INVALID_DPF
            logger.warning(
                "TCP refused for %s: %.3g Gy/fraction exceeds the LQ validity cap of %.3g Gy "
                "for site %s (%s). Pass allow_lq_extrapolation=True to compute anyway.",
                canonical,
                dpf,
                site_params.lq_valid_max_dpf_gy,
                site_params.site,
                LQ_INVALID_DPF,
            )
            result["_dvh_df"] = dvh_df
            return result

        try:
            poisson = self._poisson.compute_tcp_dvh(dvh_df, n_fractions, site_params, target)
            result["TCP_Poisson"] = poisson["tcp"]
            result["N_eff_Poisson"] = poisson["N_eff"]
            result["SF_total"] = poisson["SF_total"]
            result["repop_factor"] = poisson["repop_factor"]
        except Exception as exc:
            logger.warning("Poisson TCP failed: %s", exc)

        try:
            zm = self._zm.compute_tcp_dvh(dvh_df, n_fractions, site_params, target)
            result["TCP_ZM"] = zm["tcp"]
            result["p0_single_cell"] = zm["p0_single_cell"]
        except Exception as exc:
            logger.warning("Z-M TCP failed: %s", exc)

        try:
            geud = self._geud.compute_tcp(dvh_df, site_params)
            result["TCP_gEUD"] = geud["tcp"]
            result["gEUD_gy"] = geud["geud_gy"]
            result["gEUD_reason"] = geud.get("geud_reason", "")
        except Exception as exc:
            logger.warning("gEUD TCP failed: %s", exc)

        try:
            logistic = self._logistic.compute_tcp(dvh_df, site_params)
            result["TCP_Logistic"] = logistic["tcp"]
        except Exception as exc:
            logger.warning("Logistic TCP failed: %s", exc)

        if not dvh_df.empty:
            from dicom_io.dvh_shape_features import compute_dvh_shape_features

            result.update(compute_dvh_shape_features(dvh_df, canonical))

        model_tcps: list[float] = [
            float(result["TCP_Poisson"]),
            float(result["TCP_ZM"]),
            float(result["TCP_gEUD"]),
            float(result["TCP_Logistic"]),
        ]
        for model_name, model_instance in iter_tcp_models().items():
            try:
                ext_result = model_instance.compute_tcp_dvh(
                    dvh_df, n_fractions, site_params, target
                )
                tcp_key = f"TCP_{model_name}"
                ext_tcp = float(ext_result.get("tcp", math.nan))
                result[tcp_key] = ext_tcp
                if not math.isnan(ext_tcp):
                    model_tcps.append(ext_tcp)
            except Exception as exc:
                logger.warning("Registered TCP model %s failed: %s", model_name, exc)

        valid = [v for v in model_tcps if not math.isnan(v)]
        if valid:
            result["TCP_mean"] = float(np.mean(valid))
            result["TCP_range"] = float(max(valid) - min(valid))

        result["_dvh_df"] = dvh_df

        return result

    def compute_cohort(
        self,
        patient_list: list[dict],
        site_params_map: dict[str, TCPSiteParams],
        allow_lq_extrapolation: bool = False,
    ) -> pd.DataFrame:
        rows: list[dict] = []
        for patient in patient_list:
            anon_id = patient.get("anon_id", "")
            site_key = patient.get("site", "")
            params = site_params_map.get(site_key)
            if params is None:
                continue
            plan_meta = patient.get("plan_metadata", {})
            targets = patient.get("all_target_dvhs") or []
            for dvh_res in targets:
                row = self.compute_all(
                    dvh_res,
                    plan_meta,
                    params,
                    allow_lq_extrapolation=allow_lq_extrapolation,
                )
                row["AnonPatientID"] = anon_id
                rows.append(row)
        return pd.DataFrame(rows)
