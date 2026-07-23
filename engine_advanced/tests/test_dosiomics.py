import numpy as np

from rbgyanx_advanced.dose3d.dose_grid_extractor import synthetic_oar_dose_voxels
from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features


def test_synthetic_dose_voxels():
    v = synthetic_oar_dose_voxels(n_voxels=200, mean_dose_gy=50.0, seed=1)
    assert len(v) == 200
    assert 0 <= v.mean() <= 80


def test_dosiomics_features():
    v = synthetic_oar_dose_voxels(mean_dose_gy=45.0, std_gy=5.0, seed=2)
    f = extract_dosiomics_features(v, oar_name="Parotid_L")
    assert "dosio_Parotid_L_mean" in f
    assert f["dosio_Parotid_L_mean"] > 0
