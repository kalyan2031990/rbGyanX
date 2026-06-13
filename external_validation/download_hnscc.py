#!/usr/bin/env python3
"""
Acquire TCIA Head-Neck-CT-Atlas (215-patient HNSCC RT subset) + clinical spreadsheet.

Uses NBIA REST API for discovery; bulk download via NBIA Data Retriever manifest (.tcia).
HNSCC is under NIH Controlled Data Access — public getSeries returns 0 rows until
a TCIA restricted-use agreement is in place and manifest/retriever is used.

Usage:
  python external_validation/download_hnscc.py --discover-only
  python external_validation/download_hnscc.py --download --manifest path/to/manifest.tcia
  python external_validation/download_hnscc.py --download --install-retriever-hint
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "external_validation" / "data" / "hnscc"
MANIFEST_DIR = ROOT / "external_validation" / "manifests"
NBIA_BASE = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
TARGET_MODALITIES = ("CT", "RTSTRUCT", "RTDOSE", "RTPLAN")
EXPECTED_PATIENTS = 215

COLLECTION = "HNSCC"
ATLAS_DOI = "10.7937/K9/TCIA.2017.umz8dv6s"
PARENT_DOI = "10.7937/k9/tcia.2020.a8sh-7363"
ATLAS_PAGE = "https://www.cancerimagingarchive.net/analysis-result/head-neck-ct-atlas/"
PARENT_PAGE = "https://www.cancerimagingarchive.net/collection/hnscc/"

CITATIONS = """
## Citations (required by TCIA Data Usage Policy)

- Grossberg A, et al. (2017). Data from Head and Neck Cancer CT Atlas (Version 2).
  The Cancer Imaging Archive. DOI: 10.7937/K9/TCIA.2017.umz8dv6s
- Grossberg A, et al. (2018). Imaging and Clinical Data Archive for HNSCC Patients
  Treated with Radiotherapy. Scientific Data 5:180173. DOI: 10.1038/sdata.2018.173
- Clark K, et al. (2013). The Cancer Imaging Archive (TCIA). J Digit Imaging 26(6):1045-1057.
  DOI: 10.1007/s10278-013-9622-7
- Parent collection HNSCC DOI: 10.7937/k9/tcia.2020.a8sh-7363

## DUA compliance

Downloaded data are used only for software pipeline validation, with attribution as above.
Data are not redistributed. Access follows the TCIA Restricted License / NIH Controlled
Data Access Policy where applicable.
"""


def _ensure_dirs() -> None:
    for sub in ("CT", "RTSTRUCT", "RTDOSE", "RTPLAN", "clinical"):
        (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


def query_series(collection: str = COLLECTION) -> pd.DataFrame:
    """Query NBIA getSeries (public API). Empty => controlled access."""
    r = requests.get(
        f"{NBIA_BASE}/getSeries",
        params={"Collection": collection, "format": "json"},
        timeout=300,
    )
    r.raise_for_status()
    if not r.content:
        return pd.DataFrame()
    return pd.DataFrame(r.json())


def discover() -> dict:
    """Print discovery summary; return metadata dict."""
    _ensure_dirs()
    df = query_series(COLLECTION)
    meta: dict = {
        "collection": COLLECTION,
        "api_series_count": len(df),
        "access_note": (
            "Public NBIA getSeries returned 0 rows — HNSCC requires TCIA Data Retriever "
            "and NIH Controlled / Restricted Data Access (see collection page)."
        ),
        "atlas_page": ATLAS_PAGE,
        "parent_page": PARENT_PAGE,
        "expected_patients": EXPECTED_PATIENTS,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }
    if df.empty:
        print("DISCOVERY: 0 public series for Collection=HNSCC (controlled access expected).")
        print(f"  Atlas page: {ATLAS_PAGE}")
        print(f"  Parent page: {PARENT_PAGE}")
        print("  Next: download manifest from TCIA portal -> run with --manifest")
        return meta

    meta["patients"] = int(df["PatientID"].nunique())
    meta["modalities"] = df["Modality"].value_counts().to_dict()
    rt = df[df["Modality"].isin(TARGET_MODALITIES)]
    meta["rt_patients"] = int(rt["PatientID"].nunique()) if not rt.empty else 0
    meta["rt_series"] = len(rt)
    print("DISCOVERY TABLE")
    print(f"  Patients (all):     {meta['patients']}")
    print(f"  RT-modal patients:  {meta['rt_patients']}")
    print(f"  Modalities:         {meta['modalities']}")
    return meta


def find_nbia_retriever() -> Path | None:
    for name in ("NBIADataRetriever", "NBIADataRetriever.exe", "nbia-data-retriever"):
        p = shutil.which(name)
        if p:
            return Path(p)
    candidates = [
        Path(r"C:\Program Files\NBIA Data Retriever\NBIADataRetriever.exe"),
        Path(r"C:\Program Files (x86)\NBIA Data Retriever\NBIADataRetriever.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def run_retriever(manifest: Path, dest: Path) -> int:
    exe = find_nbia_retriever()
    if exe is None:
        print(
            "NBIA Data Retriever not found. Install from TCIA:\n"
            "  https://www.cancerimagingarchive.net/software/NBIA-data-retriever/\n"
            "Then re-run with --manifest <file.tcia>"
        )
        return 127
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [str(exe), "--cli", str(manifest), "-d", str(dest), "-v", "-f"]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


def organize_dicom_by_modality(src: Path) -> dict[str, int]:
    """Move/copy DICOM files under modality subfolders by SOP Class / Modality tag."""
    try:
        import pydicom
    except ImportError:
        print("pydicom required for organize step")
        return {}

    counts: dict[str, int] = {m: 0 for m in TARGET_MODALITIES}
    for dcm in src.rglob("*.dcm"):
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True, force=True)
            mod = str(getattr(ds, "Modality", "") or "").upper()
            if mod in counts:
                rel = dcm.relative_to(src)
                dst = DATA_ROOT / mod / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copy2(dcm, dst)
                counts[mod] += 1
        except Exception:
            continue
    return counts


def scan_local_cohort() -> dict:
    """Sanity report on downloaded data under DATA_ROOT."""
    patients: set[str] = set()
    by_mod: dict[str, set[str]] = {m: set() for m in TARGET_MODALITIES}
    total_dcm = 0
    try:
        import pydicom
    except ImportError:
        pydicom = None

    for mod in TARGET_MODALITIES:
        mod_dir = DATA_ROOT / mod
        if not mod_dir.is_dir():
            continue
        for dcm in mod_dir.rglob("*.dcm"):
            total_dcm += 1
            pid = dcm.parent.name
            if pydicom:
                try:
                    ds = pydicom.dcmread(str(dcm), stop_before_pixels=True, force=True)
                    pid = str(getattr(ds, "PatientID", pid))
                except Exception:
                    pass
            patients.add(pid)
            by_mod[mod].add(pid)

    complete = set.intersection(*(by_mod[m] for m in TARGET_MODALITIES if by_mod[m])) if patients else set()
    clinical_rows = 0
    clin_dir = DATA_ROOT / "clinical"
    for x in clin_dir.glob("*.xlsx"):
        try:
            clinical_rows += len(pd.read_excel(x))
        except Exception:
            pass

    report = {
        "patients_found": len(patients),
        "patients_complete_ct_rtstruct_rtdose": len(complete),
        "patients_missing_modality": len(patients - complete) if patients else 0,
        "total_dicom_files": total_dcm,
        "clinical_spreadsheet_rows": clinical_rows,
        "per_modality_patients": {m: len(by_mod[m]) for m in TARGET_MODALITIES},
    }
    return report


def write_provenance(meta: dict, scan: dict, download_path: str) -> Path:
    out = DATA_ROOT / "DATA_PROVENANCE.md"
    text = f"""# HNSCC Head-Neck-CT-Atlas — data provenance

Generated: {datetime.now(timezone.utc).isoformat()}
Download path: {download_path}

## DOIs
- Head-Neck-CT-Atlas: {ATLAS_DOI}
- HNSCC parent: {PARENT_DOI}

## Discovery
```json
{json.dumps(meta, indent=2)}
```

## Local sanity scan
```json
{json.dumps(scan, indent=2)}
```

{CITATIONS}
"""
    out.write_text(text, encoding="utf-8")
    manifest_json = DATA_ROOT / "download_manifest.json"
    manifest_json.write_text(json.dumps({"meta": meta, "scan": scan}, indent=2), encoding="utf-8")
    return out


def try_fetch_clinical() -> bool:
    """
    Clinical XLSX has no stable public direct URL on TCIA (retriever-only).
    User must place files in data/hnscc/clinical/ after portal download.
    """
    clin = DATA_ROOT / "clinical"
    existing = list(clin.glob("*.xlsx")) + list(clin.glob("*.xls"))
    if existing:
        print(f"Clinical file(s) already present: {[p.name for p in existing]}")
        return True
    print(
        "Clinical spreadsheet: manual download required.\n"
        f"  1. Open {ATLAS_PAGE}\n"
        "  2. Download 'Head-Neck-CT-Atlas Clinical Data' (XLSX) via TCIA Data Retriever\n"
        f"  3. Save to: {clin}\n"
        "  (Optional: Data Dictionary XLSX in the same folder.)"
    )
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--manifest", type=Path, help="Path to .tcia manifest from TCIA portal")
    parser.add_argument("--raw-dest", type=Path, help="NBIA retriever output dir (default: data/hnscc/_raw)")
    args = parser.parse_args()

    _ensure_dirs()
    meta = discover()

    if args.discover_only and not args.download:
        if meta.get("api_series_count", 0) == 0:
            print("\nCannot bulk-download via public API. Provide --manifest after TCIA portal export.")
        return 0

    if not args.download:
        parser.print_help()
        return 0

    download_path = "nbia_api"
    raw = args.raw_dest or (DATA_ROOT / "_raw")
    if args.manifest:
        if not args.manifest.is_file():
            print(f"Manifest not found: {args.manifest}")
            return 1
        rc = run_retriever(args.manifest, raw)
        if rc != 0:
            return rc
        download_path = f"nbia_retriever:{args.manifest.name}"
        print("Organizing DICOM by modality...")
        organize_dicom_by_modality(raw)
    elif meta.get("api_series_count", 0) > 0:
        print("Direct series download via tcia_utils not available; use --manifest.")
        return 1
    else:
        print("No manifest and no public API series — see discovery output.")
        bundled = list(MANIFEST_DIR.glob("*.tcia"))
        if bundled:
            m = bundled[0]
            print(f"Using bundled manifest: {m}")
            rc = run_retriever(m, raw)
            if rc == 0:
                download_path = f"nbia_retriever:{m.name}"
                organize_dicom_by_modality(raw)
            else:
                return rc
        else:
            print(f"Place manifest in {MANIFEST_DIR} or pass --manifest")
            return 1

    try_fetch_clinical()
    scan = scan_local_cohort()
    print("\nSANITY REPORT")
    for k, v in scan.items():
        print(f"  {k}: {v}")
    write_provenance(meta, scan, download_path)

    if scan["patients_complete_ct_rtstruct_rtdose"] < EXPECTED_PATIENTS * 0.9:
        print(
            f"\nWarning: expected ~{EXPECTED_PATIENTS} patients with CT+RTSTRUCT+RTDOSE; "
            f"found {scan['patients_complete_ct_rtstruct_rtdose']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
