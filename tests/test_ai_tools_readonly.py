"""
Read-only tool layer tests (governed AI assistant, phase 4).

Two things are proved here. First, that the registry refuses *before* a tool runs, for every
disallowed combination in the matrix - a tool that is refused must not have executed. Second,
that each tool enforces the part the matrix cannot express: path containment, pytest selector
validation, and the synthetic-data-only rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rbgyanx.ai.capability import Capability, InstallType
from rbgyanx.ai.config import PROVIDERS
from rbgyanx.ai.scrubber import install_root
from rbgyanx.ai.tools import REGISTRY, ToolContext, invoke
from rbgyanx.ai.tools.paths import PathRefused, resolve_within
from rbgyanx.ai.tools.readonly import _validate_selector

REMOTE = PROVIDERS["claude"]
LOCAL = PROVIDERS["local"]
NO_ENV: dict[str, str] = {}

SOURCE_LOCAL = ToolContext(LOCAL, InstallType.SOURCE, env=NO_ENV)
SOURCE_REMOTE = ToolContext(REMOTE, InstallType.SOURCE, env=NO_ENV)
FROZEN_LOCAL = ToolContext(LOCAL, InstallType.FROZEN, env=NO_ENV)
FROZEN_REMOTE = ToolContext(REMOTE, InstallType.FROZEN, env=NO_ENV)
CI_LOCAL = ToolContext(LOCAL, InstallType.CI, env=NO_ENV)


# --------------------------------------------------------------------------- the registry


#: Sample arguments for every registered tool. Kept in one place and asserted complete below,
#: so adding a tool fails with one clear message rather than a KeyError deep in another test.
SAMPLE_KWARGS: dict[str, dict] = {
    "read_code": {"path": "README.md"},
    "read_error": {"traceback": "boom"},
    "run_tests": {"selector": "tests"},
    "run_synthetic": {"input_path": "examples/data"},
    "explain_run": {"result": None},
    "edit_code": {"path": "README.md", "new_text": "x"},
    "literature_compare": {"organ": "Parotid", "observed": {"Dmean": 26.4}},
}


def test_every_registered_tool_has_sample_arguments():
    """Adding a tool without covering it here is itself a failure, not a silent gap."""
    assert set(REGISTRY.names()) == set(SAMPLE_KWARGS), (
        "a tool was added or removed without updating SAMPLE_KWARGS; "
        f"registry={sorted(REGISTRY.names())} sample={sorted(SAMPLE_KWARGS)}"
    )


def test_every_tool_is_registered():
    """The full inventory, written out so a new tool is a deliberate change to this list."""
    assert REGISTRY.names() == [
        "edit_code",
        "explain_run",
        "literature_compare",
        "read_code",
        "read_error",
        "run_synthetic",
        "run_tests",
    ]


def test_an_unknown_tool_is_refused_not_raised():
    result = invoke("definitely_not_a_tool", SOURCE_LOCAL)
    assert result.ok is False
    assert "no such tool" in result.reason


def test_each_tool_declares_its_capability():
    assert REGISTRY.get("read_code").capability is Capability.READ_CODE
    assert REGISTRY.get("read_error").capability is Capability.READ_ERROR
    assert REGISTRY.get("run_tests").capability is Capability.RUN_TESTS
    assert REGISTRY.get("run_synthetic").capability is Capability.RUN_SYNTHETIC
    assert REGISTRY.get("explain_run").capability is Capability.EXPLAIN_AGGREGATE


def test_available_lists_only_permitted_tools():
    assert REGISTRY.available(CI_LOCAL) == []
    frozen = REGISTRY.available(FROZEN_LOCAL)
    assert "read_code" not in frozen and "run_tests" not in frozen
    assert "explain_run" in frozen and "read_error" in frozen
    assert set(REGISTRY.available(SOURCE_LOCAL)) == set(REGISTRY.names())


def test_registry_refuses_before_the_tool_runs():
    """The gate must be structural: a refused tool never executes at all."""
    from rbgyanx.ai.tools.registry import Tool, ToolRegistry, ToolResult

    ran: list[bool] = []

    def _spy(ctx, **kwargs):
        ran.append(True)
        return ToolResult(ok=True, tool="spy", capability=Capability.READ_CODE.value)

    registry = ToolRegistry()
    registry.register(Tool(name="spy", capability=Capability.READ_CODE, func=_spy))

    refused = registry.invoke("spy", FROZEN_LOCAL)
    assert refused.ok is False
    assert ran == [], "the tool body ran despite being refused"

    permitted = registry.invoke("spy", SOURCE_LOCAL)
    assert permitted.ok is True
    assert ran == [True], "the tool body did not run when it was permitted"


# ------------------------------------------------------- refusal under each combination


@pytest.mark.parametrize("ctx", [FROZEN_LOCAL, FROZEN_REMOTE, CI_LOCAL])
def test_read_code_refused_where_the_matrix_says_no(ctx):
    result = invoke("read_code", ctx, path="README.md")
    assert result.ok is False
    assert result.reason


@pytest.mark.parametrize("ctx", [FROZEN_LOCAL, FROZEN_REMOTE, CI_LOCAL])
def test_run_tests_refused_where_the_matrix_says_no(ctx):
    result = invoke("run_tests", ctx, selector="tests/test_utils.py")
    assert result.ok is False


@pytest.mark.parametrize("ctx", [FROZEN_LOCAL, FROZEN_REMOTE, CI_LOCAL])
def test_run_synthetic_refused_where_the_matrix_says_no(ctx):
    result = invoke("run_synthetic", ctx, input_path="examples/data")
    assert result.ok is False


def test_refusal_reason_names_the_failed_condition():
    result = invoke("read_code", FROZEN_LOCAL, path="README.md")
    assert "SOURCE" in result.reason and "FROZEN" in result.reason


def test_ci_refuses_every_tool():
    for name in REGISTRY.names():
        result = invoke(name, CI_LOCAL, **SAMPLE_KWARGS[name])
        assert result.ok is False, f"{name} ran in CI"
        assert "CI" in result.reason


# ---------------------------------------------------------------------------- read_code


def test_read_code_reads_a_file_in_the_tree():
    result = invoke("read_code", SOURCE_LOCAL, path="rbgyanx/ai/capability.py")
    assert result.ok is True
    assert "class Capability" in result.output
    assert result.metadata["path"] == "rbgyanx/ai/capability.py"


@pytest.mark.parametrize(
    "path",
    [
        "../secrets.txt",
        "../../etc/passwd",
        "/etc/passwd",
        r"C:\Windows\win.ini",
        r"\\server\share\file.py",
        "C:relative.py",
        "rbgyanx/../../outside.py",
    ],
)
def test_read_code_refuses_paths_outside_the_tree(path):
    result = invoke("read_code", SOURCE_LOCAL, path=path)
    assert result.ok is False
    assert "refusing" in result.reason


def test_read_code_refuses_an_alternate_data_stream():
    result = invoke("read_code", SOURCE_LOCAL, path="README.md:hidden")
    assert result.ok is False
    assert "alternate data stream" in result.reason


@pytest.mark.parametrize("name", [".env", "id_rsa", "server.pem", "key.p12"])
def test_read_code_refuses_credential_files(tmp_path, name):
    with pytest.raises(PathRefused):
        resolve_within(install_root(), name, must_exist=False)


@pytest.mark.parametrize("directory", ["test_data", ".git", "Outputs", "external_validation"])
def test_read_code_refuses_data_and_vcs_directories(directory):
    with pytest.raises(PathRefused):
        resolve_within(install_root(), f"{directory}/anything.py", must_exist=False)


def test_read_code_refuses_a_missing_file():
    result = invoke("read_code", SOURCE_LOCAL, path="rbgyanx/ai/not_a_real_file.py")
    assert result.ok is False
    assert "no such file" in result.reason


def test_read_code_refuses_an_oversized_file(monkeypatch):
    import rbgyanx.ai.tools.readonly as ro

    monkeypatch.setattr(ro, "MAX_READ_BYTES", 10)
    result = invoke("read_code", SOURCE_LOCAL, path="rbgyanx/ai/capability.py")
    assert result.ok is False
    assert "exceeds" in result.reason


# --------------------------------------------------------------------------- read_error

PATIENT_TB = (
    "Traceback (most recent call last):\n"
    '  File "C:\\Data\\PAROTID\\Smith_John_1234567\\load.py", line 12, in <module>\n'
    "ValueError: bad\n"
)


def test_read_error_is_raw_for_a_local_provider():
    result = invoke("read_error", SOURCE_LOCAL, traceback=PATIENT_TB)
    assert result.ok is True
    assert result.output == PATIENT_TB
    assert result.metadata["scrubbed"] is False


def test_read_error_is_scrubbed_for_a_remote_provider():
    result = invoke("read_error", SOURCE_REMOTE, traceback=PATIENT_TB)
    assert result.ok is True
    assert "Smith" not in result.output
    assert "1234567" not in result.output
    assert result.metadata["scrubbed"] is True
    assert result.findings_redacted >= 1


def test_read_error_refuses_when_it_cannot_clean_confidently():
    result = invoke("read_error", SOURCE_REMOTE, traceback="failure in Parotid_L_Smith\n")
    assert result.ok is False
    assert "refusing to transmit" in result.reason


# ---------------------------------------------------------------------------- run_tests


@pytest.mark.parametrize(
    "selector",
    [
        "-p",
        "--pdb",
        "-c=evil.ini",
        "--rootdir=/tmp",
        "tests; rm -rf /",
        "tests && echo pwned",
        "tests | cat",
        "$(whoami)",
        "`whoami`",
        "../outside/test_x.py",
        "",
    ],
)
def test_run_tests_refuses_option_and_shell_injection(selector):
    """A selector reaches a subprocess argv, where -p and -c both change what code runs."""
    result = invoke("run_tests", SOURCE_LOCAL, selector=selector)
    assert result.ok is False
    assert "refusing" in result.reason or "empty" in result.reason


@pytest.mark.parametrize(
    "selector",
    [
        "tests",
        "tests/test_utils.py",
        "tests/test_utils.py::test_something",
        "tests/synthetic/test_property_invariants.py::test_x[param-1]",
    ],
)
def test_valid_selectors_are_accepted_by_the_validator(selector):
    assert _validate_selector(selector) == selector


def test_run_tests_refuses_a_nonexistent_path():
    result = invoke("run_tests", SOURCE_LOCAL, selector="tests/not_a_real_test.py")
    assert result.ok is False
    assert "no such test path" in result.reason


def test_run_tests_actually_runs_a_tiny_selection():
    """One real subprocess run, kept small so the suite stays fast."""
    result = invoke(
        "run_tests", SOURCE_LOCAL, selector="tests/test_ai_capability.py::test_column_mapping"
    )
    assert result.ok is True
    assert result.metadata["returncode"] == 0


# ------------------------------------------------------------------------ run_synthetic


def test_run_synthetic_accepts_the_shipped_demo_data():
    result = invoke(
        "run_synthetic", SOURCE_LOCAL, input_path=str(install_root() / "examples" / "data")
    )
    assert result.ok is True


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Data\PAROTID",
        "/data/patients",
        "test_data/dicom_input",
        "rbgyanx",
    ],
)
def test_run_synthetic_refuses_undeclared_directories(path):
    """An allow-list, not a deny-list: undeclared is refused whether or not it holds real data."""
    result = invoke("run_synthetic", SOURCE_LOCAL, input_path=path)
    assert result.ok is False
    assert "declared synthetic" in result.reason


def test_run_synthetic_accepts_a_user_declared_synthetic_directory(tmp_path):
    (tmp_path / "case.txt").write_text("synthetic", encoding="utf-8")
    ctx = ToolContext(LOCAL, InstallType.SOURCE, env=NO_ENV, synthetic_roots=(tmp_path,))
    result = invoke("run_synthetic", ctx, input_path=str(tmp_path))
    assert result.ok is True


def test_run_synthetic_refuses_real_data_even_for_a_local_provider(tmp_path):
    """'Never touches real patient data regardless of provider' - including the local one."""
    real = tmp_path / "real_cohort"
    real.mkdir()
    for ctx in (SOURCE_LOCAL, SOURCE_REMOTE):
        result = invoke("run_synthetic", ctx, input_path=str(real))
        assert result.ok is False


# -------------------------------------------------------------------------- explain_run


class _Structure:
    def __init__(self, label, mean_dose_gy, ntcp):
        self.label = label
        self.mean_dose_gy = mean_dose_gy
        self.ntcp = ntcp


class _Result:
    n_files = 2
    structures = [
        _Structure("Parotid_L", 26.4, {"LKB": 0.21}),
        _Structure("Parotid_R", 24.1, {"LKB": 0.18}),
    ]


def test_explain_run_returns_an_aggregate_summary():
    result = invoke("explain_run", SOURCE_LOCAL, result=_Result())
    assert result.ok is True
    assert "structures analysed" in result.output
    assert result.metadata["patient_level"] is False


def test_patient_level_is_granted_locally():
    result = invoke("explain_run", SOURCE_LOCAL, result=_Result(), include_patient_level=True)
    assert result.ok is True
    assert result.metadata["patient_level"] is True
    assert "Parotid_L" in result.output


def test_patient_level_is_withheld_on_a_remote_provider_and_says_so():
    """Not silently reduced: the caller is told the detail was withheld, and why."""
    result = invoke("explain_run", SOURCE_REMOTE, result=_Result(), include_patient_level=True)
    assert result.ok is True
    assert result.metadata["patient_level"] is False
    assert result.metadata["patient_level_requested"] is True
    assert "withheld" in result.reason
    assert "local" in result.reason


def test_explain_run_never_reaches_the_numeric_core():
    """Hard constraint: the assistant explains values, it never produces them."""
    source = (Path(install_root()) / "rbgyanx" / "ai" / "tools" / "readonly.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("radiobiology", "ntcp_models", "tcp_models", "lkb", "compute_ntcp"):
        assert forbidden not in source.lower(), f"tool layer must not import {forbidden}"
