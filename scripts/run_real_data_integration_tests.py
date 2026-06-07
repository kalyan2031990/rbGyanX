#!/usr/bin/env python3
"""
Integration tests on real data under rbgyanx_test_data.

Runs Step 1 ingest, clinical adapter, and optional engine Step 3
for BASIC/ADVANCED x TCP/NTCP modes where data exists.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_DATA = Path(r"C:\Users\Sampa\OneDrive\Desktop\input_folders\rbgyanx_test_data")

SCENARIOS = [
    {
        "name": "TPS_Eclipse_HN57",
        "input": TEST_DATA / "HN57_OAR_Eclipse",
        "clinical": TEST_DATA / "clinical_data" / "treatment_params_toxicity_HN57_input.xlsx",
        "source": "tps_txt",
        "site": "HeadNeck",
        "modes": ["NTCP_ONLY", "TCP_NTCP"],
        "gui_modes": ["basic", "advanced"],
    },
    {
        "name": "TPS_CSV_HN57",
        "input": TEST_DATA / "HN57_dDVH_CSV",
        "clinical": TEST_DATA / "clinical_data" / "treatment_params_toxicity_HN57_input.xlsx",
        "source": "tps_txt",
        "site": "HeadNeck",
        "modes": ["NTCP_ONLY"],
        "gui_modes": ["advanced"],
    },
    {
        "name": "DICOM_samples",
        "input": TEST_DATA / "DICOM_samples",
        "clinical": None,
        "source": "dicom",
        "site": "HeadNeck",
        "modes": ["TCP_NTCP", "NTCP_ONLY", "TCP_ONLY"],
        "gui_modes": ["basic", "advanced"],
    },
]


def run_step1(input_path: Path, out_dir: Path, source: str) -> dict:
    from rbgyanx.logic.input_router import run_step1_ingest

    return run_step1_ingest(input_path, out_dir / "processed_DVH", source_pref=source)


def run_clinical(clinical_path: Path, out_dir: Path, analysis_mode: str) -> dict:
    from clinical.clinical_adapter import adapt_clinical_data

    mapped, status, messages, std = adapt_clinical_data(clinical_path, analysis_mode, out_dir / "adapted_clinical")
    return {
        "status": status,
        "messages": messages,
        "mapped": {k: (v is not None) for k, v in mapped.items()},
        "standardized": str(std) if std else None,
    }


def run_engine(input_path: Path, out_dir: Path, endpoint: str, mode: str, site: str) -> dict:
    from rbgyanx.logic.engine_bridge import is_engine_available, map_site_override, run_engine_analysis

    if not is_engine_available():
        return {"skipped": True, "reason": "engine not installed"}
    site_key = map_site_override(site)
    result, logs = run_engine_analysis(
        input_dir=input_path,
        output_dir=out_dir,
        endpoint=endpoint,  # type: ignore[arg-type]
        mode=mode,
        site_override=site_key,
        enable_ml=(mode == "advanced"),
        cohort=True,
    )
    return {
        "exit_code": result.exit_code,
        "tcp_rows": len(result.tcp_results),
        "ntcp_rows": len(result.ntcp_results),
        "logs": logs[-5:],
    }


def main() -> int:
    if not TEST_DATA.is_dir():
        print(f"[X] Test data not found: {TEST_DATA}")
        return 1

    base_out = TEST_DATA / "_integration_test_output"
    if base_out.exists():
        shutil.rmtree(base_out, ignore_errors=True)
    base_out.mkdir(parents=True, exist_ok=True)

    report = []
    failures = 0
    step1_cache: dict[str, dict] = {}

    for sc in SCENARIOS:
        inp = sc["input"]
        if not inp.exists():
            report.append({"scenario": sc["name"], "error": f"missing input {inp}"})
            failures += 1
            continue

        for gui_mode in sc["gui_modes"]:
            for analysis_mode in sc["modes"]:
                tag = f"{sc['name']}_{gui_mode}_{analysis_mode}"
                run_dir = base_out / tag
                run_dir.mkdir(parents=True, exist_ok=True)
                entry = {"scenario": tag, "input": str(inp), "gui_mode": gui_mode, "analysis_mode": analysis_mode}

                try:
                    cache_key = f"{inp}|{sc['source']}"
                    if cache_key in step1_cache:
                        s1 = step1_cache[cache_key]
                        # copy processed_DVH artifacts
                        src_p = base_out / "_step1_cache" / Path(cache_key.replace("|", "_"))
                        dst_p = run_dir / "processed_DVH"
                        if (src_p / "cDVH_csv").exists():
                            shutil.copytree(src_p, dst_p, dirs_exist_ok=True)
                    else:
                        s1 = run_step1(inp, run_dir, sc["source"])
                        cache_dir = base_out / "_step1_cache" / cache_key.replace("|", "_")
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        pdvh = run_dir / "processed_DVH"
                        if pdvh.exists():
                            shutil.copytree(pdvh, cache_dir, dirs_exist_ok=True)
                        step1_cache[cache_key] = s1
                    entry["step1"] = {
                        "processed": s1.get("processed"),
                        "total": s1.get("total_files"),
                        "failed": s1.get("failed"),
                        "input_kind": s1.get("input_kind"),
                    }
                    ok_step1 = s1.get("processed", 0) > 0 or s1.get("input_kind") == "dicom"
                    if not ok_step1:
                        entry["step1"]["FAIL"] = True
                        failures += 1

                    if sc.get("clinical") and Path(sc["clinical"]).is_file():
                        entry["clinical"] = run_clinical(Path(sc["clinical"]), run_dir, analysis_mode)

                    if sc["source"] == "dicom" and analysis_mode in ("TCP_NTCP", "TCP_ONLY", "NTCP_ONLY"):
                        ep = (
                            "both"
                            if analysis_mode == "TCP_NTCP"
                            else ("tcp" if analysis_mode == "TCP_ONLY" else "ntcp")
                        )
                        eng_dir = run_dir / "engine_out"
                        eng_dir.mkdir(parents=True, exist_ok=True)
                        entry["engine"] = run_engine(inp, eng_dir, ep, gui_mode, sc["site"])
                        if entry["engine"].get("skipped"):
                            entry["engine_note"] = "skipped"
                        elif entry["engine"].get("exit_code", 1) != 0:
                            failures += 1
                            entry["engine"]["FAIL"] = True

                except Exception as exc:
                    entry["error"] = str(exc)
                    entry["trace"] = traceback.format_exc()
                    failures += 1

                report.append(entry)
                status = "OK" if "FAIL" not in json.dumps(entry) and "error" not in entry else "FAIL"
                print(f"[{status}] {tag}")
                if entry.get("step1"):
                    print(f"       step1: {entry['step1']}")
                if entry.get("clinical"):
                    print(f"       clinical: {entry['clinical'].get('status')} mapped={entry['clinical'].get('mapped')}")
                if entry.get("engine"):
                    print(f"       engine: {entry['engine']}")

    report_path = base_out / "integration_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {report_path}")
    print(f"Failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
