"""
Qt packaging prerequisites (v2 Phase 4 · Slice 3).

A full PyInstaller build is far too slow for the test suite, so instead we assert the things
that actually break Qt installers:

  * the Qt spec exists, parses, and targets the Qt entry point;
  * ``collect_all`` really finds the QtWebEngine helper process, its ``.pak`` resources and
    locales — the usual cause of a "blank window" in a packaged Qt app;
  * the existing Tkinter spec is untouched and still ships the Tk app.

Skips cleanly without PySide6 / PyInstaller.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
QT_SPEC = ROOT / "packaging" / "rbGyanX-qt.spec"
TK_SPEC = ROOT / "packaging" / "rbGyanX.spec"


def test_qt_spec_exists_and_parses():
    assert QT_SPEC.exists(), "packaging/rbGyanX-qt.spec is missing"
    ast.parse(QT_SPEC.read_text(encoding="utf-8"))  # syntactically valid Python


def test_qt_spec_targets_the_qt_entry_point_and_branding():
    text = QT_SPEC.read_text(encoding="utf-8")
    assert 'ROOT / "rbgyanx" / "qtapp" / "__main__.py"' in text
    assert "QtWebEngineWidgets" in text, "QtWebEngine must be collected for embedded plots"
    assert '"assets"' in text, "existing rbGyanX branding must ship with the Qt build"
    assert '"tkinter"' in text and "excludes" in text  # Qt build drops the Tk stack


def test_tkinter_spec_is_unchanged_and_still_ships():
    """Do-no-harm: the shipping Tkinter installer must not be disturbed by the Qt work."""
    text = TK_SPEC.read_text(encoding="utf-8")
    assert "rbgyanx_gui.py" in text
    assert "QtWebEngine" not in text


@pytest.mark.skipif(
    pytest.importorskip("PySide6", reason="PySide6 not installed") is None, reason="no PySide6"
)
def test_qtwebengine_runtime_files_are_collectable():
    """The packaged app needs QtWebEngineProcess + resources; prove they are discoverable."""
    pytest.importorskip("PyInstaller", reason="PyInstaller not installed")
    from PyInstaller.utils.hooks import collect_all

    # Collect from the PACKAGE. PySide6.QtWebEngineCore is a *module*, so PyInstaller skips
    # its data/binaries with only a warning — a build using it ships without the helper
    # process and the embedded plot renders blank. This test exists because that happened.
    datas, binaries, _hidden = collect_all("PySide6")
    names = [Path(src).name.lower() for src, _dest in (datas + binaries)]

    assert any("qtwebengineprocess" in n for n in names), (
        "QtWebEngineProcess helper not collected — a packaged Qt app would show a blank plot"
    )
    assert any(n.endswith(".pak") for n in names), "QtWebEngine .pak resources not collected"


def test_qt_spec_collects_from_the_pyside6_package_not_the_module():
    """Regression guard for the blank-plot packaging bug described above."""
    text = QT_SPEC.read_text(encoding="utf-8")
    assert 'for module in ("PySide6", "plotly")' in text, (
        "spec must collect_all('PySide6'); collecting the QtWebEngineCore module collects nothing"
    )


@pytest.mark.skipif(
    pytest.importorskip("PySide6", reason="PySide6 not installed") is None, reason="no PySide6"
)
def test_qtwebengine_importable_at_runtime():
    pytest.importorskip("PySide6.QtWebEngineWidgets")
