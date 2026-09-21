"""Regression for the SPARK canonical-key collision (B.1).

`collect_txt_tcp` itself has always appended to a plain list -- the collapse this covers happened
one layer down, in `_read_txt_structures` (see test_txt_dvh_reader.py for the unit-level version).
This test proves the fix holds end to end, at the actual TCP row output: a multi-structure
dvh_txt file, run through the exact code path a cohort uses, must produce one TCP row per
structure, never fewer, even though several of them collide on the same canonical name.
"""
from pathlib import Path

import pytest

from rbgyanx_engine.pipeline import collect_txt_tcp

_FIXTURE = """\
Patient ID           : MS-003
Prescribed dose [Gy]: 36.25

Structure: Bladder
Mean Dose [Gy]: 7.0
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
5    60
10   20
15   0

Structure: Rectum
Mean Dose [Gy]: 10.0
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
8    70
16   10
20   0

Structure: PTV
Mean Dose [Gy]: 36.9
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
36   99
38   40
40   0
"""


def test_collect_txt_tcp_keeps_every_colliding_structure(tmp_path: Path) -> None:
    d = tmp_path / "dvh"
    d.mkdir()
    (d / "MS-003_PlanSumwithKIM.txt").write_text(_FIXTURE, encoding="utf-8")

    results = collect_txt_tcp(
        d,
        site_override="PROSTATE",  # bypass per-structure site auto-detection (tracked separately)
        user_config=None,
        glob_pattern="*.txt",
        default_dpf_gy=2.0,
        preserve_canonical=False,  # the SPARK cohort's actual configuration
    )

    assert len(results) == 3, (
        "one or more structures colliding on canonical 'PTV' was silently discarded -- "
        f"got {len(results)} row(s): {[r.get('raw_name') for r in results]}"
    )
    by_raw = {r["raw_name"]: r for r in results}
    assert {"Bladder", "Rectum", "PTV"} == set(by_raw)
    # Each row's own DVH-derived value (recomputed from that structure's own curve by
    # TCPCalculator, not the header's stated mean -- see test_txt_dvh_reader.py for the
    # header-value check), not one contaminated survivor's: distinct and clinically ordered
    # (Bladder/Rectum are OARs receiving far less of this plan's dose than the PTV boost).
    means = {name: row["Dmean_gy"] for name, row in by_raw.items()}
    assert len({round(v, 3) for v in means.values()}) == 3, f"means not distinct: {means}"
    assert means["Bladder"] < means["Rectum"] < means["PTV"], means
