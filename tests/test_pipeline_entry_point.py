"""
Regression tests for the documented pipeline entry point.

``run_analysis_pipeline`` is the entry point the documentation points a new user at, and it was
unusable in exactly the configuration that documentation describes: the default one. Two separate
defects sat on that path.

1. ``UnboundLocalError``. The BASIC-mode block applied conservative defaults and logged each one
   through ``structured_logger``, but the provenance tracker and the structured logger were both
   initialised *after* that block. BASIC is the default mode, so the very first call raised.

2. ``AttributeError``. The loop that copies applicability warnings onto the output dereferenced
   ``applicability_result`` unconditionally. That object is only built when
   ``inputs.treatment_info`` is supplied -- not the default -- and the loop had additionally been
   indented into the ``if provenance_tracker:`` block above it, so it ran whenever provenance was
   enabled, which is also the default.

Both were reachable by calling the function the way the docs describe, with no arguments beyond
the required inputs. These tests pin that call down.

Note on types: ``PipelineInput`` annotates its directories as ``Path`` and the pipeline uses the
``/`` operator on them, so these tests pass ``Path`` objects, matching the only production caller
(``rbgyanx_gui.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rbgyanx.logic.pipeline import PipelineInput, run_analysis_pipeline

pytestmark = pytest.mark.unit


@pytest.fixture()
def inputs(tmp_path: Path) -> PipelineInput:
    """Minimal valid input: two real directories and nothing else."""
    dvh = tmp_path / "dvh"
    out = tmp_path / "out"
    dvh.mkdir()
    out.mkdir()
    return PipelineInput(dvh_directory=dvh, output_directory=out)


def test_runs_with_default_arguments(inputs: PipelineInput) -> None:
    """The documented call -- inputs only, every other argument defaulted -- must not raise.

    This is the regression guard for the ``UnboundLocalError``. It asserts the call returns a
    result object rather than asserting a particular status: with the legacy ``code1``-``code7``
    scripts quarantined in ``legacy/``, the subprocess steps report themselves as missing and the
    run degrades to ``partial``. Degrading is allowed; raising is not.
    """
    output = run_analysis_pipeline(inputs)

    assert output is not None
    assert output.status in {"success", "partial", "failed"}
    # BASIC is the default mode and must announce itself.
    assert any("BASIC" in line for line in output.logs)


def test_basic_mode_applies_conservative_defaults(inputs: PipelineInput) -> None:
    """The BASIC block must actually run -- not merely fail to crash.

    The bug lived inside the loop that applies conservative defaults, so a fix that skipped the
    block would also stop the exception. Assert the side effect is present.
    """
    assert inputs.config is None  # nothing supplied by the caller

    run_analysis_pipeline(inputs)

    assert inputs.config, "BASIC mode should have populated inputs.config with its defaults"


def test_runs_with_provenance_and_logging_disabled(inputs: PipelineInput) -> None:
    """The non-default combination must work too.

    Turning both subsystems off makes ``structured_logger`` and ``provenance_tracker`` ``None``
    rather than unset, which is the case every ``if structured_logger:`` guard was written for.
    """
    output = run_analysis_pipeline(
        inputs, enable_provenance=False, enable_structured_logging=False
    )

    assert output is not None
    assert any("BASIC" in line for line in output.logs)


def test_applicability_warnings_do_not_require_provenance(tmp_path: Path) -> None:
    """Applicability warnings must survive provenance being switched off.

    The warning loop had been indented inside ``if provenance_tracker:``. Disabling provenance
    therefore silently discarded user-facing applicability warnings -- the opposite of what a
    governance feature should do. Supplying ``treatment_info`` builds a real result object, so
    this exercises the de-indented, guarded loop.
    """
    dvh = tmp_path / "dvh"
    out = tmp_path / "out"
    dvh.mkdir()
    out.mkdir()
    inputs = PipelineInput(
        dvh_directory=dvh,
        output_directory=out,
        treatment_info={"dose_per_fraction": 2.0, "n_fractions": 35},
    )

    output = run_analysis_pipeline(inputs, enable_provenance=False)

    assert output is not None
    assert output.applicability_result is not None
