"""
Write-tool and freeze-boundary tests (governed AI assistant, phase 5).

The two properties that matter here:

  * Every frozen path is refused, including when reached by traversal, and including the files
    that would let the agent re-open the boundary without touching a frozen file at all.
  * A test-breaking edit is reverted automatically, and the tree afterwards is byte-identical to
    what it was before. That is asserted against a real pytest subprocess, not a stub, because a
    verification loop that has only ever been tested against a fake verifier has not been tested.
"""

from __future__ import annotations

import hashlib

import pytest
from rbgyanx.ai.capability import (
    InstallType,
    creation_reason,
    frozen_reason,
    is_frozen,
)
from rbgyanx.ai.config import PROVIDERS
from rbgyanx.ai.tools import ToolContext
from rbgyanx.ai.tools import edit as edit_mod
from rbgyanx.ai.tools.edit import Snapshot, edit_code

LOCAL = PROVIDERS["local"]
REMOTE = PROVIDERS["claude"]
NO_ENV: dict[str, str] = {}

SOURCE_LOCAL = ToolContext(LOCAL, InstallType.SOURCE, env=NO_ENV)
FROZEN_LOCAL = ToolContext(LOCAL, InstallType.FROZEN, env=NO_ENV)
CI_LOCAL = ToolContext(LOCAL, InstallType.CI, env=NO_ENV)


# ------------------------------------------------------------------- the frozen set


@pytest.mark.parametrize(
    "path",
    [
        # what produces the numbers
        "engine/radiobiology/ntcp_models.py",
        "engine/radiobiology/deep/nested/file.py",
        "engine/uncertainty/propagate.py",
        "engine/validation/validation_metrics.py",
        "engine/statistical_models/epv_guard.py",
        "engine/config/site_ntcp_params.py",
        "baseline_numerics.json",
        # what verifies the numbers
        "tests/test_ntcp_positive_controls.py",
        "tests/synthetic/test_semantic_layer.py",
        "pyproject.toml",
        "conftest.py",
        "tests/conftest.py",
        "engine/tests/conftest.py",
        ".github/workflows/ci.yml",
        # what constrains the agent
        "rbgyanx/ai/capability.py",
        "rbgyanx/ai/scrubber.py",
        "rbgyanx/ai/audit.py",
        "rbgyanx/ai/config.py",
        "rbgyanx/ai/tools/registry.py",
        "rbgyanx/ai/tools/paths.py",
        "ask_rbgyanx/scope_guard.py",
        "rbgyanx/logic/mode_controller.py",
        "scripts/pre_publish_check.py",
    ],
)
def test_frozen_paths_are_refused(path):
    assert is_frozen(path) is True
    result = edit_code(SOURCE_LOCAL, path=path, new_text="# tampered\n")
    assert result.ok is False
    assert "frozen" in result.reason.lower()


@pytest.mark.parametrize(
    "path",
    [
        "rbgyanx/services/dvh_service.py",
        "rbgyanx/qtapp/screens/ai_panel.py",
        "docs/KNOWN_LIMITATIONS.md",
        "README.md",
    ],
)
def test_ordinary_source_is_not_frozen(path):
    assert is_frozen(path) is False


def test_the_numeric_core_and_its_inputs_are_both_frozen():
    """Editing a TD50 changes a complication probability as surely as editing the model."""
    assert is_frozen("engine/radiobiology/ntcp_models.py") is True
    assert is_frozen("engine/config/site_ntcp_params.py") is True


def test_tests_and_their_configuration_are_both_frozen():
    """Freezing tests while leaving addopts writable would leave the identical hole open."""
    assert is_frozen("tests/test_publication_suite.py") is True
    assert is_frozen("pyproject.toml") is True
    assert is_frozen("tests/conftest.py") is True


def test_windows_separators_do_not_evade_the_frozen_set():
    assert is_frozen(r"engine\radiobiology\ntcp_models.py") is True
    assert is_frozen(r"tests\test_ntcp_positive_controls.py") is True


def test_traversal_into_a_frozen_path_is_refused():
    """A frozen path reached the long way round is still a frozen path."""
    result = edit_code(
        SOURCE_LOCAL, path="rbgyanx/../tests/test_ntcp_positive_controls.py", new_text="x\n"
    )
    assert result.ok is False


def test_frozen_reason_names_the_file_or_its_prefix():
    assert "engine/radiobiology/" in frozen_reason("engine/radiobiology/x.py")
    assert "rbgyanx/ai/capability.py" in frozen_reason("rbgyanx/ai/capability.py")


# ------------------------------------------------------ creation of shadowing/hook files


@pytest.mark.parametrize(
    "path",
    [
        "sitecustomize.py",
        "usercustomize.py",
        "rbgyanx/sitecustomize.py",
        "anything.pth",
        "rbgyanx/services/conftest.py",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
    ],
)
def test_files_that_reopen_the_boundary_cannot_be_created(path):
    """Restricting edits is not enough if a new auto-loaded file re-opens everything."""
    assert creation_reason(path) is not None
    result = edit_code(SOURCE_LOCAL, path=path, new_text="# hook\n")
    assert result.ok is False


@pytest.mark.parametrize(
    "path",
    [
        "rbgyanx/ai/capability/__init__.py",
        "rbgyanx/ai/scrubber/__init__.py",
        "rbgyanx/ai/config/helper.py",
    ],
)
def test_a_package_shadowing_a_frozen_module_cannot_be_created(path):
    """rbgyanx/ai/capability/ is imported in preference to rbgyanx/ai/capability.py."""
    reason = creation_reason(path)
    assert reason is not None
    assert "shadow" in reason


def test_an_ordinary_new_file_is_allowed():
    assert creation_reason("rbgyanx/services/new_helper.py") is None


# ------------------------------------------------------------------ capability gating


def test_editing_is_refused_in_a_frozen_install():
    result = edit_code(FROZEN_LOCAL, path="README.md", new_text="x\n")
    assert result.ok is False


def test_editing_is_refused_in_ci():
    from rbgyanx.ai.tools import invoke

    result = invoke("edit_code", CI_LOCAL, path="README.md", new_text="x\n")
    assert result.ok is False
    assert "CI" in result.reason


def test_edit_code_is_registered_under_modify_code():
    from rbgyanx.ai.capability import Capability
    from rbgyanx.ai.tools import REGISTRY

    assert REGISTRY.get("edit_code").capability is Capability.MODIFY_CODE


# ---------------------------------------------------------------------- the snapshot


def test_snapshot_restores_bytes_exactly(tmp_path):
    target = tmp_path / "f.py"
    target.write_text("original\n", encoding="utf-8")
    snap = Snapshot.take(target)
    target.write_text("changed\n", encoding="utf-8")
    assert snap.restore() is True
    assert target.read_text(encoding="utf-8") == "original\n"


def test_snapshot_of_a_missing_file_removes_it_again(tmp_path):
    target = tmp_path / "new.py"
    snap = Snapshot.take(target)
    assert snap.existed is False
    target.write_text("created\n", encoding="utf-8")
    assert snap.restore() is True
    assert not target.exists()


def test_snapshot_verifies_the_restore_by_hash(tmp_path):
    target = tmp_path / "f.py"
    target.write_bytes(b"original\n")  # exact bytes: write_text would translate the newline
    snap = Snapshot.take(target)
    assert snap.sha256 == hashlib.sha256(b"original\n").hexdigest()


def test_the_revert_path_uses_no_git_command():
    """git stash is repo-global: it would capture the user's own uncommitted work."""
    from pathlib import Path

    source = Path(edit_mod.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]  # skip the module docstring, which explains why
    assert "git stash" not in body
    assert "subprocess.run([" not in body.replace(" ", "") or "git" not in body.split("_run")[0]


# ------------------------------------------------ the verification loop, end to end


@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    """A miniature tree with a real (fast) test, so the loop runs against real pytest."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "pkg").mkdir()
    # Exact bytes throughout: write_text translates the line feed to os.linesep on Windows,
    # which would make every edit below look like a whole-file line-ending change.
    (tmp_path / "pkg" / "calc.py").write_bytes(b"def value():\n    return 42\n")
    (tmp_path / "tests" / "test_calc.py").write_bytes(
        b"import sys\n"
        b"sys.path.insert(0, '.')\n"
        b"from pkg.calc import value\n"
        b"\n"
        b"def test_value():\n"
        b"    assert value() == 42\n"
    )
    monkeypatch.setattr(edit_mod, "install_root", lambda: tmp_path)
    return tmp_path


def test_a_clean_edit_is_applied_after_both_gates_pass(fake_repo):
    result = edit_code(
        SOURCE_LOCAL,
        path="pkg/calc.py",
        new_text="def value():\n    # clarified\n    return 42\n",
        confirm=True,
        controls="tests/test_calc.py",
        suite="tests",
    )
    assert result.ok is True, result.reason
    assert result.metadata["applied"] is True
    assert "clarified" in (fake_repo / "pkg" / "calc.py").read_text(encoding="utf-8")


def test_a_test_breaking_edit_is_reverted_and_the_tree_is_byte_identical(fake_repo):
    """The acceptance criterion, run against a real pytest subprocess."""
    target = fake_repo / "pkg" / "calc.py"
    before = target.read_bytes()
    digest_before = hashlib.sha256(before).hexdigest()

    result = edit_code(
        SOURCE_LOCAL,
        path="pkg/calc.py",
        new_text="def value():\n    return 99\n",  # breaks test_value
        confirm=True,
        controls="tests/test_calc.py",
        suite="tests",
    )

    assert result.ok is False
    assert result.metadata["applied"] is False
    assert result.metadata["reverted"] is True
    assert target.read_bytes() == before
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest_before


def test_a_failed_edit_reports_what_failed_and_does_not_retry(fake_repo):
    result = edit_code(
        SOURCE_LOCAL,
        path="pkg/calc.py",
        new_text="def value():\n    return 99\n",
        confirm=True,
        controls="tests/test_calc.py",
        suite="tests",
    )
    assert "reverted automatically" in result.reason
    assert "not retried" in result.reason
    assert "test_calc.py" in result.reason
    # The slower suite is not run once the controls have already failed.
    assert "full_suite" not in result.metadata["verdicts"]


def test_a_reverted_creation_leaves_no_file_behind(fake_repo):
    new_file = fake_repo / "pkg" / "extra.py"
    result = edit_code(
        SOURCE_LOCAL,
        path="pkg/extra.py",
        new_text="raise SystemExit('boom')\n",
        confirm=True,
        controls="tests/test_calc.py",
        suite="tests",
    )
    if not result.ok:
        assert not new_file.exists(), "a reverted creation must not leave the file behind"


# ------------------------------------------------------------- review before writing


def test_an_unconfirmed_edit_returns_a_diff_and_changes_nothing(fake_repo):
    target = fake_repo / "pkg" / "calc.py"
    before = target.read_bytes()

    result = edit_code(SOURCE_LOCAL, path="pkg/calc.py", new_text="def value():\n    return 7\n")

    assert result.ok is True
    assert result.metadata["applied"] is False
    assert result.output.startswith("---")
    assert "-    return 42" in result.output
    assert "+    return 7" in result.output
    assert target.read_bytes() == before, "an unconfirmed edit must not write"


def test_review_is_the_default_not_an_option(fake_repo):
    """confirm defaults to False, so a caller that forgets it cannot write silently."""
    import inspect

    assert inspect.signature(edit_code).parameters["confirm"].default is False


def test_a_no_op_edit_is_reported_rather_than_applied(fake_repo):
    result = edit_code(
        SOURCE_LOCAL,
        path="pkg/calc.py",
        new_text="def value():\n    return 42\n",
        confirm=True,
        controls="tests/test_calc.py",
        suite="tests",
    )
    assert result.ok is True
    assert result.metadata["applied"] is False
    assert "no change" in result.reason
