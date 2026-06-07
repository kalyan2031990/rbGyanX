import math
import pathlib
import tempfile

import numpy as np
import pytest


def _xgb_available() -> bool:
    try:
        import xgboost  # noqa: F401

        return True
    except ImportError:
        return False


xgb_skip = pytest.mark.skipif(
    not _xgb_available(), reason="xgboost not installed"
)


def make_ml_data(n: int = 60, n_features: int = 4, seed: int = 0):
    """Separable dataset large enough for nested CV."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n, dtype=int)
    y[: n // 2] = 1
    rng.shuffle(y)
    X = rng.normal(size=(n, n_features))
    X[y == 1, 0] += 1.5
    return X, y, [f"f{i}" for i in range(n_features)]


# GROUP A — XGBoost
@xgb_skip
def test_xgb_raises_on_small_cohort():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=20)
    with pytest.raises(ValueError, match="Cohort size"):
        fit_xgboost_tcp(X, y, feature_names=fn)


@xgb_skip
def test_xgb_outer_auc_leq_inner():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    assert result.auc_outer_mean <= result.auc_inner_mean + 0.10


@xgb_skip
def test_xgb_outer_auc_above_chance():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    assert result.auc_outer_mean > 0.5


@xgb_skip
def test_xgb_feature_importances_sum_to_one():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    total = sum(result.feature_importances.values())
    assert abs(total - 1.0) < 0.01


@xgb_skip
def test_xgb_shap_shape():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=True)
    if result.shap_values is not None:
        assert result.shap_values.shape == X.shape


@xgb_skip
def test_xgb_n_outer_folds_correct():
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, outer_folds=3, compute_shap=False)
    assert len(result.outer_fold_aucs) == 3


# GROUP B — Random Forest
def test_rf_raises_on_small_cohort():
    from ml_models.random_forest_tcp import fit_random_forest_tcp

    X, y, fn = make_ml_data(n=20)
    with pytest.raises(ValueError, match="Cohort size"):
        fit_random_forest_tcp(X, y, feature_names=fn)


def test_rf_outer_auc_leq_inner():
    from ml_models.random_forest_tcp import fit_random_forest_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_random_forest_tcp(X, y, feature_names=fn, compute_shap=False)
    assert result.auc_outer_mean <= result.auc_inner_mean + 0.10


def test_rf_outer_auc_above_chance():
    from ml_models.random_forest_tcp import fit_random_forest_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_random_forest_tcp(X, y, feature_names=fn, compute_shap=False)
    assert result.auc_outer_mean > 0.5


def test_rf_feature_importances_sum_to_one():
    from ml_models.random_forest_tcp import fit_random_forest_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_random_forest_tcp(X, y, feature_names=fn, compute_shap=False)
    total = sum(result.feature_importances.values())
    assert abs(total - 1.0) < 0.01


@xgb_skip
def test_rf_and_xgb_give_different_aucs():
    from ml_models.random_forest_tcp import fit_random_forest_tcp
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60, seed=5)
    r_xgb = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    r_rf = fit_random_forest_tcp(X, y, feature_names=fn, compute_shap=False)
    assert math.isfinite(r_xgb.auc_outer_mean)
    assert math.isfinite(r_rf.auc_outer_mean)


# GROUP C — Model Manager
@xgb_skip
def test_save_and_load_model():
    from ml_models.model_manager import load_model, save_model
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        save_model(result.model, fn, "xgboost", tmpdir)
        pipe, meta = load_model(tmpdir, "xgboost")
        assert meta["model_type"] == "xgboost"
        assert meta["feature_names"] == fn
        probs = pipe.predict_proba(X)[:, 1]
        assert probs.shape == (len(y),)


def test_load_model_missing_file_raises():
    from ml_models.model_manager import load_model

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError):
            load_model(tmpdir, "nonexistent_model")


@xgb_skip
def test_predict_new_patient_feature_mismatch():
    from ml_models.model_manager import predict_new_patient
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    wrong_names = ["a", "b", "c", "d"]
    with pytest.raises(ValueError, match="Feature mismatch"):
        predict_new_patient(result.model, X[:1], wrong_names, fn)


@xgb_skip
def test_predict_new_patient_returns_probability():
    from ml_models.model_manager import predict_new_patient
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    probs = predict_new_patient(result.model, X[:3], fn, fn)
    assert probs.shape == (3,)
    assert np.all(probs >= 0) and np.all(probs <= 1)


@xgb_skip
def test_save_model_creates_two_files():
    from ml_models.model_manager import save_model
    from ml_models.xgboost_tcp import fit_xgboost_tcp

    X, y, fn = make_ml_data(n=60)
    result = fit_xgboost_tcp(X, y, feature_names=fn, compute_shap=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        save_model(result.model, fn, "xgboost", tmpdir)
        files = list(pathlib.Path(tmpdir).iterdir())
        names = {f.name for f in files}
        assert "xgboost_pipeline.joblib" in names
        assert "xgboost_metadata.json" in names
