import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "engine_advanced_f"))

from rbgyanx_engine.run_config import RunConfig
from rbgyanx_advanced_f.integration import enable_part_f_analysis


def test_enable_part_f_bayesian(tmp_path):
    ntcp = []
    rng = np.random.default_rng(1)
    for i in range(25):
        geud = float(rng.uniform(20, 50))
        ntcp.append(
            {
                "AnonPatientID": f"P{i:02d}",
                "structure": "Parotid",
                "gEUD_gy": geud,
                "NTCP_LKB_probit": 0.3,
            }
        )
    out_csv = tmp_path / "outcomes.csv"
    pd.DataFrame(
        {
            "AnonPatientID": [f"P{i:02d}" for i in range(25)],
            "ntcp_outcome": (rng.random(25) > 0.6).astype(int),
        }
    ).to_csv(out_csv, index=False)

    cfg = RunConfig(
        mode="advanced",
        enable_bayesian_ntcp=True,
        outcome_csv=out_csv,
        output_dir=tmp_path,
    )
    _, meta = enable_part_f_analysis(cfg, [], ntcp, pd.DataFrame(), tmp_path)
    assert any("bayesian_ntcp_mean" in r for r in ntcp)
    assert meta.get("bayesian_summary_csv")
