"""Two runs on identical input must produce byte-identical strings.

Defect #24. ``site_detector`` interpolated raw sets into its evidence strings -
``f"H&N keyword(s): {hn}"`` where ``hn`` is a ``set[str]``. A set renders in string-hash order,
which ``PYTHONHASHSEED`` randomises per process, so two runs on the same input produced
byte-different ``evidence`` values. Observed directly: the same patient gave
``"H&N OAR structures: {'Mandible', 'OralCavity'}"`` in one run and
``"{'OralCavity', 'Mandible'}"`` in another.

That matters because byte-identical comparison is this project's own reproducibility check - it
is how the CRLF false alarm was diagnosed, how the Step A dose-selection replication was
validated against the live run, and how the installer's html_bytes claim was made. A column that
changes on its own defeats the instrument.

The decisive test runs the detector in SEPARATE PROCESSES with DIFFERENT hash seeds, because
within one process the seed is fixed and the bug is invisible.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ENGINE = str(Path(__file__).resolve().parents[1])

# Exercises the keyword path and the OAR-structure path together.
_PROBE = """
import sys
sys.path.insert(0, __ENGINE__)
from dicom_io.site_detector import _fmt, _match_anatomical_site
out = []
out.append(_fmt({"OralCavity", "Mandible", "Larynx", "SpinalCord", "BrainStem"}))
out.append(_fmt(set()))
out.append(_fmt({"Parotid_L"}))
site, ev = _match_anatomical_site("HeadNeck IMRT parotid larynx mandible oral cavity")
out.append(str(site))
out.extend(ev)
print("\\n".join(out))
""".replace("__ENGINE__", repr(_ENGINE))


def _run(seed: str) -> str:
    # inherit the real environment and override only the seed: a stripped env cannot load the
    # interpreter's own dependencies on Windows
    import os

    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    r = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_evidence_strings_are_identical_across_hash_seeds():
    """The claim. Reverting the fix makes these differ for at least one seed pair."""
    outs = {seed: _run(seed) for seed in ("0", "1", "2", "12345", "99991")}
    distinct = set(outs.values())
    assert len(distinct) == 1, (
        "evidence strings vary with PYTHONHASHSEED, so two runs on identical input are not "
        "byte-identical:\n" + "\n---\n".join(sorted(distinct))
    )


def test_fmt_is_sorted_and_stable():
    from dicom_io.site_detector import _fmt

    assert _fmt({"b", "a", "c"}) == "{'a', 'b', 'c'}"
    assert _fmt(set()) == "{}"
    # idempotent regardless of insertion order
    assert _fmt({"OralCavity", "Mandible"}) == _fmt({"Mandible", "OralCavity"})


def test_no_evidence_string_interpolates_a_bare_set():
    """A regression guard on the source itself: catch a new ``{some_set}`` before it ships."""
    import re

    src = (Path(_ENGINE) / "dicom_io" / "site_detector.py").read_text(encoding="utf-8")
    offenders = []
    for line in src.splitlines():
        if "evidence.append(f" not in line:
            continue
        # a brace group that is not already wrapped in _fmt(...) and names a set-ish local
        for m in re.finditer(r"\{([^{}]+)\}", line):
            inner = m.group(1).strip()
            if inner.startswith("_fmt(") or ":" in inner:
                continue
            if re.search(r"canonicals|markers|hits|\b(brain|hn|lung|breast|prostate|pelvis|liver)\b",
                         inner):
                offenders.append(line.strip())
    assert not offenders, "evidence strings interpolating a bare set:\n" + "\n".join(offenders)
