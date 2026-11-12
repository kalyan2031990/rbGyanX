"""The prescription table must reach the path a cohort run actually takes (defect #60).

The first fix for #60 wired the override into `cohort_features.build_patient_features`. Nothing on
the cohort path calls that: `cohort_runner` goes `run_analysis` -> `engine.py` ->
`pipeline.collect_dicom_tcp`. So the capability existed, had tests, and was unreachable from the
entry point it was built for -- which is worse than not having it, because the run manifest would
have recorded a table as "in force" while every prescription still came from the RT Plan.

These tests assert the wiring end to end, by signature and by behaviour, so the two halves cannot
drift apart again.
"""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

import pytest

from dicom_io.prescription_table import load_prescription_table
from rbgyanx_engine import pipeline
from rbgyanx_engine.cohort_runner import RunnerConfig
from rbgyanx_engine.run_config import RunConfig

HEADER = "patient,target_roi,prescription_gy,n_fractions\n"


@pytest.fixture
def table(tmp_path):
    p = tmp_path / "rx.csv"
    p.write_text(HEADER + "PT-1,PTVHigh,60,35\n", encoding="utf-8")
    return load_prescription_table(p)


# --------------------------------------------------------------------------- the wiring


def test_run_config_carries_a_prescription_table():
    assert any(f.name == "prescription_table" for f in fields(RunConfig))
    assert RunConfig.__dataclass_fields__["prescription_table"].default is None


def test_runner_config_carries_a_prescription_table():
    assert any(f.name == "prescription_table" for f in fields(RunnerConfig))


def test_collect_dicom_tcp_accepts_one():
    """The DICOM seam: this is where an RT Plan becomes plan metadata."""
    sig = inspect.signature(pipeline.collect_dicom_tcp)
    assert "prescription_table" in sig.parameters
    assert sig.parameters["prescription_table"].default is None


def test_the_engine_passes_it_to_the_dicom_seam():
    """#60: the gap that made the first fix unreachable was exactly this call."""
    src = inspect.getsource(
        __import__("rbgyanx_engine.engine", fromlist=["x"])
    )
    assert "collect_dicom_tcp(" in src
    call = src.split("collect_dicom_tcp(", 1)[1][:400]
    assert "prescription_table=" in call, (
        "engine.py calls collect_dicom_tcp without passing the prescription table; the override "
        "would never reach a cohort run (defect #60)"
    )


def test_the_cohort_runner_passes_it_to_the_engine():
    src = inspect.getsource(__import__("rbgyanx_engine.cohort_runner", fromlist=["x"]))
    assert "prescription_table=cfg.prescription_table" in src, (
        "cohort_runner builds a RunConfig without the prescription table"
    )


# --------------------------------------------------------------------------- behaviour


def test_the_loader_is_cached_per_path(tmp_path):
    """A cohort run asks once per patient; re-reading and re-validating each time is waste."""
    from dicom_io.prescription_table import clear_prescription_table_cache
    from rbgyanx_engine import engine

    p = tmp_path / "rx.csv"
    p.write_text(HEADER + "PT-1,PTVHigh,60,35\n", encoding="utf-8")
    cfg = RunConfig(prescription_table=p)
    clear_prescription_table_cache()  # #64: the cache is shared now, so the manifest and the lookup see one object
    first = engine._prescription_table(cfg)
    second = engine._prescription_table(cfg)
    assert first is second, "the table was re-loaded rather than cached"
    assert len(first) == 1


def test_no_table_means_no_table():
    from rbgyanx_engine import engine

    assert engine._prescription_table(RunConfig()) is None


def test_a_bad_table_fails_at_load_not_mid_cohort(tmp_path):
    """The failure must happen before any patient is read, not after forty of them."""
    from dicom_io.prescription_table import PrescriptionTableError, clear_prescription_table_cache
    from rbgyanx_engine import engine

    p = tmp_path / "bad.csv"
    p.write_text(HEADER + "PT-1,PTVHigh,900,35\n", encoding="utf-8")   # 900 Gy
    clear_prescription_table_cache()  # #64: the cache is shared now, so the manifest and the lookup see one object
    with pytest.raises(PrescriptionTableError):
        engine._prescription_table(RunConfig(prescription_table=p))


def test_the_override_changes_the_metadata_tcp_reads(table):
    """End of the chain: TCP's EQD2 comes from these two fields."""
    from dicom_io.prescription_table import apply_to_plan_metadata

    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35}
    out = apply_to_plan_metadata(meta, "PT-1", table)
    assert out["prescription_dose_gy"] == 60.0
    assert out["dose_per_fraction_gy"] == pytest.approx(60.0 / 35)
    assert out["prescription_dose_gy_from_rtplan"] == 70.0


def test_what_the_prescription_actually_reaches():
    """The prescription moves EQD2_gy and BED_gy. It does NOT move any TCP value.

    Recorded as a test because I got this wrong while writing #60 up: I reported that TCP's EQD2
    is computed from the prescription "so this changed numbers without changing any dose", and
    inferred that TCP therefore moves. Measured on a real patient, substituting 70 Gy with 60 Gy
    gave EQD2_gy 70.0 -> 58.57 and BED_gy 84.0 -> 70.29 with **every TCP value identical**.

    The reason is in `radiobiology/tcp_calculator.py`: `eqd2_gy` and `bed_gy` are computed from
    the prescription and reported as columns, but all four TCP models -- Poisson, Z-M, gEUD and
    Logistic -- are computed from the target's DVH. If a model ever starts consuming `eqd2_gy`,
    this test is where that should be noticed, because it changes what a wrong prescription costs.
    """
    src = (Path(pipeline.__file__).parent.parent / "radiobiology" / "tcp_calculator.py").read_text(
        encoding="utf-8"
    )
    # The models read the DVH frame, not the EQD2 scalar.
    assert "dvh_df = dvh_object_to_dataframe(" in src
    body = src.split('"EQD2_gy": eqd2_gy', 1)[1]
    for model in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic"):
        assigned = [ln for ln in body.splitlines() if f'result["{model}"] =' in ln]
        assert assigned, f"{model} is no longer assigned where expected"
        assert not any("eqd2" in ln.lower() for ln in assigned), (
            f"{model} now reads eqd2 -- a wrong prescription would move TCP, which it does not "
            "today. Update the #60 documentation before relaxing this."
        )


def test_ntcp_does_not_depend_on_the_prescription():
    """Stated as a test because it is the reason the override sits only on the TCP seam.

    `radiobiology/bdvh.py` computes an OAR's EQD2 from that OAR's own dose divided by the fraction
    count. If that ever changes, the override has to be applied in `collect_dicom_ntcp` too, and
    this test is where that should be noticed.
    """
    src = Path(pipeline.__file__).parent.parent / "radiobiology" / "bdvh.py"
    text = src.read_text(encoding="utf-8")
    assert "dpf = physical_dose / n_fractions" in text, (
        "bdvh no longer derives dose-per-fraction from the organ's own dose; if it now uses the "
        "plan prescription, the #60 override must also be applied on the NTCP path"
    )
