"""Declared provenance columns must carry values, and rows must identify their ROI.

Defect #17 is one architectural failure with several symptoms: the engine computes provenance and
then discards it.

  * ``dvh_mode``   -- computed per ROI by the extractor, aggregated correctly by
                      ``patient_registry``, filed there under ``"DVH_Mode"``, and read downstream
                      as ``"extraction_mode"``. A three-way name mismatch, so the column shipped
                      empty on every run at every version.
  * ``site`` / ``site_confidence`` -- detected correctly and attached to every row
                      (``pipeline._attach_site_metadata``), but ``patient_features.csv`` wrote
                      ``cfg.site``, which is empty unless ``--site`` was passed. A correctly
                      detected HN at HIGH confidence shipped as an empty cell.
  * ``dose_selected`` -- did not exist. The RTDOSE is the sole origin of every DVH, Dmean, gEUD,
                      TCP and NTCP value, and the output recorded only the PLAN.
  * ``volume_cc``  -- declared by two CSVs, filled from ``total_volume_cc``, which the DICOM
                      target path never set.
  * ``selection_notes`` / ``ct_instance_count`` -- written in ``cohort_discovery`` and read
                      nowhere.
  * ``input_root`` -- never written to ``run_manifest.json``, so a finished run did not record
                      where its data came from.

Defect #19's identity half is here too: NTCP rows carried no ``raw_name`` and no ``roi_number``,
so an organ and its own PRV expansion arrived as two rows with the same ``structure`` label and
nothing to tell them apart. Measured on TCIA2: ``BrainStem``/``BrainStem_03`` and
``SpinalCord``/``SpinalCord_05`` collide in 121/121 patients, with a 7-fold NTCP difference.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------ the columns are declared

def test_patient_features_declares_the_provenance_columns():
    from rbgyanx_engine.cohort_runner import COHORT_CSVS

    cols = COHORT_CSVS["patient_features.csv"]
    for c in ("site", "site_confidence", "dvh_mode", "plan_selected", "dose_selected",
              "struct_selected", "ct_instance_count", "selection_notes"):
        assert c in cols, f"{c} missing from patient_features.csv"


def test_dose_selected_exists_on_the_record():
    """It is the origin of every number; it must be a field, not a comment."""
    import dataclasses

    from rbgyanx_engine.cohort_runner import PatientRecord

    names = {f.name for f in dataclasses.fields(PatientRecord)}
    for f in ("dose_selected", "struct_selected", "selection_notes", "ct_instance_count",
              "site_detected", "site_confidence"):
        assert f in names, f"PatientRecord.{f} missing"


# ------------------------------------------------------------------ the rows carry what fills them

def _dicom_row_assignments(func_name: str) -> str:
    """The source of one pipeline collector, so we can assert on what it attaches."""
    import inspect

    from rbgyanx_engine import pipeline

    return inspect.getsource(getattr(pipeline, func_name))


@pytest.mark.parametrize("key", ["raw_name", "roi_number", "extraction_mode", "total_volume_cc"])
def test_dicom_ntcp_rows_carry_roi_identity_and_mode(key):
    """Reverting any of these makes the corresponding output column empty again."""
    src = "".join(_dicom_row_assignments(n) for n in dir(__import__(
        "rbgyanx_engine.pipeline", fromlist=["x"])) if n.startswith("_collect") or "ntcp" in n)
    assert f'row["{key}"]' in src, f"no NTCP row sets {key}"


def test_dvh_result_actually_exposes_extraction_mode():
    """The value the mapping relies on must exist on the object the row is built from."""
    import dataclasses

    from dicom_io.dvh_extractor import DVHResult

    names = {f.name for f in dataclasses.fields(DVHResult)}
    assert "extraction_mode" in names
    assert "raw_name" in names and "roi_number" in names and "total_volume_cc" in names


def test_registry_and_reader_agree_on_the_dvh_mode_key():
    """The three-way name mismatch: the reader's key must be one a row can actually have."""
    import inspect

    from rbgyanx_engine import cohort_runner

    src = inspect.getsource(cohort_runner)
    assert 'r.get("extraction_mode"' in src, "the reader key changed"
    # and the pipeline must set that exact key
    from rbgyanx_engine import pipeline

    assert 'row["extraction_mode"]' in inspect.getsource(pipeline), (
        "nothing sets extraction_mode, so the reader will keep finding nothing"
    )


# ------------------------------------------------------------------ the manifest records its input

def test_run_manifest_records_the_input_root():
    import inspect

    from rbgyanx_engine import cohort_runner

    src = inspect.getsource(cohort_runner)
    assert '"input_root"' in src, (
        "run_manifest.json must record the tree the run read, or the run cannot be reproduced "
        "from its own output"
    )
