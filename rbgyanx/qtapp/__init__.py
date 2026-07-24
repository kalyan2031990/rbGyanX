"""
rbGyanX Qt6 desktop shell (v2 Phase 4 · Slice 3).

A PySide6 view over :mod:`rbgyanx.services` — the same headless orchestration the Tkinter app
uses, so the two cannot diverge scientifically. Launch with::

    python -m rbgyanx.qtapp

PySide6 is an optional dependency: importing this package without it raises a clear message
rather than an opaque ImportError, and the Qt tests skip cleanly.
"""

from __future__ import annotations

__all__ = ["main", "is_available"]


def is_available() -> bool:
    """True when PySide6 is importable (used to skip Qt tests)."""
    import importlib.util

    return importlib.util.find_spec("PySide6") is not None


def main(argv: list[str] | None = None) -> int:
    """Launch the Qt application."""
    if not is_available():
        raise ImportError(
            "the rbGyanX Qt interface needs PySide6: pip install 'PySide6>=6.6'\n"
            "(the Tkinter interface remains available via rbgyanx_gui.py)"
        )
    from rbgyanx.qtapp.main_window import main as _main

    return _main(argv)
