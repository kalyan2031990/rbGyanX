from pathlib import Path

import pandas as pd

from rbgyanx_engine.pipeline import results_to_feature_df


def test_clinical_features_csv_merges(tmp_path):
    clin = pd.DataFrame(
        {
            "AnonPatientID": ["P001", "P002"],
            "age_years": [65, 52],
            "smoking_pack_years": [30, 0],
        }
    )
    clin_path = tmp_path / "clin.csv"
    clin.to_csv(clin_path, index=False)
    results = [
        {"AnonPatientID": "P001", "LocalControl": 1, "TCP_Poisson": 0.7},
        {"AnonPatientID": "P002", "LocalControl": 0, "TCP_Poisson": 0.8},
    ]
    feat = results_to_feature_df(results, clinical_features_csv=clin_path)
    assert "age_years" in feat.columns
    assert feat.loc[feat.AnonPatientID == "P001", "age_years"].iloc[0] == 65
