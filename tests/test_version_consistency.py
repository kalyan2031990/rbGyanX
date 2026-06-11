"""All surfaced version strings must match engine __version__."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read_version_txt() -> str:
    text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    m = re.search(r"(\d+\.\d+\.\d+)", text)
    assert m, "VERSION.txt must contain semver"
    return m.group(1)


def _read_citation_cff() -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = re.search(r'^version:\s*["\']?([^"\'\n]+)', text, re.M)
    assert m, "CITATION.cff must contain version:"
    return m.group(1).strip('"')


def _read_pyproject() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*["\']([^"\']+)', text, re.M)
    assert m
    return m.group(1)


def test_version_single_source_of_truth():
    from rbgyanx_engine import __version__ as engine_ver

    assert engine_ver == "1.0.0"
    assert _read_version_txt() == engine_ver
    assert _read_citation_cff() == engine_ver
    assert _read_pyproject() == engine_ver

    import rbgyanx

    assert rbgyanx.__version__ == engine_ver
