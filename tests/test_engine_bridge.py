"""Tests for rbgyanx-engine bridge (Phase R2 / rbGyanX 1.0)."""

from pathlib import Path

import pytest

from rbgyanx.logic.engine_bridge import (
    detect_input_kind,
    is_engine_available,
    map_site_override,
    needs_subprocess_fallback,
)
from rbgyanx.paths import get_engine_root


def test_engine_root_resolves():
    root = get_engine_root()
    if root is None:
        pytest.skip("rbGyanX_cdss / engine_bundle not installed on this machine")
    assert (root / "rbgyanx_engine" / "__init__.py").is_file()


def test_engine_package_importable():
    root = get_engine_root()
    if root is None:
        pytest.skip("engine not available")
    assert is_engine_available(root)


def test_map_head_neck_site():
    assert map_site_override("HeadNeck") == "HN"


def test_subprocess_fallback_on_fdvh():
    assert needs_subprocess_fallback({"use_fdvh": True}, {})


def test_subprocess_fallback_ntcp_ml():
    assert needs_subprocess_fallback({}, {"enable_ml": True})


def test_no_fallback_classical_dicom_ml_tcp():
    """TCP ML/SHAP in ADVANCED does not force legacy if NTCP ML is off."""
    assert not needs_subprocess_fallback({"enable_ml": True, "enable_shap": True}, {})


def test_detect_unknown_empty_dir(tmp_path):
    assert detect_input_kind(tmp_path) == "unknown"
