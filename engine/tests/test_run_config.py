"""Engine API smoke tests."""

from pathlib import Path

from rbgyanx_engine import RunConfig, __version__, run_analysis


def test_version_is_alpha():
    assert "0.1" in __version__


def test_run_analysis_missing_input(tmp_path):
    cfg = RunConfig(
        endpoint="tcp",
        input_kind="dicom",
        input_dir=tmp_path / "empty",
        output_dir=tmp_path / "out",
        enable_ml=False,
    )
    (tmp_path / "empty").mkdir()
    result = run_analysis(cfg)
    assert result.exit_code == 1
