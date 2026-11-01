"""Defect #48 — refuse rather than read DICOM through the obsolete ``dicom`` package.

The fault needs two conditions at once: pydicom >= 3, which removed
``pydicom.dicomio.read_file``, and the obsolete ``dicom`` distribution installed, so
dicompyler-core's import guard falls back to it. The result is the dangerous kind of failure --
not an exception, but every dose grid reading as nothing, so every TCP and NTCP comes out NaN and
a run completes with a full output tree of them.

The project has declared ``pydicom>=2.4,<3`` since v1.1.0, with a comment saying why, and it
happened anyway on a machine whose pydicom was upgraded after the pin was written. A declaration
constrains an install; it cannot constrain an environment that has drifted. Hence a runtime check.

Both branches are exercised by substituting the resolved module, so the test says the same thing
on a sound interpreter and on a broken one.
"""

from __future__ import annotations

import pytest

from dicom_io.reader_guard import (
    OBSOLETE_DICOM_READER,
    assert_pydicom_reader,
    reader_diagnostics,
    warn_if_not_pydicom,
)

SOUND = {
    "read_file_module": "pydicom.filereader",
    "pydicom": "2.4.5",
    "dicompylercore": "0.5.6",
    "is_pydicom": True,
    "error": "",
}
FALLEN_BACK = {
    "read_file_module": "dicom.filereader",
    "pydicom": "3.0.1",
    "dicompylercore": "0.5.6",
    "is_pydicom": False,
    "error": "",
}
UNVERIFIABLE = {
    "read_file_module": "",
    "pydicom": "2.4.5",
    "dicompylercore": "",
    "is_pydicom": False,
    "error": "dicompylercore unimportable: No module named 'dicompylercore'",
}


@pytest.fixture
def resolved(monkeypatch):
    """Substitute what the reader resolved to, without touching the environment."""

    def _set(info: dict):
        monkeypatch.setattr(
            "dicom_io.reader_guard.reader_diagnostics", lambda: dict(info)
        )

    return _set


# --------------------------------------------------------------------- the sound branch


def test_a_pydicom_reader_is_accepted(resolved) -> None:
    resolved(SOUND)
    assert_pydicom_reader()  # must not raise
    assert warn_if_not_pydicom() is True


@pytest.mark.parametrize(
    "module", ["pydicom.filereader", "pydicom.dicomio", "pydicom.fileset"]
)
def test_any_pydicom_submodule_counts_as_sound(resolved, module: str) -> None:
    resolved({**SOUND, "read_file_module": module})
    assert_pydicom_reader()


# --------------------------------------------------------------------- the refusing branch


def test_the_obsolete_package_is_refused(resolved) -> None:
    resolved(FALLEN_BACK)
    with pytest.raises(RuntimeError) as excinfo:
        assert_pydicom_reader()
    message = str(excinfo.value)
    # the message has to be actionable on its own, so it names all four facts
    assert "dicom.filereader" in message
    assert "3.0.1" in message
    assert "0.5.6" in message
    assert "pip uninstall dicom" in message
    assert 'pip install "pydicom>=2.4,<3"' in message


def test_the_refusal_explains_why_the_failure_would_be_silent(resolved) -> None:
    """A reader must understand that the alternative is NaN, not an error."""
    resolved(FALLEN_BACK)
    with pytest.raises(RuntimeError, match="NaN"):
        assert_pydicom_reader()


def test_warn_does_not_raise_but_reports_false(resolved, caplog) -> None:
    """For a GUI banner or a capability report, which must not abort."""
    resolved(FALLEN_BACK)
    with caplog.at_level("ERROR", logger="dicom_io.reader_guard"):
        assert warn_if_not_pydicom() is False
    assert any(OBSOLETE_DICOM_READER in m for m in caplog.messages), caplog.messages


def test_an_unverifiable_reader_is_also_refused(resolved) -> None:
    """Not being able to check is not the same as being fine."""
    resolved(UNVERIFIABLE)
    with pytest.raises(RuntimeError, match=OBSOLETE_DICOM_READER):
        assert_pydicom_reader()


# --------------------------------------------------------------- it guards the real doors


@pytest.mark.parametrize(
    "module, function", [("dicom_io.dvh_extractor", "extract_all_dvhs")]
)
def test_the_dicompylercore_entry_point_calls_the_guard(module: str, function: str) -> None:
    """A guard nothing calls is decoration -- and one on the wrong door is worse.

    ``dvh_extractor`` is the only rbGyanX module that reads DICOM through dicompyler-core, so it
    is the only place the fallback can bite. ``dicom_reader`` and ``cohort_discovery`` call
    pydicom directly; guarding them would refuse runs that are in fact fine, which is what
    happened when this guard was first written and 15 working tests started failing.
    """
    import importlib
    import inspect

    mod = importlib.import_module(module)
    target = getattr(mod, function, None)
    if target is None:  # a method on the module's single class
        target = next(
            getattr(obj, function)
            for _n, obj in inspect.getmembers(mod, inspect.isclass)
            if hasattr(obj, function)
        )
    assert "assert_pydicom_reader" in inspect.getsource(target), f"{module}.{function}"


def test_the_unaffected_readers_are_not_guarded() -> None:
    """Pins the scope, so the guard cannot creep back onto a door it does not belong on."""
    import inspect

    from dicom_io import cohort_discovery, dicom_reader

    for module in (dicom_reader, cohort_discovery):
        src = inspect.getsource(module)
        assert "assert_pydicom_reader" not in src, module.__name__
        assert "pydicom.dcmread" in src, f"{module.__name__} should read with pydicom directly"


# ------------------------------------------------------------- the real environment, reported


def test_the_diagnostics_describe_this_interpreter() -> None:
    """Not an assertion about which environment this is -- only that it can be described."""
    info = reader_diagnostics()
    assert set(info) >= {
        "read_file_module",
        "pydicom",
        "dicompylercore",
        "is_pydicom",
        "error",
    }
    assert isinstance(info["is_pydicom"], bool)


def test_the_manifest_records_the_resolved_reader() -> None:
    """A manifest recording only pydicom's version cannot show which reader was bound."""
    from rbgyanx_engine.cohort_runner import _dicom_reader_record

    record = _dicom_reader_record()
    assert "read_file_module" in record or "error" in record
    if "read_file_module" in record:
        assert set(record) >= {
            "read_file_module",
            "pydicom",
            "dicompylercore",
            "is_pydicom",
        }
