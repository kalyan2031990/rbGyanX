"""
Portability guards for the AI modules.

CI runs Python 3.10-3.12; a developer machine may be newer. That gap hid a real defect:
``Path.read_text(newline=...)`` only exists from 3.13, so edit_code worked locally and was
broken on every version the project actually supports. These tests fail on the developer's
machine rather than waiting for CI to find it again.
"""

from __future__ import annotations

import ast
import re
import sys

import pytest
from rbgyanx.ai.scrubber import install_root

AI_SOURCES = sorted((install_root() / "rbgyanx" / "ai").rglob("*.py"))
SCRIPTS = sorted((install_root() / "scripts").glob("*ai*.py")) + [
    install_root() / "scripts" / "export_ai_audit.py"
]

#: The lowest version this project claims to support, from pyproject's requires-python.
MIN_SUPPORTED = (3, 10)


def test_the_supported_floor_is_what_we_think_it_is():
    text = (install_root() / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10,<3.13"' in text, "update MIN_SUPPORTED if this changed"


@pytest.mark.parametrize("source", AI_SOURCES, ids=lambda p: p.name)
def test_no_pathlib_read_write_text_newline_kwarg(source):
    """Path.read_text/write_text gained `newline` in 3.13. The builtin open() always had it."""
    # Comments are stripped first: this file explains the very call it forbids, and so
    # does edit.py's own note about why it uses open() instead.
    text = chr(10).join(
        line
        for line in source.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )
    for call in ("read_text", "write_text"):
        for match in re.finditer(rf"\.{call}\(([^)]*)\)", text):
            assert "newline" not in match.group(1), (
                f"{source.name}: .{call}(newline=...) needs Python 3.13; "
                "use the builtin open(..., newline=...) instead"
            )


@pytest.mark.parametrize("source", AI_SOURCES, ids=lambda p: p.name)
def test_ai_modules_parse_on_the_supported_floor(source):
    """A syntax feature newer than the floor would break the install, not just a test."""
    if sys.version_info < MIN_SUPPORTED:  # pragma: no cover - we never run below the floor
        pytest.skip("running below the supported floor")
    ast.parse(source.read_text(encoding="utf-8"), filename=str(source))


def test_windows_paths_are_external_on_every_platform():
    """A drive-lettered path is not inside a POSIX install tree, whatever resolve() does."""
    from rbgyanx.ai.scrubber import scrub_traceback

    bs = chr(92)
    win = "C:" + bs + "Data" + bs + "PAROTID" + bs + "Doe_Jane" + bs + "run.py"
    unc = bs * 2 + "nas" + bs + "onc" + bs + "Doe_Jane" + bs + "run.py"
    for raw in (win, unc):
        result = scrub_traceback(f'  File "{raw}", line 3, in main' + chr(10))
        assert "Doe_Jane" not in result.text
        assert "REDACTED" in result.text


def test_posix_data_paths_are_external_on_every_platform():
    from rbgyanx.ai.scrubber import scrub_traceback

    result = scrub_traceback('  File "/data/patients/Doe_Jane/run.py", line 3, in main' + chr(10))
    assert "Doe_Jane" not in result.text
    assert "REDACTED" in result.text
