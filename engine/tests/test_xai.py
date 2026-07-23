import pathlib
import tempfile

import numpy as np
import pytest


def make_fake_model(n_features: int = 4):
    """Minimal sklearn-compatible model that returns fixed probabilities."""
    from sklearn.dummy import DummyClassifier

    clf = DummyClassifier(strategy="constant", constant=1)
    X = np.random.default_rng(0).normal(size=(30, n_features))
    y = np.array([0] * 15 + [1] * 15)
    clf.fit(X, y)
    return clf, X, y


def make_fake_shap_values(n_samples: int = 20, n_features: int = 4, seed: int = 0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n_samples, n_features))


def test_shap_global_creates_file():
    from xai.shap_tcp import plot_shap_global

    sv = make_fake_shap_values()
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_shap_global(
            sv, [f"f{i}" for i in range(4)], pathlib.Path(tmp) / "shap_global.png"
        )
        assert out.exists()
        assert out.stat().st_size > 1000


def test_shap_waterfall_creates_file():
    from xai.shap_tcp import plot_shap_waterfall

    sv = make_fake_shap_values(1)[0]
    fv = np.array([0.8, 60.0, 55.0, 290.0])
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_shap_waterfall(
            sv,
            [f"f{i}" for i in range(4)],
            fv,
            expected_value=-0.5,
            predicted_prob=0.85,
            patient_id="PT001",
            output_path=pathlib.Path(tmp) / "waterfall.png",
        )
        assert out.exists()


def test_shap_consistency_passes_with_exact_values():
    from xai.shap_tcp import verify_shap_consistency

    probs = np.array([0.7, 0.3, 0.9])
    ev = -0.5
    log_odds = np.log(probs / (1 - probs))
    shap_values = np.column_stack([log_odds - ev, np.zeros_like(log_odds)])
    result = verify_shap_consistency(shap_values, ev, probs, tolerance=1e-6)
    assert result["all_pass"]
    assert result["max_deviation"] < 1e-6


def test_shap_consistency_detects_violation():
    from xai.shap_tcp import verify_shap_consistency

    probs = np.array([0.7, 0.3])
    ev = -0.5
    shap_values = np.array([[100.0, 0.0], [0.0, 0.0]])
    result = verify_shap_consistency(shap_values, ev, probs, tolerance=0.01)
    assert not result["all_pass"]
    assert result["n_violations"] >= 1


def test_shap_global_top_n_respected():
    from xai.shap_tcp import plot_shap_global

    sv = make_fake_shap_values(n_features=10, n_samples=20)
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_shap_global(
            sv, [f"f{i}" for i in range(10)], pathlib.Path(tmp) / "g.png", top_n=5
        )
        assert out.exists()


def test_compute_pdp_ice_shapes():
    from xai.pdp_ice import compute_pdp_ice

    clf, X, _ = make_fake_model()
    grid, pdp, ice = compute_pdp_ice(clf, X, feature_idx=0, grid_points=20)
    assert grid.shape == (20,)
    assert pdp.shape == (20,)
    assert ice.shape == (30, 20)


def test_pdp_values_between_0_and_1():
    from xai.pdp_ice import compute_pdp_ice

    clf, X, _ = make_fake_model()
    _, pdp, _ = compute_pdp_ice(clf, X, feature_idx=1, grid_points=10)
    assert np.all(pdp >= 0) and np.all(pdp <= 1)


def test_plot_pdp_ice_creates_file():
    from xai.pdp_ice import compute_pdp_ice, plot_pdp_ice

    clf, X, _ = make_fake_model()
    grid, pdp, ice = compute_pdp_ice(clf, X, feature_idx=0, grid_points=20)
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_pdp_ice(grid, pdp, ice, "f0", pathlib.Path(tmp) / "pdp.png")
        assert out.exists()


def test_plot_pdp_ice_with_classical_overlay():
    from xai.pdp_ice import compute_pdp_ice, plot_pdp_ice

    clf, X, _ = make_fake_model()
    grid, pdp, ice = compute_pdp_ice(clf, X, feature_idx=0, grid_points=10)
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_pdp_ice(
            grid,
            pdp,
            ice,
            "f0",
            pathlib.Path(tmp) / "pdp_overlay.png",
            classical_tcp_fn=lambda g: np.clip(g / g.max(), 0, 1),
        )
        assert out.exists()


def test_lime_creates_file_and_returns_dict():
    pytest.importorskip("lime")
    from xai.lime_tcp import explain_patient_lime

    clf, X, _ = make_fake_model()
    with tempfile.TemporaryDirectory() as tmp:
        result = explain_patient_lime(
            clf,
            X[0],
            X,
            [f"f{i}" for i in range(4)],
            patient_id="PT001",
            output_path=pathlib.Path(tmp) / "lime.png",
            num_samples=200,
        )
        assert pathlib.Path(tmp, "lime.png").exists()
        assert "predicted_prob" in result
        assert 0 <= result["predicted_prob"] <= 1


def test_lime_raises_without_lime_package(monkeypatch):
    import builtins

    from xai.lime_tcp import explain_patient_lime

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "lime" in name:
            raise ImportError("lime not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    clf, X, _ = make_fake_model()
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ImportError, match="lime"):
            explain_patient_lime(
                clf,
                X[0],
                X,
                [f"f{i}" for i in range(4)],
                "PT001",
                pathlib.Path(tmp) / "out.png",
            )


def test_lime_returns_correct_number_of_features():
    pytest.importorskip("lime")
    from xai.lime_tcp import explain_patient_lime

    clf, X, _ = make_fake_model()
    with tempfile.TemporaryDirectory() as tmp:
        result = explain_patient_lime(
            clf,
            X[0],
            X,
            [f"f{i}" for i in range(4)],
            "PT002",
            pathlib.Path(tmp) / "l.png",
            num_features=3,
            num_samples=200,
        )
        assert len(result["feature_labels"]) <= 3
