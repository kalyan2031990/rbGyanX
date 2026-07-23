"""
Build the external-validation ``cohort_features.csv`` from the TCIA
Head-Neck-PET-CT archive (real anatomy; reference-planned dose).

Reads RTSTRUCT + RTDOSE (+ RTPLAN) **directly from the zip** (CT slices are not
needed for DVHs and are skipped), selects the plan-sum dose per patient, assembles
the per-patient feature row via ``dicom_io.cohort_features``, and joins the
loco-regional / death outcomes from the clinical workbook.

NO patient DICOM is written; only the derived, de-identified feature table.
Frame results as "association on reference-planned dose" (see docs/EXTVAL_DATA_READINESS.md).

Usage:
    python external_validation/build_cohort_features.py \
        --zip ".../TCIA2_Head-Neck-PET-CT.zip" \
        --clinical ".../Head-Neck-PET-CT.xlsx" \
        --out ".../cohort_features.csv" [--limit N]
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Allow running as a plain script from repo root (mirrors conftest fallback).
_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402
import pydicom  # noqa: E402
from clinical.hnscc_covariate_mapper import load_hnscc_outcomes  # noqa: E402

from dicom_io.cohort_features import build_patient_features  # noqa: E402

logger = logging.getLogger("extval.cohort_features")


def _select_plan_sum_dose(rds: list[Any]) -> Any | None:
    """Prefer DoseSummationType==PLAN; deterministic by SOPInstanceUID; else largest grid."""
    if not rds:
        return None
    plan = [d for d in rds if str(getattr(d, "DoseSummationType", "")).upper() == "PLAN"]
    pool = plan or rds
    pool.sort(key=lambda d: str(getattr(d, "SOPInstanceUID", "")))
    pool.sort(
        key=lambda d: int(getattr(d, "Rows", 0))
        * int(getattr(d, "Columns", 0))
        * int(getattr(d, "NumberOfFrames", 0)),
        reverse=True,
    )
    return pool[0]


def iter_patient_triples_from_zip(zip_path: Path) -> Iterator[tuple[str, Any, Any, Any]]:
    """Yield (patient_id, rt_struct, rt_dose_plan_sum, rt_plan) for each patient in the archive."""
    zf = zipfile.ZipFile(zip_path)
    by_patient: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {"RS": [], "RD": [], "RP": []}
    )
    for name in zf.namelist():
        if not name.lower().endswith(".dcm"):
            continue
        parts = name.split("/")
        # .../<patient>/<MODALITY>/<file>.dcm
        if len(parts) < 3:
            continue
        patient = parts[-3]
        sub = parts[-2].upper()
        if "RTSTRUCT" in sub:
            by_patient[patient]["RS"].append(name)
        elif "RTDOSE" in sub:
            by_patient[patient]["RD"].append(name)
        elif "RTPLAN" in sub:
            by_patient[patient]["RP"].append(name)

    for patient in sorted(by_patient):
        files = by_patient[patient]
        if not files["RS"] or not files["RD"]:
            logger.warning("skip %s: missing RS or RD", patient)
            continue
        rs = pydicom.dcmread(io.BytesIO(zf.read(files["RS"][0])), force=True)
        rds = [pydicom.dcmread(io.BytesIO(zf.read(n)), force=True) for n in files["RD"]]
        rd = _select_plan_sum_dose(rds)
        rp = (
            pydicom.dcmread(io.BytesIO(zf.read(sorted(files["RP"])[0])), force=True)
            if files["RP"]
            else None
        )
        yield patient, rs, rd, rp


def build_cohort_csv(
    zip_path: Path,
    clinical_xlsx: Path | None,
    out_csv: Path,
    limit: int | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, (pid, rs, rd, rp) in enumerate(iter_patient_triples_from_zip(zip_path)):
        if limit is not None and i >= limit:
            break
        try:
            row = build_patient_features(rs, rd, rp, patient_id=pid)
        except Exception as exc:  # keep going; record the failure
            logger.warning("feature build failed for %s: %s", pid, exc)
            row = {"patient_id": pid, "build_error": str(exc)}
        rows.append(row)
        logger.info("[%d] %s done", i + 1, pid)

    features = pd.DataFrame(rows)
    if clinical_xlsx and Path(clinical_xlsx).is_file():
        outcomes = load_hnscc_outcomes(clinical_xlsx)
        features = features.merge(outcomes, on="patient_id", how="left")
        n_linked = features["death"].notna().sum() if "death" in features else 0
        logger.info("linked %d/%d patients to an outcome row", int(n_linked), len(features))

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(out_csv, index=False)
    logger.info("wrote %s (%d rows x %d cols)", out_csv, *features.shape)
    return features


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", required=True, type=Path, help="TCIA2_Head-Neck-PET-CT.zip")
    ap.add_argument("--clinical", type=Path, default=None, help="Head-Neck-PET-CT.xlsx")
    ap.add_argument("--out", required=True, type=Path, help="output cohort_features.csv")
    ap.add_argument("--limit", type=int, default=None, help="process only first N patients")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    df = build_cohort_csv(args.zip, args.clinical, args.out, args.limit)
    n_events = int(df["locoregional"].sum()) if "locoregional" in df else 0
    print(f"\nDONE: {df.shape[0]} patients, {df.shape[1]} columns, {n_events} loco-regional events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
