#!/usr/bin/env python3
"""Verify Phases 1-5 + integration test harness."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DATA = Path(r"C:\Users\Sampa\OneDrive\Desktop\input_folders\rbgyanx_test_data")
DICOM = TEST_DATA / "DICOM_samples"
ECLIPSE = TEST_DATA / "HN57_OAR_Eclipse"
CSV_DIR = TEST_DATA / "HN57_dDVH_CSV"
CLINICAL = TEST_DATA / "clinical_data" / "treatment_params_toxicity_HN57_input.xlsx"


def check(name: str, ok: bool, detail: str = "") -> bool:
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    all_ok = True

    # Phase 1
    from rbgyanx.utils.numeric_compat import trapz

    all_ok &= check("Phase 1: NumPy trapz compat", trapz([0, 1, 2], [0, 1, 2]) == 2.0)

    from utils.dvh_parser import preprocess_dvh_intelligent

    td = Path(tempfile.mkdtemp())
    try:
        s = preprocess_dvh_intelligent(CSV_DIR, td, file_list=None)
        all_ok &= check(
            "Phase 1: CSV preprocess (no trapz crash)",
            s["failed"] == 0 and s["processed"] == 115,
            f"{s['processed']}/{s['total_files']}",
        )
    finally:
        shutil.rmtree(td, ignore_errors=True)

    # Phase 2 + 5 router
    from rbgyanx.logic.input_router import (
        resolve_input_kind,
        run_step1_ingest,
        validate_input_for_mode,
    )

    all_ok &= check("Phase 2: auto-detect DICOM", resolve_input_kind(DICOM, "auto") == "dicom")
    all_ok &= check("Phase 2: auto-detect TPS", resolve_input_kind(ECLIPSE, "auto") == "dvh_txt")
    ok, errs = validate_input_for_mode(ECLIPSE, basic_mode=True, source_pref="tps_txt")
    all_ok &= check("Phase 2: BASIC allows TPS", ok and not errs, str(errs) if errs else "")

    td2 = Path(tempfile.mkdtemp())
    try:
        s_d = run_step1_ingest(DICOM, td2 / "pdvh", source_pref="dicom")
        manifest = td2 / "pdvh" / "ingest_manifest.json"
        all_ok &= check(
            "Phase 5: DICOM Step 1 manifest",
            manifest.is_file() and s_d.get("input_kind") == "dicom",
        )
        s_e = run_step1_ingest(ECLIPSE, td2 / "eclipse", source_pref="tps_txt")
        all_ok &= check(
            "Phase 1+2: Eclipse Step 1",
            s_e["failed"] == 0 and s_e["processed"] >= 100,
            f"{s_e['processed']}/{s_e['total_files']}",
        )
    finally:
        shutil.rmtree(td2, ignore_errors=True)

    # Phase 3
    from clinical.clinical_adapter import ClinicalDataAdapter

    ad = ClinicalDataAdapter(CLINICAL)
    ad.read_excel()
    ad.map_sheets()
    st, _ = ad.assess_sufficiency("NTCP_ONLY")
    all_ok &= check(
        "Phase 3: clinical sheet split",
        ad.mapped_data["patient_core"] is not None
        and ad.mapped_data["ntcp_outcome"] is not None,
    )
    all_ok &= check("Phase 3: clinical status", st in ("usable", "partial"), st)

    # Phase 4
    from rbgyanx.logic.patient_id_registry import (
        build_auto_mapping,
        collect_clinical_patient_ids,
        collect_dvh_patient_ids,
        write_registry_report,
    )

    td3 = Path(tempfile.mkdtemp())
    try:
        run_step1_ingest(ECLIPSE, td3, source_pref="tps_txt")
        dvh_ids = collect_dvh_patient_ids(td3)
        clinical_ids = collect_clinical_patient_ids(ad.mapped_data["patient_core"])
        mapping = build_auto_mapping(dvh_ids, clinical_ids)
        reg = write_registry_report(td3 / "reg", dvh_ids, clinical_ids, mapping)
        all_ok &= check(
            "Phase 4: patient ID registry",
            reg.is_file() and len(mapping) >= 50,
            f"DVH={len(dvh_ids)} clinical={len(clinical_ids)}",
        )
    finally:
        shutil.rmtree(td3, ignore_errors=True)

    # Phase 5 engine
    from rbgyanx.logic.engine_bridge import _safe_copy2, run_engine_analysis

    td4 = Path(tempfile.mkdtemp()) / "eng"
    td4.mkdir(parents=True)
    try:
        r, _ = run_engine_analysis(
            input_dir=DICOM,
            output_dir=td4,
            endpoint="both",
            mode="basic",
            site_override="HN",
        )
        all_ok &= check("Phase 5: DICOM engine", r.exit_code == 0, f"tcp={len(r.tcp_results)}")
        src = td4 / "site_detection.csv"
        try:
            _safe_copy2(src, src)
            all_ok &= check("Phase 5: safe_copy same-path", True)
        except Exception as exc:
            all_ok &= check("Phase 5: safe_copy same-path", False, str(exc))
    finally:
        shutil.rmtree(td4.parent, ignore_errors=True)

    # Phase 6: GUI wiring exists
    gui = (ROOT / "rbgyanx_gui.py").read_text(encoding="utf-8", errors="ignore")
    all_ok &= check("Phase 6: GUI uses input router", "run_step1_ingest" in gui)
    all_ok &= check("Phase 6: GUI patient registry", "PATIENT_ID_REGISTRY" in gui)

    # Phase 6: integration script
    script = ROOT / "scripts" / "run_real_data_integration_tests.py"
    all_ok &= check("Phase 6: integration test script", script.is_file())

    print("---")
    if all_ok:
        print("ALL 6 PHASES VERIFIED")
        return 0
    print("SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
