"""
Patient ID harmonization across DVH, DICOM, and clinical spreadsheets.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd


def _norm_id(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    return re.sub(r"\s+", "_", s)


def collect_dvh_patient_ids(processed_dir: Path) -> Set[str]:
    """Patient IDs from processed_DVH/cDVH_csv or dDVH_csv filenames."""
    processed_dir = Path(processed_dir)
    ids: Set[str] = set()
    for sub in ("cDVH_csv", "dDVH_csv"):
        folder = processed_dir / sub
        if not folder.is_dir():
            continue
        for csv_path in folder.glob("*.csv"):
            stem = csv_path.stem
            if "_" in stem:
                ids.add(stem.rsplit("_", 1)[0])
            else:
                ids.add(stem)
    return ids


def load_mapping(map_path: Path) -> Dict[str, str]:
    """
    Load patient_id_map.csv with columns: source_id, canonical_id (header flexible).
    """
    map_path = Path(map_path)
    if not map_path.is_file():
        return {}
    df = pd.read_csv(map_path)
    cols = {c.lower(): c for c in df.columns}
    src_col = cols.get("source_id") or cols.get("source") or df.columns[0]
    dst_col = cols.get("canonical_id") or cols.get("canonical") or cols.get("patient_id")
    if dst_col is None and len(df.columns) > 1:
        dst_col = df.columns[1]
    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        src = _norm_id(row[src_col])
        dst = _norm_id(row[dst_col])
        if src and dst:
            mapping[src] = dst
    return mapping


def save_mapping(map_path: Path, mapping: Dict[str, str]) -> None:
    map_path = Path(map_path)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"source_id": k, "canonical_id": v} for k, v in sorted(mapping.items())]
    pd.DataFrame(rows).to_csv(map_path, index=False)


def build_auto_mapping(
    dvh_ids: Set[str],
    clinical_ids: Set[str],
) -> Dict[str, str]:
    """
    Heuristic 1:1 map when IDs match exactly (case-insensitive).
    PT001 <-> PT001, 2019-1927 <-> 2019-1927
    """
    mapping: Dict[str, str] = {}
    clinical_lower = {_norm_id(c).lower(): _norm_id(c) for c in clinical_ids if _norm_id(c)}

    for did in dvh_ids:
        key = _norm_id(did).lower()
        if key in clinical_lower:
            mapping[_norm_id(did)] = clinical_lower[key]
        else:
            mapping[_norm_id(did)] = _norm_id(did)
    for cid in clinical_ids:
        c = _norm_id(cid)
        if c and c not in mapping.values():
            mapping.setdefault(c, c)
    return mapping


def apply_mapping_to_clinical_df(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Rewrite patient ID columns using mapping (source -> canonical)."""
    if df is None or df.empty or not mapping:
        return df
    out = df.copy()
    id_cols = [
        c
        for c in out.columns
        if any(kw in c.lower() for kw in ("patientid", "patient_id", "patient_anoid", "anoid", "id"))
    ]
    for col in id_cols:
        out[col] = out[col].map(lambda x: mapping.get(_norm_id(x), _norm_id(x)) or x)
    return out


def collect_clinical_patient_ids(df: pd.DataFrame) -> Set[str]:
    if df is None or df.empty:
        return set()
    for col in df.columns:
        if any(kw in col.lower() for kw in ("patientid", "patient_id", "patient_anoid", "anoid")):
            return {_norm_id(v) for v in df[col].dropna().unique() if _norm_id(v)}
    return set()


def write_registry_report(
    output_dir: Path,
    dvh_ids: Set[str],
    clinical_ids: Set[str],
    mapping: Dict[str, str],
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "dvh_patient_count": len(dvh_ids),
        "clinical_patient_count": len(clinical_ids),
        "mapped_count": len(mapping),
        "overlap_exact": len(set(mapping.keys()) & set(clinical_ids)),
        "dvh_only": sorted(dvh_ids - set(mapping.values())),
        "clinical_only": sorted(clinical_ids - set(mapping.keys())),
    }
    path = output_dir / "patient_id_registry.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    save_mapping(output_dir / "patient_id_map.csv", mapping)
    return path
