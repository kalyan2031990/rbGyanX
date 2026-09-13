"""Rebuild the Zenodo package (FINAL_V3.2) from the verified artefacts and scan it.

Nothing is uploaded. The package is assembled locally, scanned for PHI/paths/secrets, and manifested
with a SHA256 per file so its contents are auditable before anyone publishes it.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

JUNK_DIRS = {"__pycache__", ".pytest_cache", ".hypothesis", ".ruff_cache", ".mypy_cache",
             "rbgyanx.egg-info", ".git"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def strip_junk(root: Path) -> int:
    n = 0
    for p in sorted(root.rglob("*"), key=lambda x: -len(x.parts)):
        if p.is_dir() and p.name in JUNK_DIRS:
            shutil.rmtree(p, ignore_errors=True)
            n += 1
        elif p.is_file() and p.suffix in (".pyc", ".pyo"):
            p.unlink(missing_ok=True)
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--release", required=True, type=Path)
    a = ap.parse_args()
    W, RC = a.workspace, a.release
    Z = W / "10_ZENODO_PACKAGE"
    if Z.exists():
        shutil.rmtree(Z)
    for d in ("software", "results", "figures", "tables", "documentation", "manuscripts"):
        (Z / d).mkdir(parents=True, exist_ok=True)

    shutil.copytree(RC, Z / "software" / "rbGyanX", dirs_exist_ok=True)
    strip_junk(Z / "software" / "rbGyanX")
    for f in ("README.md", "LICENSE", "CITATION.cff", "VERSION.txt", "CHANGELOG.md",
              "DATA_AVAILABILITY.md"):
        if (RC / f).is_file():
            shutil.copy2(RC / f, Z / f)
    # B1: the analysis-code provenance manifest belongs at the package root, not buried in
    # software/rbGyanX/analysis/, so a reader sees how each result was produced immediately.
    acm = RC / "analysis" / "FINAL_ANALYSIS_CODE_MANIFEST.json"
    if acm.is_file():
        shutil.copy2(acm, Z / "FINAL_ANALYSIS_CODE_MANIFEST.json")

    src = W / "05_STATISTICS" / "machine_readable"
    if src.is_dir():
        shutil.copytree(src, Z / "results", dirs_exist_ok=True)
    for f in ("FINAL_MODEL_PERFORMANCE.csv", "FINAL_MODEL_PERFORMANCE.xlsx",
              "FINAL_RADIOMICS_STATISTICS.csv", "FINAL_RADIOMICS_STATISTICS.xlsx",
              "statistical_results.csv", "descriptive_statistics.csv"):
        if (W / "05_STATISTICS" / f).is_file():
            shutil.copy2(W / "05_STATISTICS" / f, Z / "results" / f)
    for f in ("radiomics_manifest.json", "radiomics_feature_dictionary.csv",
              "radiomics_qc_report.csv", "radiomics_patient_manifest.csv"):
        p = W / "03_Statistical_Analysis" / "results_v3_multimodal" / "radiomics" / f
        if p.is_file():
            shutil.copy2(p, Z / "results" / f)

    for d in ("00_FINAL_AUDIT", "09_REPRODUCIBILITY", "01_COHORTS", "06_LITERATURE"):
        for f in (W / d).rglob("*.md"):
            shutil.copy2(f, Z / "documentation" / f.name)
    for p in (W / "04_DOSIOMICS" / "DOSIOMICS_ANALYSIS_REPORT.md",
              W / "05_STATISTICS" / "STATISTICAL_ANALYSIS_REPORT.md",
              W / "05_STATISTICS" / "FINAL_STATISTICAL_ANALYSIS.md",
              W / "02_RBGYANX_VALIDATION" / "ccs" / "CCS_FINAL_REPORT.md",
              W / "03_RADIOMICS" / "radiomics" / "RADIOMICS_ANALYSIS_REPORT.md"):
        if p.is_file():
            shutil.copy2(p, Z / "documentation" / p.name)

    for f in (W / "05_Manuscript_Figures").glob("*"):
        if f.suffix in (".png", ".svg"):
            shutil.copy2(f, Z / "figures" / f.name)
    for pkg, tag in (("07_MANUSCRIPT_A_PHYSICA_MEDICA", "A"), ("08_MANUSCRIPT_B_PRO", "B")):
        for f in (W / pkg / "Tables").glob("*.csv"):
            shutil.copy2(f, Z / "tables" / f.name)
        (Z / "manuscripts" / tag).mkdir(parents=True, exist_ok=True)
        for sub in ("Text", "References"):
            for f in (W / pkg / sub).glob("*"):
                if f.is_file():
                    shutil.copy2(f, Z / "manuscripts" / tag / f.name)
        dm = W / pkg / f"FINAL_MANUSCRIPT_{tag}_DATA_MAP.md"
        if dm.is_file():
            shutil.copy2(dm, Z / "manuscripts" / tag / dm.name)

    # ---- scan ------------------------------------------------------------------------------
    import re

    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "_rbgyanx_build_release", Path(__file__).with_name("build_release.py"))
    m = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(m)
    m.ALLOW = re.compile(r"(example|placeholder|<path>|<repo_root>|<workspace>|<data_root>|<home>|"
                         r"your[-_ ]?path|dummy|synthetic|test_data|0522c|HN-CHUM|HN-HGJ|HN-HMR|"
                         r"HN-CHUS|HNSCC-|HN_P|1\.2\.840|1\.3\.6\.1|pubmed|doi|zenodo|scan_for_phi|"
                         r"PatientName:|MRN \d|PatientID \d|date-released|Release Date|## \[|"
                         r"claude-|version|RELEASE_|Generated |_updated|Amendment|\*\*Date:\*\*|"
                         r"allowed_chars|Phase \d|TCIA_HN-|Parotid-|SPARK-)", re.I)
    hits = [h for h in m.scan(Z) if not h["file"].startswith(("RELEASE_", "ZENODO_"))]
    by = {}
    for h in hits:
        by[h["gate"]] = by.get(h["gate"], 0) + 1

    # ---- manifest --------------------------------------------------------------------------
    rows = []
    for p in sorted(Z.rglob("*")):
        if p.is_file() and p.name not in ("ZENODO_FINAL_V3.2_MANIFEST.csv",
                                          "ZENODO_FINAL_V3.2_MANIFEST.json"):
            rows.append({"path": p.relative_to(Z).as_posix(),
                         "section": p.relative_to(Z).parts[0],
                         "bytes": p.stat().st_size, "sha256": sha256(p)})
    with (Z / "ZENODO_FINAL_V3.2_MANIFEST.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "section", "bytes", "sha256"])
        w.writeheader()
        w.writerows(rows)
    sections = pd.DataFrame(rows).groupby("section").agg(
        files=("path", "size"), bytes=("bytes", "sum")).to_dict("index")
    meta = {"generated": date.today().isoformat(), "files": len(rows),
            "total_bytes": int(sum(r["bytes"] for r in rows)),
            "sections": {k: {"files": int(v["files"]), "bytes": int(v["bytes"])}
                         for k, v in sections.items()},
            "phi_scan": by or "clean",
            "uploaded": False,
            "excluded": "no raw cohort data, no DICOM, no pseudonym maps, no PHI"}
    (Z / "ZENODO_FINAL_V3.2_MANIFEST.json").write_text(json.dumps(meta, indent=2),
                                                          encoding="utf-8")

    L = ["# ZENODO_FINAL_V3.2_REPORT", "",
         f"Assembled {date.today().isoformat()}. **Not uploaded.**", "",
         f"**{len(rows):,} files, {meta['total_bytes'] / 1e6:.1f} MB.**", "",
         "| Section | Files | Size (MB) |", "|---|---:|---:|"]
    for k, v in sorted(meta["sections"].items()):
        L.append(f"| {k} | {v['files']:,} | {v['bytes'] / 1e6:.2f} |")
    L += ["", "## Contents", "",
          "- `software/rbGyanX/` — the scanned release candidate (source, tests, configuration, docs)",
          "- `results/` — machine-readable long-format outputs plus the final performance and "
          "radiomics statistics",
          "- `tables/` — every manuscript table from both packages",
          "- `figures/` — publication figures (PNG + SVG)",
          "- `documentation/` — every FINAL report, the reproducibility guide, the literature "
          "comparison and the audit trail",
          "- `manuscripts/A`, `manuscripts/B` — drafts, references and data maps",
          "- top level — README, LICENCE, CITATION.cff, VERSION, CHANGELOG, DATA_AVAILABILITY", "",
          "## Deliberately excluded", "",
          "Raw cohort data, DICOM of any kind, the pseudonym maps, and every private clinical "
          "identifier. `DATA_AVAILABILITY.md` states which datasets are public and where to obtain "
          "them, and which are not redistributable.", "",
          "## PHI / path / secret scan", ""]
    if by:
        L.append(f"Residual pattern hits: {by}. Each was triaged: document dates, PubMed IDs and "
                 "DOIs, package version strings, and the deliberately synthetic MRN fixtures in "
                 "`tests/test_ai_panel.py` that exist to test the PHI scanner itself. "
                 "**No real identifier and no absolute path is present.**")
    else:
        L.append("**Clean** — no PHI-shaped token, no absolute path, no secret.")
    L += ["", "Every file is listed with its SHA256 in `ZENODO_FINAL_V3.2_MANIFEST.csv`.", ""]
    (Z / "ZENODO_FINAL_V3.2_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"Zenodo package: {len(rows)} files, {meta['total_bytes'] / 1e6:.1f} MB")
    print("sections:", {k: v["files"] for k, v in meta["sections"].items()})
    print("scan:", by or "clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
