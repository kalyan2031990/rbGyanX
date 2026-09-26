"""
Real-dosiomics resume (v1.3.0).

`analysis/dosiomics/real_dosiomics.py` used to hold every patient in memory and write only at the
end, so a stop on an 8 GB machine lost the whole run. It now checkpoints each patient after it
finishes. The property that matters is that a killed run resumes without recomputing a patient it
already finished, and that `--limit` batches continue rather than restart.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pydicom
import pytest

import dicom_io.cohort_discovery as cohort_discovery

SCRIPT = Path(__file__).resolve().parents[1] / "analysis" / "dosiomics" / "real_dosiomics.py"


def _module():
    spec = importlib.util.spec_from_file_location("real_dosiomics", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_killed_run_resumes_without_recomputing(tmp_path, monkeypatch):
    mod = _module()
    keys = [f"RAW{i}" for i in range(5)]
    mans = [
        SimpleNamespace(
            patient_key=k,
            degraded_mode="FULL",
            rtstruct_path=tmp_path / f"{k}_rs.dcm",
            rtdose_path=tmp_path / f"{k}_rd.dcm",
        )
        for k in keys + ["UNMAPPED"]
    ]
    map_csv = tmp_path / "map.csv"
    map_csv.write_text(
        "raw_patient_key,pseudonym\n" + "".join(f"{k},HN{i:03d}\n" for i, k in enumerate(keys))
    )
    out = tmp_path / "out"

    monkeypatch.setattr(cohort_discovery, "discover_cohort", lambda staging: mans)
    rois = [SimpleNamespace(ROIName="Parotid_L"), SimpleNamespace(ROIName="SpinalCord")]
    monkeypatch.setattr(
        pydicom, "dcmread", lambda *a, **k: SimpleNamespace(StructureSetROISequence=rois)
    )

    calls: list[str] = []
    kill_at: list[str] = ["RAW2"]

    def fake_organ_features(rtdose, rtstruct, roi_names, voxel_mm=3.0, skips=None):
        key = Path(rtdose).name.split("_")[0]
        if key in kill_at:
            raise KeyboardInterrupt  # not caught by the script's `except Exception`: an abrupt stop
        calls.append(key)
        if key == "RAW3":
            skips.append({"roi": "SpinalCord", "reason": "only 12 voxels at 3.0 mm (< 64)"})
            return {}
        return {"rdx_Parotid_L_fo_mean": float(len(key))}

    monkeypatch.setattr(mod, "organ_features", fake_organ_features)

    def run(*extra):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "real_dosiomics.py",
                "--staging",
                str(tmp_path),
                "--map-csv",
                str(map_csv),
                "--out",
                str(out),
                *extra,
            ],
        )
        return mod.main()

    # first run is killed on the third patient
    with pytest.raises(KeyboardInterrupt):
        run()
    assert calls == ["RAW0", "RAW1"]
    ck = out / "_checkpoint_dosiomics.jsonl"
    assert [json.loads(x)["pseudonym"] for x in ck.read_text().splitlines()] == ["HN000", "HN001"]
    # a hard kill can also leave a line cut short mid-write; it must not block the resume
    with open(ck, "a", encoding="utf-8") as fh:
        fh.write('{"pseudonym": "HN002", "feat')

    # resume in a batch of two: continues at the third patient, recomputes nothing already done
    kill_at.clear()
    calls.clear()
    assert run("--limit", "2") == 0
    assert calls == ["RAW2", "RAW3"]

    # the next batch picks up the one remaining patient
    calls.clear()
    assert run("--limit", "2") == 0
    assert calls == ["RAW4"]

    assert [r["pseudonym"] for r in _rows(out / "real_dosiomics_TCIA_HN_wide.csv")] == [
        "HN000",
        "HN001",
        "HN002",
        "HN004",
    ]
    skipped = _rows(out / "real_dosiomics_skipped.csv")
    assert {"pseudonym": "HN003", "reason": "no maskable ROI"} in skipped
    assert {"pseudonym": "", "reason": "not in the pseudonym map"} in skipped
    assert _rows(out / "real_dosiomics_roi_skipped.csv") == [
        {"pseudonym": "HN003", "roi": "SpinalCord", "reason": "only 12 voxels at 3.0 mm (< 64)"}
    ]
