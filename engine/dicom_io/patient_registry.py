"""Cohort patient registry with Excel export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dicom_io.dvh_extractor import DVHExtractor, DVHResult


class PatientRegistry:
    """Accumulate per-patient DICOM, plan, site, and DVH records."""

    def __init__(self):
        self._records: list[dict] = []
        self._dvh_metric_rows: list[dict] = []
        self._anon_counter = 1
        self._extractor = DVHExtractor()

    def _next_anon_id(self) -> str:
        anon_id = f"PT{self._anon_counter:03d}"
        self._anon_counter += 1
        return anon_id

    def add_patient(
        self,
        dicom_data: dict,
        plan_metadata: dict,
        site_result: dict,
        dvh_results: dict[int, DVHResult],
    ) -> None:
        anon_id = self._next_anon_id()
        structures_present = sorted(
            {res.canonical_name for res in dvh_results.values()}
        )

        by_canonical: dict[str, DVHResult] = {}
        for res in dvh_results.values():
            by_canonical.setdefault(res.canonical_name, res)

        def _vol(name: str) -> float | None:
            item = by_canonical.get(name)
            return item.total_volume_cc if item else None

        def _metric(name: str, key: str) -> float | None:
            item = by_canonical.get(name)
            if not item or item.quality_flag != "OK":
                return None
            if not item.dose_metrics:
                item.dose_metrics = self._extractor.compute_dose_metrics(
                    item, float(plan_metadata.get("prescription_dose_gy") or 0.0)
                )
            value = item.dose_metrics.get(key)
            return None if value is None else float(value)

        modes = {res.extraction_mode for res in dvh_results.values()}
        if len(modes) == 1:
            dvh_mode = next(iter(modes)) if modes else ""
        elif modes:
            dvh_mode = "MIXED"
        else:
            dvh_mode = ""

        warnings: list[str] = []
        if "GTV" not in by_canonical:
            warnings.append("WARNING_MISSING_TARGET")
        if site_result.get("confidence") == "LOW":
            warnings.append("WARNING_LOW_SITE_CONFIDENCE")
        if plan_metadata.get("lq_model_caution"):
            warnings.append("WARNING_LQ_CAUTION")
        if any(res.quality_flag == "FAILED" for res in dvh_results.values()):
            warnings.append("WARNING_DVH_FAILED")

        ptv_hi = _metric("PTV", "HI")
        record = {
            "PrimaryPatientID": dicom_data.get("patient_id", ""),
            "AnonPatientID": anon_id,
            "PatientSex": dicom_data.get("patient_sex", ""),
            "PatientDOB": dicom_data.get("patient_dob", ""),
            "StudyDate": dicom_data.get("study_date", ""),
            "Institution": dicom_data.get("institution", ""),
            "TPS_Vendor": dicom_data.get("tps_vendor", ""),
            "TPS_Version": dicom_data.get("tps_version", ""),
            "Site": site_result.get("site", ""),
            "SiteSubtype": site_result.get("subtype", ""),
            "SiteConfidence": site_result.get("confidence", ""),
            "BeamType": plan_metadata.get("beam_type", ""),
            "IsStereotactic": plan_metadata.get("is_stereotactic", False),
            "LQ_Caution_Flag": plan_metadata.get("lq_model_caution", False),
            "PrescriptionDose_Gy": plan_metadata.get("prescription_dose_gy"),
            "NumFractions": plan_metadata.get("n_fractions"),
            "DosePerFraction_Gy": plan_metadata.get("dose_per_fraction_gy"),
            "NominalEnergy_MV": plan_metadata.get("nominal_energy_mv"),
            "TotalMU": plan_metadata.get("total_mu"),
            "Structures_Present": ";".join(structures_present),
            "GTV_Volume_cc": _vol("GTV"),
            "CTV_Volume_cc": _vol("CTV"),
            "PTV_Volume_cc": _vol("PTV"),
            "GTV_Dmean_Gy": _metric("GTV", "Dmean_gy"),
            "GTV_D95_Gy": _metric("GTV", "D95_gy"),
            "GTV_Dmax_Gy": _metric("GTV", "Dmax_gy"),
            "CTV_Dmean_Gy": _metric("CTV", "Dmean_gy"),
            "CTV_D95_Gy": _metric("CTV", "D95_gy"),
            "PTV_Dmean_Gy": _metric("PTV", "Dmean_gy"),
            "PTV_D95_Gy": _metric("PTV", "D95_gy"),
            "PTV_V95pct": _metric("PTV", "V95pct"),
            "PTV_HI": ptv_hi,
            "DVH_Mode": dvh_mode,
            "DataQualityFlag": ",".join(warnings) if warnings else "OK",
            "_dvh_results": dvh_results,
            "_plan_metadata": plan_metadata,
            "_site_result": site_result,
        }
        self._records.append(record)

        rx = float(plan_metadata.get("prescription_dose_gy") or 0.0)
        for res in dvh_results.values():
            metrics = self._extractor.compute_dose_metrics(res, rx)
            self._dvh_metric_rows.append(
                {
                    "AnonPatientID": anon_id,
                    "Structure_Canonical": res.canonical_name,
                    "Structure_Raw": res.raw_name,
                    "Category": res.category,
                    "Volume_cc": res.total_volume_cc,
                    **metrics,
                }
            )

    def build_dataframe(self) -> pd.DataFrame:
        if not self._records:
            return pd.DataFrame()
        rows = [
            {k: v for k, v in record.items() if not k.startswith("_")}
            for record in self._records
        ]
        return pd.DataFrame(rows)

    def export(self, output_path: str | Path) -> None:
        output_path = Path(output_path)
        registry_df = self.build_dataframe()
        metrics_df = pd.DataFrame(self._dvh_metric_rows)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            registry_df.to_excel(writer, sheet_name="Registry", index=False)
            metrics_df.to_excel(writer, sheet_name="DVH_Metrics", index=False)

    def get_tcp_inputs(self, patient_id: str) -> dict:
        record = None
        for item in self._records:
            if item["PrimaryPatientID"] == patient_id or item["AnonPatientID"] == patient_id:
                record = item
                break
        if record is None:
            raise KeyError(f"Patient not found in registry: {patient_id}")

        dvh_results: dict[int, DVHResult] = record["_dvh_results"]
        by_canonical = {res.canonical_name: res for res in dvh_results.values()}
        target_dvhs = [
            res
            for res in dvh_results.values()
            if res.canonical_name in {"GTV", "CTV", "PTV", "ITV", "BOOST"}
        ]

        return {
            "anon_id": record["AnonPatientID"],
            "site": record["Site"],
            "plan_metadata": record["_plan_metadata"],
            "gtv_dvh": by_canonical.get("GTV"),
            "ctv_dvh": by_canonical.get("CTV"),
            "ptv_dvh": by_canonical.get("PTV"),
            "all_target_dvhs": target_dvhs,
        }
