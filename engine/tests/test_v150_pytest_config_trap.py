"""The checks must be the same whichever pytest config wins (defects #49, #50).

Defect #50: pytest chooses its rootdir by walking **up** from the command-line arguments to the
nearest ancestor holding a pytest configuration. `pytest engine/tests` from the repository root
therefore stops at `engine/pyproject.toml` and uses that, not the root `pyproject.toml`:

    $ pytest engine/tests/test_v150_dicom_reader_guard.py --collect-only
    rootdir: .../rbGyanX_FINAL_REPO/engine
    configfile: pyproject.toml

The root `addopts` and marker list were silently dropped as a result. `--strict-markers` was off,
so a mistyped marker name would be accepted and the test would run unmarked; the import mode fell
back to `prepend`; and the root `conftest.py` was not loaded. Nothing failed -- the suite simply
ran under weaker settings than the author intended, which is the worst form of this bug.

The fix duplicates the load-bearing options into `engine/pyproject.toml`. These tests are what
stops the two copies drifting apart again: they assert the *effective* configuration, so they fail
under either file if that file stops carrying a required option.

Defect #49 is asserted here too, from the other side: `-q` must not be in `addopts`, because a
`-q` there plus a `-q` on the command line is `-qq` and suppresses the totals line.

On v1.4.0 and on v1.5.0 before this fix, `test_strict_markers_is_in_effect` and
`test_import_mode_is_importlib` fail when the suite is invoked as `pytest engine/tests`, and
`test_quiet_is_not_baked_into_addopts` fails under the root config.
"""

from __future__ import annotations

import pathlib

import pytest

try:  # tomllib is stdlib from 3.11; this project still supports 3.10.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib  # declared in the `dev` extra for python_version < '3.11'

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

REQUIRED_ADDOPTS = ("--import-mode=importlib", "--tb=short", "--strict-markers")

CONFIGS = ("pyproject.toml", "engine/pyproject.toml")


def _ini_options(rel: str) -> dict:
    with open(REPO_ROOT / rel, "rb") as fh:
        data = tomllib.load(fh)
    return data.get("tool", {}).get("pytest", {}).get("ini_options", {})


# --------------------------------------------------------------------------- effective config


def test_strict_markers_is_in_effect(pytestconfig):
    """#50: whichever config was loaded, an unknown marker must be an error."""
    assert pytestconfig.getoption("strict_markers"), (
        "--strict-markers is not in effect. The config actually loaded is "
        f"{pytestconfig.inipath}; it must carry --strict-markers in addopts (defect #50)."
    )


def test_import_mode_is_importlib(pytestconfig):
    """#50: the import mode must not quietly fall back to `prepend`."""
    assert pytestconfig.getoption("importmode") == "importlib", (
        f"import mode is {pytestconfig.getoption('importmode')!r}, not 'importlib'. The config "
        f"actually loaded is {pytestconfig.inipath} (defect #50)."
    )


def test_the_marker_list_is_in_effect(pytestconfig):
    """#50: the root marker list must be available under the engine config too."""
    declared = {line.split(":", 1)[0].strip() for line in pytestconfig.getini("markers")}
    missing = {"requires_ml", "requires_dicom", "slow"} - declared
    assert not missing, (
        f"markers {sorted(missing)} are not declared under {pytestconfig.inipath}. With "
        "--strict-markers on, using one would error; with it off, a typo would pass silently "
        "(defect #50)."
    )


# --------------------------------------------------------------------------- the files themselves


@pytest.mark.parametrize("rel", CONFIGS)
def test_quiet_is_not_baked_into_addopts(rel: str):
    """#49: `-q` in addopts plus `-q` on the command line is `-qq`, which hides the totals."""
    addopts = _ini_options(rel).get("addopts", [])
    assert "-q" not in addopts and "--quiet" not in addopts, (
        f"{rel} bakes a quiet flag into addopts. Combined with a `-q` on the command line that "
        "becomes -qq, and a run with failures prints no summary line at all (defect #49)."
    )


@pytest.mark.parametrize("rel", CONFIGS)
def test_both_configs_carry_the_load_bearing_options(rel: str):
    """#50: the two configs must not drift, because either one can be the one that is used."""
    addopts = _ini_options(rel).get("addopts", [])
    missing = [opt for opt in REQUIRED_ADDOPTS if opt not in addopts]
    assert not missing, (
        f"{rel} is missing {missing} from addopts. Either config can win depending on how pytest "
        "is invoked, so both must carry these (defect #50)."
    )


def test_the_two_marker_lists_agree():
    """#50: a marker declared in one config and not the other is the same trap in slow motion."""
    root = set(_ini_options("pyproject.toml").get("markers", []))
    engine = set(_ini_options("engine/pyproject.toml").get("markers", []))
    assert root == engine, (
        "the root and engine marker lists have diverged; symmetric difference: "
        f"{sorted(root ^ engine)} (defect #50)"
    )
