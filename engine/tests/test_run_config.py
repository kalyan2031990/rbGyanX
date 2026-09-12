"""Engine API smoke tests."""


from rbgyanx_engine import RunConfig, __version__, run_analysis


def test_version_matches_release():
    assert __version__ == "1.3.0"


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
