"""
QUANTEC 2010 dose constraint checker.

Evaluates DVH metrics against QUANTEC published thresholds (Marks et al. IJROBP 2010).
Dose-volume constraint check — complementary to probabilistic NTCP models.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class QUANTECResult:
    organ: str
    metric: str
    actual_value: float
    limit: float
    endpoint: str
    reference: str
    severity: str
    anon_patient_id: str = ""


QUANTEC_CONSTRAINTS: dict[str, list[dict]] = {
    "SpinalCord": [
        {
            "metric": "Dmax",
            "limit": 45.0,
            "endpoint": "Myelopathy <1%",
            "ref": "Kirkpatrick IJROBP 2010;76:S42",
        },
        {
            "metric": "Dmax",
            "limit": 50.0,
            "endpoint": "Myelopathy <0.2%",
            "ref": "Kirkpatrick IJROBP 2010;76:S42",
        },
    ],
    "Brainstem": [
        {
            "metric": "Dmax",
            "limit": 54.0,
            "endpoint": "Neuropathy/necrosis",
            "ref": "Mayo IJROBP 2010;76:S20",
        },
        {
            "metric": "Dmax",
            "limit": 60.0,
            "endpoint": "Neuropathy absolute limit (<1cc)",
            "ref": "Mayo IJROBP 2010;76:S20",
        },
    ],
    "OpticChiasm": [
        {
            "metric": "Dmax",
            "limit": 54.0,
            "endpoint": "Optic neuropathy <3%",
            "ref": "Mayo IJROBP 2010;76:S28",
        },
    ],
    "OpticNerve_L": [
        {
            "metric": "Dmax",
            "limit": 54.0,
            "endpoint": "Optic neuropathy <3%",
            "ref": "Mayo IJROBP 2010;76:S28",
        },
    ],
    "OpticNerve_R": [
        {
            "metric": "Dmax",
            "limit": 54.0,
            "endpoint": "Optic neuropathy <3%",
            "ref": "Mayo IJROBP 2010;76:S28",
        },
    ],
    "NormalBrain": [
        {
            "metric": "V60",
            "limit": 3.0,
            "endpoint": "Symptomatic radionecrosis <5% (V60<3cc)",
            "ref": "Lawrence IJROBP 2010;76:S20",
        },
    ],
    "Hippocampus_L": [
        {
            "metric": "Dmean",
            "limit": 7.3,
            "endpoint": "Neurocognitive decline (RTOG 0933)",
            "ref": "Gondi IJROBP 2014;88:571",
        },
    ],
    "Hippocampus_R": [
        {
            "metric": "Dmean",
            "limit": 7.3,
            "endpoint": "Neurocognitive decline (RTOG 0933)",
            "ref": "Gondi IJROBP 2014;88:571",
        },
    ],
    "Parotid_L": [
        {
            "metric": "Dmean",
            "limit": 25.0,
            "endpoint": "Xerostomia grade≥2 <20%",
            "ref": "Deasy IJROBP 2010;76:S86",
        },
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Xerostomia grade≥2 <15%",
            "ref": "Deasy IJROBP 2010;76:S86",
        },
    ],
    "Parotid_R": [
        {
            "metric": "Dmean",
            "limit": 25.0,
            "endpoint": "Xerostomia grade≥2 <20%",
            "ref": "Deasy IJROBP 2010;76:S86",
        },
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Xerostomia grade≥2 <15%",
            "ref": "Deasy IJROBP 2010;76:S86",
        },
    ],
    "Mandible": [
        {
            "metric": "Dmax",
            "limit": 70.0,
            "endpoint": "Osteoradionecrosis",
            "ref": "Tsai IJROBP 2013;85:1124",
        },
    ],
    "Larynx": [
        {
            "metric": "Dmean",
            "limit": 44.0,
            "endpoint": "Laryngeal edema grade≥2",
            "ref": "Sanguineti IJROBP 2007;69:1300",
        },
        {
            "metric": "Dmax",
            "limit": 66.0,
            "endpoint": "Laryngeal dysfunction",
            "ref": "QUANTEC HN supplement 2010",
        },
    ],
    "PharynxConstrictor": [
        {
            "metric": "Dmean",
            "limit": 50.0,
            "endpoint": "Dysphagia grade≥2",
            "ref": "Eisbruch IJROBP 2011;81:1327",
        },
    ],
    "OralCavity": [
        {
            "metric": "Dmean",
            "limit": 40.0,
            "endpoint": "Mucositis grade≥2",
            "ref": "QUANTEC HN supplement 2010",
        },
    ],
    "LungTotal": [
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Pneumonitis grade≥2 <20%",
            "ref": "Marks IJROBP 2010;76:S70",
        },
        {
            "metric": "V20",
            "limit": 30.0,
            "endpoint": "Pneumonitis grade≥2 <20%",
            "ref": "Marks IJROBP 2010;76:S70",
        },
        {
            "metric": "V5",
            "limit": 65.0,
            "endpoint": "Pneumonitis (V5 limit)",
            "ref": "Marks IJROBP 2010;76:S70",
        },
    ],
    "Lung_L": [
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Pneumonitis grade≥2",
            "ref": "Marks IJROBP 2010;76:S70",
        },
        {
            "metric": "V20",
            "limit": 30.0,
            "endpoint": "Pneumonitis grade≥2",
            "ref": "Marks IJROBP 2010;76:S70",
        },
    ],
    "Lung_R": [
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Pneumonitis grade≥2",
            "ref": "Marks IJROBP 2010;76:S70",
        },
        {
            "metric": "V20",
            "limit": 30.0,
            "endpoint": "Pneumonitis grade≥2",
            "ref": "Marks IJROBP 2010;76:S70",
        },
    ],
    "Heart": [
        {
            "metric": "Dmean",
            "limit": 26.0,
            "endpoint": "Pericarditis grade≥3",
            "ref": "Gagliardi IJROBP 2010;76:S77",
        },
        {
            "metric": "V25",
            "limit": 10.0,
            "endpoint": "Cardiac toxicity <1%",
            "ref": "Gagliardi IJROBP 2010;76:S77",
        },
    ],
    "Esophagus": [
        {
            "metric": "Dmean",
            "limit": 34.0,
            "endpoint": "Esophagitis grade≥2 <30%",
            "ref": "Werner-Wasik IJROBP 2010;76:S86",
        },
        {
            "metric": "Dmax",
            "limit": 58.0,
            "endpoint": "Esophageal stricture",
            "ref": "Werner-Wasik IJROBP 2010;76:S86",
        },
    ],
    "Cochlea_L": [
        {
            "metric": "Dmean",
            "limit": 45.0,
            "endpoint": "Sensorineural hearing loss",
            "ref": "Bhandare IJROBP 2010;76:S110",
        },
    ],
    "Cochlea_R": [
        {
            "metric": "Dmean",
            "limit": 45.0,
            "endpoint": "Sensorineural hearing loss",
            "ref": "Bhandare IJROBP 2010;76:S110",
        },
    ],
    "LAD": [
        {
            "metric": "Dmean",
            "limit": 10.0,
            "endpoint": "Major coronary event risk (LAD)",
            "ref": "van Nimwegen Heart 2016;102:1703",
        },
    ],
    "Lung_Ipsi": [
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Pneumonitis grade≥2",
            "ref": "Marks IJROBP 2010;76:S70",
        },
    ],
    "ChestWall": [
        {
            "metric": "V30",
            "limit": 70.0,
            "endpoint": "Chest wall pain grade≥2 <30%",
            "ref": "Timmerman IJROBP 2008;72:S53 (RTOG 0236)",
        },
    ],
    "BrachialPlexus": [
        {
            "metric": "Dmax",
            "limit": 66.0,
            "endpoint": "Brachial plexopathy grade≥2",
            "ref": "Johansson IJROBP 2014;88:92",
        },
    ],
    "Pituitary": [
        {
            "metric": "Dmean",
            "limit": 45.0,
            "endpoint": "Hypopituitarism grade≥2",
            "ref": "Appelman IJROBP 2011;79:1421",
        },
    ],
    "Thyroid": [
        {
            "metric": "Dmean",
            "limit": 30.0,
            "endpoint": "Hypothyroidism grade≥1 (supraclav RT)",
            "ref": "Smyczek-Gargya Clin Trans RadSci 2024 (PubMed 38317677)",
        },
        {
            "metric": "Dmean",
            "limit": 20.0,
            "endpoint": "Hypothyroidism grade≥1 <15% risk",
            "ref": "NTCP hypothyroid breast: PubMed 32926911",
        },
    ],
    "Lung_Contra": [
        {
            "metric": "Dmean",
            "limit": 10.0,
            "endpoint": "Low-dose pneumonitis risk (bilateral fields)",
            "ref": "Marks IJROBP 2010;76:S70 (extrapolated)",
        },
    ],
    "Rib": [
        {
            "metric": "Dmax",
            "limit": 50.0,
            "endpoint": "Rib fracture grade≥2 <5% (EQD2 Dmax)",
            "ref": "Timmerman IJROBP 2008;72:S53; PMC3573931",
        },
    ],
    "Rectum": [
        {
            "metric": "V70",
            "limit": 25.0,
            "endpoint": "Rectal bleeding grade≥2 <15%",
            "ref": "Michalski IJROBP 2010;76:S123",
        },
        {
            "metric": "V60",
            "limit": 35.0,
            "endpoint": "Rectal toxicity grade≥2",
            "ref": "Michalski IJROBP 2010;76:S123",
        },
        {
            "metric": "V50",
            "limit": 50.0,
            "endpoint": "Rectal toxicity grade≥2",
            "ref": "Michalski IJROBP 2010;76:S123",
        },
        {
            "metric": "Dmean",
            "limit": 40.0,
            "endpoint": "Rectal toxicity (mean dose limit)",
            "ref": "Michalski IJROBP 2010;76:S123",
        },
    ],
    "Bladder": [
        {
            "metric": "V80",
            "limit": 15.0,
            "endpoint": "Bladder toxicity grade≥3 <6%",
            "ref": "Viswanathan IJROBP 2010;76:S132",
        },
        {
            "metric": "V65",
            "limit": 25.0,
            "endpoint": "Bladder toxicity grade≥2",
            "ref": "Viswanathan IJROBP 2010;76:S132",
        },
    ],
    "Liver": [
        {
            "metric": "Dmean",
            "limit": 28.0,
            "endpoint": "RILD grade≥3 <5% (whole liver RT)",
            "ref": "Pan IJROBP 2010;76:S94",
        },
        {
            "metric": "Dmean",
            "limit": 32.0,
            "endpoint": "RILD (liver minus GTV, Child-Pugh A)",
            "ref": "Pan IJROBP 2010;76:S94",
        },
    ],
    "Kidney_L": [
        {
            "metric": "Dmean",
            "limit": 18.0,
            "endpoint": "Renal dysfunction grade≥3 <5%",
            "ref": "Cassidy IJROBP 2010;76:S108",
        },
    ],
    "Kidney_R": [
        {
            "metric": "Dmean",
            "limit": 18.0,
            "endpoint": "Renal dysfunction grade≥3 <5%",
            "ref": "Cassidy IJROBP 2010;76:S108",
        },
    ],
    "KidneysTotal": [
        {
            "metric": "Dmean",
            "limit": 18.0,
            "endpoint": "Renal dysfunction grade≥3 <5% (combined)",
            "ref": "Cassidy IJROBP 2010;76:S108",
        },
        {
            "metric": "V20",
            "limit": 32.0,
            "endpoint": "Renal dysfunction (V20 combined kidneys)",
            "ref": "Cassidy IJROBP 2010;76:S108",
        },
    ],
    "FemoralHead_L": [
        {
            "metric": "V50",
            "limit": 5.0,
            "endpoint": "Avascular necrosis grade≥3 <5%",
            "ref": "Kavanagh IJROBP 2010;76:S137",
        },
    ],
    "FemoralHead_R": [
        {
            "metric": "V50",
            "limit": 5.0,
            "endpoint": "Avascular necrosis grade≥3 <5%",
            "ref": "Kavanagh IJROBP 2010;76:S137",
        },
    ],
}


def _compute_dvh_metric(dvh_df: pd.DataFrame, metric: str) -> float:
    """Vxx = volume % receiving ≥ xx Gy; Dmax/Dmean in Gy."""
    if dvh_df is None or dvh_df.empty:
        return math.nan
    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    total = vols.sum()
    if total <= 0:
        return math.nan
    if metric == "Dmax":
        return float(doses.max())
    if metric == "Dmean":
        return float((doses * vols).sum() / total)
    if metric.startswith("V"):
        try:
            thr = float(metric[1:])
            return float(vols[doses >= thr].sum() / total * 100.0)
        except ValueError:
            return math.nan
    return math.nan


def check_quantec_constraints(
    dvh_df: pd.DataFrame,
    canonical_oar: str,
    anon_id: str = "",
) -> list[QUANTECResult]:
    """VIOLATION if actual > limit; WARNING if within 10% below limit."""
    results: list[QUANTECResult] = []
    for c in QUANTEC_CONSTRAINTS.get(canonical_oar, []):
        actual = _compute_dvh_metric(dvh_df, c["metric"])
        if math.isnan(actual):
            continue
        limit = float(c["limit"])
        if actual > limit:
            severity = "VIOLATION"
        elif actual > limit * 0.90:
            severity = "WARNING"
        else:
            continue
        results.append(
            QUANTECResult(
                organ=canonical_oar,
                metric=c["metric"],
                actual_value=actual,
                limit=limit,
                endpoint=c["endpoint"],
                reference=c["ref"],
                severity=severity,
                anon_patient_id=anon_id,
            )
        )
    return results


def check_cohort_quantec(ntcp_results: list[dict]) -> pd.DataFrame:
    """Evaluate QUANTEC constraints for all OARs in an NTCP result list."""
    rows: list[dict] = []
    for r in ntcp_results:
        dvh_df = r.get("_dvh_df")
        if dvh_df is None:
            continue
        organ = str(r.get("structure", ""))
        anon_id = str(r.get("AnonPatientID", ""))
        for v in check_quantec_constraints(dvh_df, organ, anon_id):
            rows.append(
                {
                    "AnonPatientID": v.anon_patient_id,
                    "OAR": v.organ,
                    "Metric": v.metric,
                    "Actual_Gy_or_Pct": round(v.actual_value, 2),
                    "QUANTEC_Limit": round(v.limit, 2),
                    "Clinical_Endpoint": v.endpoint,
                    "Reference": v.reference,
                    "Severity": v.severity,
                }
            )
    cols = [
        "AnonPatientID",
        "OAR",
        "Metric",
        "Actual_Gy_or_Pct",
        "QUANTEC_Limit",
        "Clinical_Endpoint",
        "Reference",
        "Severity",
    ]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
