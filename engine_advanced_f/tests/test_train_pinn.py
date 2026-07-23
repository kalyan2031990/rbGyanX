import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "engine_advanced"))
sys.path.insert(0, str(ROOT / "engine_advanced_f"))

torch = pytest.importorskip("torch")

from rbgyanx_advanced.pinn.models.tcp_pinn import PINNTCPAdapter
from rbgyanx_advanced_f.pinn.train_pinn import train_pinn_from_df


def _synthetic_features(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for i in range(n):
        eqd2 = float(rng.uniform(60, 80))
        rows.append(
            {
                "AnonPatientID": f"P{i:03d}",
                "EQD2_gy": eqd2,
                "BED_gy": eqd2 * 1.1,
                "Dmean_gy": eqd2 * 0.9,
                "D95_gy": eqd2 * 0.85,
                "TCP_Poisson": float(rng.uniform(0.3, 0.9)),
                "TCP_gEUD": float(rng.uniform(0.3, 0.9)),
                "tcp_outcome": float(rng.random() > 0.4),
            }
        )
    return pd.DataFrame(rows)


def test_train_pinn_checkpoint_format(tmp_path):
    df = _synthetic_features(30)
    model, hist = train_pinn_from_df(
        df, "HN", tmp_path, epochs=8, min_patients=20, experimental=True
    )
    assert model is not None
    assert hist["val_loss"]
    ckpt_path = tmp_path / "tcp_pinn_hn.pt"
    assert ckpt_path.is_file()
    adapter = PINNTCPAdapter.load(ckpt_path, site="HN")
    assert adapter.model is not None
    assert adapter.feat_names
    assert adapter.feat_means is not None
