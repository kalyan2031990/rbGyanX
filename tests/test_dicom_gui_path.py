"""Three defects found by driving the Qt app over a synthetic DICOM-RT study.

All three sat in the GUI/service layer while the engine beneath was correct, which is why they
survived: the engine's own CSVs carried the right numbers throughout.

  1. the folder check refused a cohort root the engine handles (patient-per-subfolder);
  2. the Cohort flow view raised on a DICOM result, because its opening stage counted files
     while the next counted structures, and one RTSTRUCT carries many structures;
  3. the results adapter read ``volume_cc``, a key no engine row has, so every DICOM row showed
     the volume as NaN.

These use hand-built rows rather than a real study: the defects are in the adaptation and the
presentation, so they reproduce without DICOM on disk, and the suite stays fast and data-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rbgyanx.services.run_controller import RunController, RunResult, StructureResult
from rbgyanx.services.run_request import RunRequest, validate_run_request

# --------------------------------------------------------------------- 1. the folder check


def _write_study(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("CT_000.dcm", "RTSTRUCT.dcm", "RTPLAN.dcm", "RTDOSE.dcm"):
        (folder / name).write_bytes(b"")


def _errors(path: Path, tmp_path: Path) -> list[str]:
    return validate_run_request(
        RunRequest(analysis_mode="NTCP", input_path=path, output_dir=tmp_path, input_source="dicom")
    ).errors


def test_a_flat_folder_of_dcm_files_is_accepted(tmp_path: Path) -> None:
    study = tmp_path / "flat"
    _write_study(study)
    assert _errors(study, tmp_path) == []


def test_a_cohort_root_of_patient_folders_is_accepted(tmp_path: Path) -> None:
    """The layout make_synthetic_dicom_cohort.py writes, and the docs tell operators to browse."""
    root = tmp_path / "dicom_input"
    _write_study(root / "SYNTH001")
    _write_study(root / "SYNTH002")
    assert _errors(root, tmp_path) == []


def test_a_folder_with_no_dicom_anywhere_is_still_refused(tmp_path: Path) -> None:
    empty = tmp_path / "notes"
    (empty / "sub").mkdir(parents=True)
    (empty / "readme.txt").write_text("no dicom here", encoding="utf-8")
    assert any("does not look like DICOM RT" in e for e in _errors(empty, tmp_path))


def test_the_check_does_not_walk_below_one_level(tmp_path: Path) -> None:
    """Depth is bounded on purpose: a wrongly chosen folder must not cost a recursive walk."""
    deep = tmp_path / "deep"
    _write_study(deep / "a" / "b")
    assert any("does not look like DICOM RT" in e for e in _errors(deep, tmp_path))


# --------------------------------------------------------------------- 2. the cohort-flow view


def _result(n_files: int, n_structures: int) -> RunResult:
    structures = [
        StructureResult(
            label=f"OAR_{i}",
            patient_id="SYNTH001",
            dose_gy=[70.0, 0.0],
            volume_pct=[100.0, 0.0],
            mean_dose_gy=20.0,
        )
        for i in range(n_structures)
    ]
    return RunResult(ok=True, structures=structures, n_files=n_files)


@pytest.mark.parametrize(
    "n_files, n_structures",
    [(1, 4), (2, 6), (16, 16), (0, 3)],
    ids=["one-patient-dicom", "two-patient-dicom", "dvh-text", "no-file-count"],
)
def test_cohort_flow_never_grows(n_files: int, n_structures: int) -> None:
    """A flow diagram must be monotone non-increasing; DICOM used to open it on a file count."""
    pytest.importorskip("PySide6")
    from rbgyanx.qtapp.screens.visualisation import VisualisationScreen

    # build_spec reads only ``self._result`` on this branch, so it runs unbound against a stand-in
    # and the test needs no QApplication.
    screen = _Screen(_result(n_files, n_structures))
    spec = VisualisationScreen.build_spec(screen, "cohort_flow")

    counts = [s.n for s in spec.stages]
    assert counts == sorted(counts, reverse=True), counts
    assert counts[-1] >= 0
    assert counts[0] >= n_structures


class _Screen:
    """The smallest stand-in ``build_spec`` needs for the cohort-flow branch."""

    def __init__(self, result: RunResult) -> None:
        self._result = result


# --------------------------------------------------------------------- 3. the volume key


def test_engine_rows_keep_their_volume_through_the_adapter() -> None:
    """The engine names it ``total_volume_cc``; the adapter used to ask for ``volume_cc``."""
    engine_result = _EngineResult(
        ntcp_results=[
            {
                "structure": "Parotid_L",
                "AnonPatientID": "SYNTH001",
                "Dmean_gy": 19.1,
                "total_volume_cc": 16.896,
                "NTCP_RS": 0.385,
            }
        ],
        tcp_results=[
            {
                "raw_name": "PTV",
                "AnonPatientID": "SYNTH001",
                "Dmean_gy": 51.0,
                "total_volume_cc": 120.5,
                "TCP_Poisson": 0.9995,
            }
        ],
    )
    adapted = RunController._adapt_engine_result(engine_result)
    volumes = {s.label: s.volume_cc for s in adapted.structures}
    assert volumes["Parotid_L"] == pytest.approx(16.896)
    assert volumes["PTV"] == pytest.approx(120.5)


class _EngineResult:
    def __init__(self, ntcp_results: list[dict], tcp_results: list[dict]) -> None:
        self.ntcp_results = ntcp_results
        self.tcp_results = tcp_results
