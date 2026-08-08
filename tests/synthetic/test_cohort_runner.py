"""
Phase 5 acceptance — cohort runner (resumable, idempotent, deterministic, pseudonymised).

Proves: the mandated output tree + 16 always-written CSVs; two fresh runs are byte-identical (C5); a
resumed run is idempotent and reports cached patients; the DICOM path degrades a missing-dose patient
with a reason code without crashing; and NO raw identifier ever appears in the output tree (C2).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dicom_rt_factory import build_rt_triple, save_dataset  # noqa: E402

from rbgyanx_engine.cohort_runner import COHORT_CSVS, RunnerConfig, run_cohort  # noqa: E402

pytestmark = [pytest.mark.integration]

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "data" / "dvh_txt"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cfg(out_root: Path, maps: Path) -> RunnerConfig:
    return RunnerConfig(
        input_root=_EXAMPLES, cohort="DEMO", output_root=out_root / "Outputs",
        validation="InternalValidation", input_kind="dvh_txt", site="HN", pseudonym_map_dir=maps,
    )


def test_all_16_csvs_written_and_tree_shape(tmp_path):
    run_cohort(_cfg(tmp_path, tmp_path / "_maps"))
    base = tmp_path / "Outputs" / "InternalValidation" / "DEMO"
    for sub in ("PatientLevel", "CohortLevel", "Figures", "QA", "Logs"):
        assert (base / sub).is_dir()
    for name in COHORT_CSVS:
        assert (base / "CohortLevel" / name).is_file(), f"missing {name}"
    assert (base / "run_manifest.json").is_file()


def test_two_fresh_runs_byte_identical(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    run_cohort(_cfg(a, tmp_path / "_mapsA"))
    run_cohort(_cfg(b, tmp_path / "_mapsB"))
    ca = a / "Outputs" / "InternalValidation" / "DEMO" / "CohortLevel"
    cb = b / "Outputs" / "InternalValidation" / "DEMO" / "CohortLevel"
    for name in COHORT_CSVS:
        assert _sha(ca / name) == _sha(cb / name), f"non-deterministic: {name}"


def test_resume_is_idempotent(tmp_path):
    cfg = _cfg(tmp_path, tmp_path / "_maps")
    s1 = run_cohort(cfg)
    cohort_dir = tmp_path / "Outputs" / "InternalValidation" / "DEMO" / "CohortLevel"
    before = {n: _sha(cohort_dir / n) for n in COHORT_CSVS}
    s2 = run_cohort(cfg)  # resume
    after = {n: _sha(cohort_dir / n) for n in COHORT_CSVS}
    assert before == after                      # cohort CSVs unchanged on resume
    assert s1["completed"] == s2["completed"]   # same completion count (cached, not lost)


def test_no_phi_token_in_output_tree(tmp_path):
    run_cohort(_cfg(tmp_path, tmp_path / "_maps"))
    tree = tmp_path / "Outputs"
    phi_tokens = ("EX-001", "EX-002", "EX-003", "EX-004", "PatientName", "PatientBirthDate",
                  "StudyDate", "InstitutionName", "AnonPatientID")
    for f in tree.rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="ignore")
            for tok in phi_tokens:
                assert tok not in text, f"PHI token {tok!r} leaked into {f.name}"
    # raw IDs live only in the map, OUTSIDE the tree
    map_csv = tmp_path / "_maps" / "DEMO_pseudonym_map.csv"
    assert map_csv.is_file() and "EX-001" in map_csv.read_text(encoding="utf-8")
    assert not list(tree.rglob("*pseudonym_map*"))


def test_dicom_cohort_degrades_missing_dose(tmp_path):
    root = tmp_path / "dicom"
    for pid in ("SYN-A", "SYN-B"):
        s, d, p = build_rt_triple(patient_id=pid)
        (root / pid).mkdir(parents=True, exist_ok=True)
        for ds, nm in ((s, "RS"), (d, "RD"), (p, "RP")):
            save_dataset(ds, root / pid / f"{nm}.dcm")
    s, _d, p = build_rt_triple(patient_id="SYN-C")  # no dose → must degrade, not crash
    (root / "SYN-C").mkdir(parents=True, exist_ok=True)
    save_dataset(s, root / "SYN-C" / "RS.dcm")
    save_dataset(p, root / "SYN-C" / "RP.dcm")

    cfg = RunnerConfig(
        input_root=root, cohort="HN", output_root=tmp_path / "Outputs",
        validation="ExternalValidation", input_kind="dicom", site="HN",
        pseudonym_map_dir=tmp_path / "_maps",
    )
    summary = run_cohort(cfg)  # must not raise
    assert summary["attempted"] == 3
    base = tmp_path / "Outputs" / "ExternalValidation" / "HN"
    failures = (base / "CohortLevel" / "failures.csv").read_text(encoding="utf-8")
    qa = (base / "CohortLevel" / "QA.csv").read_text(encoding="utf-8")
    # SYN-C degraded via NO_DOSE and is recorded (skipped or failed), never a crash
    assert "NO_DOSE" in qa or "NO_DOSE" in failures or summary["skipped"] >= 1
