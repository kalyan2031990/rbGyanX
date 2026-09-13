import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from dicom_io.dvh_shape_features import compute_dvh_shape_features


def test_shape_features_uniform_dvh():
    dvh = pd.DataFrame(
        {"dose_gy": np.linspace(0, 60, 50), "volume_frac": np.ones(50) / 50}
    )
    f = compute_dvh_shape_features(dvh)
    assert f["D50_gy"] > 0
    assert f["D2_gy"] >= f["D98_gy"]
