#!/usr/bin/env python3
"""
rbGyanX v1.0 - DVH Preprocessing Module
========================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

code1_dvh_preprocess.py  ⟶  processed_dvh.xlsx  +  cDVH_csv/ +  dDVH_csv/
================================================================================
Reads DVH files in multiple formats (Eclipse TXT, CSV, DICOM), extracts header 
metadata, detects whether the curve is *cumulative* or *differential*, converts 
as needed, and writes **both** variants:

    • cDVH_csv/<AnoID>_<Organ>.csv   – cumulative DVH (volume column = cm³)
    • dDVH_csv/<AnoID>_<Organ>.csv   – differential DVH (cm³ per‑bin)

The script keeps the workbook summary (processed_dvh.xlsx) unchanged.

Author: rbGyanX Team
License: MIT
"""
from __future__ import annotations

import argparse
import hashlib
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Tuple, List, Dict

import numpy as np
import pandas as pd

from rbgyanx.utils.numeric_compat import trapz as _trapz

# Import UniversalDVHParser for intelligent preprocessing
try:
    from utils.dvh_parser import UniversalDVHParser, preprocess_dvh_intelligent
    UNIVERSAL_PARSER_AVAILABLE = True
except ImportError:
    UNIVERSAL_PARSER_AVAILABLE = False
    print("Warning: UniversalDVHParser not available. Using legacy parser.")

# ── canonical organs ───────────────────────────────────────────────────────────

def canon(raw: str) -> str:
    """Enhanced normalization with variant handling"""
    if not isinstance(raw, str):
        raw = str(raw)
    
    s = re.sub(r"[ _\\-]", "", raw.lower())
    
    # Map common variations including "combo"
    if "combo" in s or any(tag in s for tag in ["pd", "prtd", "parot", "parotid"]):
        return "Parotid"
    if any(x in s for x in ["cord", "spinal", "sc"]):
        return "SpinalCord"
    if any(x in s for x in ["larynx", "lar"]):
        return "Larynx"
    if any(x in s for x in ["oral", "mucosa"]):
        return "OralCavity"
    if any(x in s for x in ["ptv", "planning"]):
        return "PTV"
    if any(x in s for x in ["gtv", "gross"]):
        return "GTV"
    if any(x in s for x in ["ctv", "clinical"]):
        return "CTV"
    
    return raw.title().replace(" ", "")

ORG_TYPE = {
    "SpinalCord": "serial",
    "Parotid": "parallel",
    "OralCavity": "parallel",
    "Larynx": "mixed",
}

# ── header regex table ─────────────────────────────────────────────────────────
RX = {
    "pid": re.compile(r"Patient\s+ID\s*[:=]\s*(.+)", re.I),
    "pname": re.compile(r"Patient\s+Name\s*[:=]\s*(.+)", re.I),
    "agesx": re.compile(r"(\d{1,3})\s*YRS?[/\s]*(M|F)", re.I),
    "sex": re.compile(r"\b(Male|Female|M\.|F\.)\b", re.I),
    "age": re.compile(r"(\d{1,3})\s*YRS?", re.I),
    "diag": re.compile(r"Ca\.\s*([A-Za-z ]+)", re.I),
    "min": re.compile(r"Min\s*dose.*[:=]\s*([\d.]+)", re.I),
    "max": re.compile(r"Max\s*dose.*[:=]\s*([\d.]+)", re.I),
    "mean": re.compile(r"Mean\s*dose.*[:=]\s*([\d.]+)", re.I),
    "tpd": re.compile(r"Prescribed.*dose.*[:=]\s*([\d.]+)", re.I),
    "dpf": re.compile(r"(?:Dose\s*per\s*Fraction|DPF).*[:=]\s*([\d.]+)", re.I),
}

# ── helpers ───────────────────────────────────────────────────────────────────-

def to_gy(x: float) -> float:
    """Original TPS often exports cGy; convert >150 ⇒ assume cGy → Gy."""
    return x / 100 if x > 150 else x


def uniq_id(stem: str) -> str:
    return f"ID_{hashlib.md5(stem.encode()).hexdigest()[:6]}"


# ── DVH type detection & conversion ───────────────────────────────────────────

def is_cumulative(vol: np.ndarray) -> bool:
    """Heuristic: cumulative DVH is monotonically non‑increasing."""
    return np.all(np.diff(vol) <= 1e-6)


def cum_to_diff(vol_cum: np.ndarray) -> np.ndarray:
    diff = np.empty_like(vol_cum)
    diff[:-1] = vol_cum[:-1] - vol_cum[1:]
    diff[-1] = vol_cum[-1]
    return diff


def diff_to_cum(vol_diff: np.ndarray) -> np.ndarray:
    return vol_diff[::-1].cumsum()[::-1]


# ── main txt‑parser ───────────────────────────────────────────────────────────

def parse_txt(path: Path):
    meta: Dict[str, object] = defaultdict(lambda: np.nan)
    dose: List[float] = []
    vol: List[float] = []

    for raw in path.read_text(errors="ignore").splitlines():
        # Header parsing
        for k, rx in RX.items():
            if (m := rx.search(raw)):
                if k in ("min", "max", "mean", "tpd", "dpf"):
                    meta[k] = to_gy(float(m.group(1)))
                elif k == "agesx":
                    meta["Age"] = float(m.group(1))
                    meta["Sex"] = m.group(2).upper()
                elif k == "sex":
                    meta["Sex"] = m.group(1)[0].upper()
                else:
                    meta[k] = m.group(1).strip()

        if raw.lower().startswith("structure"):
            meta["OrganRaw"] = raw.split(":", 1)[-1].strip()
            continue

        line = raw.lstrip()
        if not line or (not line[0].isdigit() and line[0] != "-"):
            continue
        parts = re.split(r"[,\s]+", line)
        try:
            dose.append(float(parts[0]))
            vol.append(float(parts[-1]))
        except ValueError:
            continue

    if not dose:
        return None

    D = np.array(dose)
    V = np.array(vol)
    if D.max() > 150:  # cGy → Gy
        D = D / 100.0

    organ = canon(meta.get("OrganRaw", path.stem))

    # Clean patient name
    if "pname" in meta:
        name = meta["pname"]
        name = re.split(r"[,/()]", name, 1)[0]
        name = re.sub(r"\d.*", "", name)
        meta["pname"] = name.strip()

    return meta, organ, D, V


# ── derived DVH metrics (unchanged) ───────────────────────────────────────────

def metrics(cum_D: np.ndarray, cum_V: np.ndarray, meta):
    Vr = cum_V / cum_V[0] * 100.0
    hdr_mean = pd.to_numeric(meta.get("mean"), errors="coerce")
    meanD = (
        hdr_mean
        if not np.isnan(hdr_mean)
        else _trapz(Vr * cum_D, cum_D) / _trapz(Vr, cum_D)
    )
    hdr_max = pd.to_numeric(meta.get("max"), errors="coerce")
    vmax = hdr_max if not np.isnan(hdr_max) else cum_D.max()
    hdr_min = pd.to_numeric(meta.get("min"), errors="coerce")
    first_drop = cum_D[np.where(Vr < 99.5)[0][0]] if (Vr < 99.5).any() else cum_D.min()
    vmin = hdr_min if (not np.isnan(hdr_min) and hdr_min <= vmax) else first_drop
    modal = cum_D[np.argmax(-np.diff(np.r_[Vr[0], Vr]))]
    median = np.interp(50, Vr[::-1], cum_D[::-1]) if Vr.min() <= 50 else np.nan
    return {
        "MeanDose(Gy)": meanD,
        "MaxDose(Gy)": vmax,
        "MinDose(Gy)": vmin,
        "MedianDose(Gy)": median,
        "ModalDose(Gy)": modal,
    }


# ── main builder ─────────────────────────────────────────────────────────────

def validate_dvh_physics(D: np.ndarray, V_cum: np.ndarray, V_diff: np.ndarray) -> Dict[str, any]:
    """
    Validate DVH physics consistency. Returns FLAG (not FAIL) if issues found.
    
    Parameters
    ----------
    D : np.ndarray
        Dose array (Gy)
    V_cum : np.ndarray
        Cumulative volume array (cm³)
    V_diff : np.ndarray
        Differential volume array (cm³)
    
    Returns
    -------
    Dict with validation results:
        - flag: bool (True if physics issues detected)
        - warnings: List[str] (list of warnings)
        - corrections_applied: List[str] (list of corrections)
    """
    warnings = []
    corrections = []
    flag = False
    
    # Check 1: Dose should be ascending
    if not np.all(np.diff(D) >= 0):
        flag = True
        warnings.append("Dose array not strictly ascending")
        # Sort by dose
        sort_idx = np.argsort(D)
        D = D[sort_idx]
        V_cum = V_cum[sort_idx]
        V_diff = V_diff[sort_idx]
        corrections.append("Sorted dose array")
    
    # Check 2: Cumulative DVH should be non-increasing
    if not np.all(np.diff(V_cum) <= 1e-6):
        flag = True
        warnings.append("Cumulative DVH not monotonically non-increasing")
        corrections.append("Reconstructed cumulative DVH from differential")
    
    # Check 3: Differential DVH should be non-negative
    if np.any(V_diff < -1e-6):
        flag = True
        warnings.append("Differential DVH has negative values")
        V_diff = np.maximum(V_diff, 0)
        corrections.append("Clipped negative differential volumes to zero")
    
    # Check 4: Volume conservation (cumulative should match differential sum)
    if len(V_cum) > 0 and len(V_diff) > 0:
        diff_sum = np.sum(V_diff)
        cum_max = V_cum[0] if len(V_cum) > 0 else 0
        if abs(diff_sum - cum_max) > 0.01 * cum_max:  # 1% tolerance
            flag = True
            warnings.append(f"Volume conservation mismatch: diff_sum={diff_sum:.2f}, cum_max={cum_max:.2f}")
    
    # Check 5: Dose range sanity
    if D.max() > 200:  # Likely in cGy
        flag = True
        warnings.append(f"High maximum dose ({D.max():.1f} Gy) - verify units")
    
    return {
        "flag": flag,
        "warnings": warnings,
        "corrections_applied": corrections,
        "D": D,
        "V_cum": V_cum,
        "V_diff": V_diff
    }


def detect_structure_type(organ: str) -> str:
    """
    Detect if structure is TARGET or OAR.
    
    Parameters
    ----------
    organ : str
        Organ name (normalized)
    
    Returns
    -------
    str
        "TARGET" or "OAR"
    """
    target_keywords = {"PTV", "GTV", "CTV", "Tumor", "Target"}
    organ_upper = organ.upper()
    if any(kw in organ_upper for kw in target_keywords):
        return "TARGET"
    return "OAR"


def build(src: Path, dst: Path, use_universal_parser: bool = True):
    """
    Build processed DVH files from source (CANONICAL DVH ENGINE).
    
    This is the SINGLE SOURCE OF TRUTH for DVH processing.
    Both TCP and NTCP use this engine.
    
    Parameters
    ----------
    src : Path
        Source directory or file
    dst : Path
        Destination directory
    use_universal_parser : bool, default True
        If True, use UniversalDVHParser for intelligent format detection.
        If False, use legacy parser (txt files only).
    """
    dst.mkdir(parents=True, exist_ok=True)
    cdir = dst / "cDVH_csv"  # cumulative
    ddir = dst / "dDVH_csv"  # differential
    cdir.mkdir(exist_ok=True)
    ddir.mkdir(exist_ok=True)

    rows = []
    validation_flags = []  # Store validation results
    idmap: Dict[str, str] = OrderedDict()
    n = 1

    # Use UniversalDVHParser if available and requested
    if use_universal_parser and UNIVERSAL_PARSER_AVAILABLE:
        # Find all DVH files (txt, csv, dcm)
        files = list(src.glob("*.txt")) + list(src.glob("*.csv")) + list(src.glob("*.dcm"))
        
        for file_path in sorted(files):
            try:
                parser = UniversalDVHParser(file_path)
                metadata, dvh_data = parser.parse()
                
                # Extract information
                patient_id = metadata.get('patient_id') or uniq_id(file_path.stem)
                structure_name = metadata.get('structure_name', file_path.stem)
                organ = canon(structure_name)
                
                # Map patient ID
                if patient_id not in idmap:
                    idmap[patient_id] = f"PT{n:03d}"
                    n += 1
                ano = idmap[patient_id]
                
                # Get DVH data
                D = dvh_data['Dose[Gy]'].values
                V_raw = dvh_data['Volume[cm3]'].values
                
                # Detect DVH type & convert
                detected_dvh_type = None
                if metadata.get('dvh_type') == 'cumulative':
                    V_cum = V_raw.copy()
                    V_diff = parser.convert_to_differential(dvh_data)['Volume[cm3]'].values
                    detected_dvh_type = 'cumulative'
                elif metadata.get('dvh_type') == 'differential':
                    V_diff = V_raw.copy()
                    V_cum = parser.convert_to_cumulative(dvh_data)['Volume[cm3]'].values
                    detected_dvh_type = 'differential'
                else:
                    # Auto-detect
                    if is_cumulative(V_raw):
                        V_cum = V_raw.copy()
                        V_diff = cum_to_diff(V_cum)
                        detected_dvh_type = 'cumulative'
                    else:
                        V_diff = V_raw.copy()
                        V_cum = diff_to_cum(V_diff)
                        detected_dvh_type = 'differential'
                
                # Validate DVH physics (FLAG, not FAIL)
                validation_result = validate_dvh_physics(D, V_cum, V_diff)
                D = validation_result["D"]
                V_cum = validation_result["V_cum"]
                V_diff = validation_result["V_diff"]
                
                # Detect structure type
                structure_type = detect_structure_type(organ)
                
                # Store validation metadata
                validation_flags.append({
                    "Patient_AnoID": ano,
                    "Organ": organ,
                    "dvh_type": detected_dvh_type,
                    "structure_type": structure_type,
                    "source_format": metadata.get('source_format', 'unknown'),
                    "flag": validation_result["flag"],
                    "warnings": "; ".join(validation_result["warnings"]) if validation_result["warnings"] else "",
                    "corrections_applied": "; ".join(validation_result["corrections_applied"]) if validation_result["corrections_applied"] else ""
                })
                
                # Write CSVs
                pd.DataFrame({"Dose[Gy]": D, "Volume[cm3]": V_cum}).to_csv(
                    cdir / f"{ano}_{organ}.csv", index=False
                )
                pd.DataFrame({"Dose[Gy]": D, "Volume[cm3]": V_diff}).to_csv(
                    ddir / f"{ano}_{organ}.csv", index=False
                )
                
                # Calculate metrics (using cumulative DVH)
                meta_dict = {
                    "pid": patient_id,
                    "pname": metadata.get('patient_name', np.nan),
                    "OrganRaw": structure_name,
                    "mean": np.nan,
                    "max": np.nan,
                    "min": np.nan,
                }
                
                rows.append(
                    {
                        "PatientId": patient_id,
                        "Patient_AnoID": ano,
                        "PatientName": meta_dict.get("pname", np.nan),
                        "Sex": np.nan,
                        "Age": np.nan,
                        "Diagnosis": np.nan,
                        "Organ": organ,
                        "OrganType": ORG_TYPE.get(organ, "mixed"),
                        **metrics(D, V_cum, meta_dict),
                        "TPD(Gy)": np.nan,
                        "DPF(Gy)": np.nan,
                    }
                )
                
            except Exception as e:
                print(f"  Warning:  {file_path.name}: {str(e)} → skipped")
                continue
    
    else:
        # Legacy parser (txt files only)
        for txt in sorted(src.glob("*.txt")):
            parsed = parse_txt(txt)
            if parsed is None:
                print(f"  Warning:  {txt.name}: no DVH rows → skipped")
                continue
            meta, org, D, V_raw = parsed

            # Detect DVH type & convert
            detected_dvh_type = None
            if is_cumulative(V_raw):
                V_cum = V_raw.copy()
                V_diff = cum_to_diff(V_cum)
                detected_dvh_type = 'cumulative'
            else:
                V_diff = V_raw.copy()
                V_cum = diff_to_cum(V_diff)
                detected_dvh_type = 'differential'

            pid = meta.get("pid") or uniq_id(txt.stem)
            if pid not in idmap:
                idmap[pid] = f"PT{n:03d}"
                n += 1
            ano = idmap[pid]
            
            # Validate DVH physics (FLAG, not FAIL)
            validation_result = validate_dvh_physics(D, V_cum, V_diff)
            D = validation_result["D"]
            V_cum = validation_result["V_cum"]
            V_diff = validation_result["V_diff"]
            
            # Detect structure type
            structure_type = detect_structure_type(org)
            
            # Store validation metadata
            validation_flags.append({
                "Patient_AnoID": ano,
                "Organ": org,
                "dvh_type": detected_dvh_type,
                "structure_type": structure_type,
                "source_format": "txt",
                "flag": validation_result["flag"],
                "warnings": "; ".join(validation_result["warnings"]) if validation_result["warnings"] else "",
                "corrections_applied": "; ".join(validation_result["corrections_applied"]) if validation_result["corrections_applied"] else ""
            })

            # Write CSVs
            pd.DataFrame({"Dose[Gy]": D, "Volume[cm3]": V_cum}).to_csv(
                cdir / f"{ano}_{org}.csv", index=False
            )
            pd.DataFrame({"Dose[Gy]": D, "Volume[cm3]": V_diff}).to_csv(
                ddir / f"{ano}_{org}.csv", index=False
            )

            rows.append(
                {
                    "PatientId": pid,
                    "Patient_AnoID": ano,
                    "PatientName": meta.get("pname", np.nan),
                    "Sex": meta.get("Sex", np.nan),
                    "Age": meta.get("Age", np.nan),
                    "Diagnosis": meta.get("diag", np.nan),
                    "Organ": org,
                    "OrganType": ORG_TYPE.get(org, "mixed"),
                    **metrics(D, V_cum, meta),
                    "TPD(Gy)": meta.get("tpd", np.nan),
                    "DPF(Gy)": meta.get("dpf", np.nan),
                }
            )

    # Workbook summary
    df = pd.DataFrame(rows).sort_values(["Patient_AnoID", "Organ"])
    
    # Add validation metadata columns
    if validation_flags:
        validation_df = pd.DataFrame(validation_flags)
        # Merge validation flags into main dataframe
        df = df.merge(validation_df, on=["Patient_AnoID", "Organ"], how="left")
    else:
        # Add empty columns if no validation data
        df["dvh_type"] = ""
        df["structure_type"] = ""
        df["source_format"] = ""
        df["flag"] = False
        df["warnings"] = ""
        df["corrections_applied"] = ""
    
    df.to_excel(dst / "processed_dvh.xlsx", index=False)
    
    # Save validation metadata separately
    if validation_flags:
        validation_df = pd.DataFrame(validation_flags)
        validation_df.to_csv(dst / "dvh_validation_metadata.csv", index=False)
        flagged_count = sum(1 for v in validation_flags if v["flag"])
        if flagged_count > 0:
            print(f"  [FLAG] {flagged_count} DVH(s) have physics consistency warnings (non-blocking)")

    organs = sorted(set(r["Organ"] for r in rows))
    patients = sorted(set(r["PatientId"] for r in rows))
    print(
        f"  processed_dvh.xlsx  +  {len(rows)}×2 CSVs → {dst}\n"
        f" Patients: {len(patients)}   Organs: {organs}"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="rbGyanX v1.0 - DVH Preprocessing: Multiple formats → Excel + cumulative & differential CSVs"
    )
    ap.add_argument("input_path", help="Input file or directory containing DVH files")
    ap.add_argument("--outdir", default="DVH_Preproc_Out", help="Output directory")
    ap.add_argument("--legacy", action="store_true", 
                   help="Use legacy parser (txt files only, for backward compatibility)")
    args = ap.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    output_path = Path(args.outdir).expanduser().resolve()
    
    use_universal = not args.legacy
    
    if use_universal and UNIVERSAL_PARSER_AVAILABLE:
        print(f"\n{'='*70}")
        print(f"rbGyanX v1.0 - Intelligent DVH Preprocessing")
        print(f"{'='*70}")
        print(f"Using UniversalDVHParser for format auto-detection")
        print(f"{'='*70}\n")
    
    build(input_path, output_path, use_universal_parser=use_universal)
