import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from validation.validation_metrics import (
    compute_auc,
    compute_brier,
    expected_calibration_error,
    hosmer_lemeshow,
    validate_ntcp_model,
)


def _synthetic_data(n=200, seed=0):
    rng = np.random.default_rng(seed)
    y_pred = rng.uniform(0.05, 0.95, n)
    y_true = rng.binomial(1, y_pred * 0.85).astype(float)
    return y_true, y_pred


def test_auc_reasonable():
    y_true, y_pred = _synthetic_data()
    auc = compute_auc(y_true, y_pred)
    assert 0.5 < auc < 1.0


def test_validate_ntcp_model_full():
    y_true, y_pred = _synthetic_data()
    vr = validate_ntcp_model(y_true, y_pred, model_name="TEST_LKB", n_bootstrap=50)
    assert not math.isnan(vr.auc)
    assert not math.isnan(vr.brier_score)
    assert not math.isnan(vr.ece)
