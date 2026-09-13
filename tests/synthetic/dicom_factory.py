"""
Synthetic DICOM RT factory (minimal stub for CI).

Full analytic dose-grid DICOM generation is planned; current CI e2e uses
``tps_factory`` (TPS DVH text) which exercises the same radiobiology path.
"""

from __future__ import annotations

from pathlib import Path


def write_placeholder_dicom_folder(out_dir: Path) -> Path:
    """
    Create a folder marker for future synthetic DICOM triples.

    Returns path; tests using real DICOM ingest should use ``@pytest.mark.dicom``
    and local ``test_data/dicom_input`` until factory is complete.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    readme = out_dir / "README_SYNTHETIC_DICOM.txt"
    readme.write_text(
        "Synthetic DICOM RT triples (RTPLAN+RTDOSE+RTSTRUCT) — factory stub.\n"
        "Use tests/synthetic/tps_factory.py for CI e2e until dose grids are implemented.\n",
        encoding="utf-8",
    )
    return out_dir
