import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "engine_advanced"))

from radiobiology.model_registry import clear_registries, iter_tcp_models
from rbgyanx_advanced.integration import register_pinn_models


def test_register_pinn_stub():
    clear_registries()
    assert register_pinn_models(None, "HN")
    assert "PINN_STUB" in iter_tcp_models()
    adapter = iter_tcp_models()["PINN_STUB"]
    dvh = pd.DataFrame({"dose_gy": np.linspace(0, 70, 20), "volume_frac": np.ones(20) / 20})
    out = adapter.compute_tcp_dvh(dvh, 30, type("P", (), {"alpha_beta_gy": 10.0})(), "GTV")
    assert math.isnan(out["tcp"])
