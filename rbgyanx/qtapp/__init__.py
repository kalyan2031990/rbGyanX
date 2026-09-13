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
    """True when the Qt widgets layer can actually be imported (used to skip Qt tests).

    Imports ``PySide6.QtWidgets`` rather than asking ``importlib.util.find_spec`` whether the
    PySide6 package exists. Those are different questions, and the difference bites: a headless
    container with PySide6 pip-installed but no system Qt libraries (``libEGL.so.1`` and friends,
    which are not Python dependencies and so are not pulled in by pip) satisfies find_spec and
    then raises ImportError on the first widget import.

    Because the Qt test modules use this as their module-level skip guard, that combination turned
    a should-be-skipped file into a *collection* error, which fails the entire test suite rather
    than one module -- the same failure shape that an unguarded ``import tkinter`` used to cause.
    Attempting the real import is the only check that answers the question being asked.
    """
    try:
        import PySide6.QtWidgets  # noqa: F401
    except Exception:  # ImportError, or an OSError from the dynamic loader
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Launch the Qt application."""
    if not is_available():
        import importlib.util

        if importlib.util.find_spec("PySide6") is None:
            detail = "PySide6 is not installed: pip install 'PySide6>=6.6'"
        else:
            # Distinguish the two failures: "not installed" and "installed but its Qt libraries
            # will not load" need completely different remedies, and conflating them sends the
            # user to reinstall a package that is already there.
            detail = (
                "PySide6 is installed but its Qt libraries could not be loaded. On a minimal "
                "Linux image install the system packages Qt needs, e.g.\n"
                "  apt-get install libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1"
            )
        raise ImportError(
            f"the rbGyanX Qt interface is unavailable. {detail}\n"
            "(the Tkinter interface remains available via rbgyanx_gui.py)"
        )
    from rbgyanx.qtapp.main_window import main as _main

    return _main(argv)
