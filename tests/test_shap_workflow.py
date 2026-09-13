"""
SHAP explainability workflow: utils/shap_utils.py end to end.

This file was previously zero bytes -- a filename that looked like coverage and provided none.
It is populated rather than deleted because it names a real gap: ``utils/shap_utils.py`` is
shipped in the wheel (``utils*`` is in the packages include list) and had no tests at all, while
the neighbouring SHAP code in ``engine/xai/`` is covered by ``engine/tests/test_xai.py``. The
module is consumed by ``shap_suppl.py`` and by the quarantined ``legacy/code3`` and
``legacy/code6``, so its behaviour is load-bearing for the supplementary figures.

The workflow under test is the one those callers use:

    safe_shap_values -> to_matrix -> plot_summary_bar / plot_beeswarm / generate_shap_caption

Tests concentrate on the parts with real logic and real failure modes -- explainer selection,
the binary-classification list-of-two-arrays reshaping, and the caption's ranking -- rather than
on asserting that matplotlib produced pixels.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_ml]

shap = pytest.importorskip("shap", reason="shap not installed")
pd = pytest.importorskip("pandas")
sklearn = pytest.importorskip("sklearn")

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from utils.shap_utils import (  # noqa: E402
    generate_shap_caption,
    plot_beeswarm,
    plot_summary_bar,
    safe_shap_values,
    to_matrix,
)

FEATURES = ["mean_dose_gy", "V20_pct", "age_years", "volume_cc"]


@pytest.fixture(scope="module")
def dataset():
    """A small separable binary problem, deterministic so SHAP rankings are stable."""
    rng = np.random.default_rng(20260912)
    n = 80
    frame = pd.DataFrame(
        {
            "mean_dose_gy": rng.uniform(10, 60, n),
            "V20_pct": rng.uniform(0, 80, n),
            "age_years": rng.uniform(40, 85, n),
            "volume_cc": rng.uniform(5, 200, n),
        }
    )
    # Outcome driven almost entirely by mean_dose_gy, so it must rank first.
    y = (frame["mean_dose_gy"] + rng.normal(0, 2, n) > 35).astype(int)
    return frame, y


@pytest.fixture(scope="module")
def tree_model(dataset):
    X, y = dataset
    model = RandomForestClassifier(n_estimators=25, random_state=0)
    model.fit(X, y)
    return model


@pytest.fixture(scope="module")
def linear_model(dataset):
    """Not a tree, so safe_shap_values must fall through to KernelExplainer."""
    X, y = dataset
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    return model


# ------------------------------------------------------------ explainer choice


def test_tree_model_uses_the_tree_explainer(tree_model, dataset):
    """The fast path: a tree model must not silently end up on KernelExplainer."""
    X, _ = dataset
    explainer, values = safe_shap_values(tree_model, X, X.iloc[:10])

    assert isinstance(explainer, shap.TreeExplainer)
    assert values is not None


def test_non_tree_model_falls_back_without_raising(linear_model, dataset):
    """The documented fallback. It is slow, so only a few rows are explained."""
    X, _ = dataset
    explainer, values = safe_shap_values(linear_model, X, X.iloc[:3])

    assert explainer is not None
    matrix = to_matrix(values)
    assert matrix.shape[0] == 3


def test_shap_values_cover_every_feature(tree_model, dataset):
    """to_matrix must hand back a 2-D (samples x features) matrix, whatever shap returned.

    shap >= 0.45 gives a binary TreeExplainer result as ``(samples, features, 2)``. to_matrix is
    the function whose job is to reduce that; if it stops doing so, downstream callers get a 3-D
    array where they expect 2-D and generate_shap_caption raises.
    """
    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:10])
    matrix = to_matrix(values)

    assert matrix.ndim == 2, f"expected a 2-D matrix for binary output, got shape {matrix.shape}"
    assert matrix.shape == (10, len(FEATURES))


# ------------------------------------------------------------------- to_matrix


def test_to_matrix_selects_the_positive_class_for_binary_lists():
    """SHAP returns [negative, positive] for some binary models; the positive class is wanted."""
    negative = np.full((4, 3), -1.0)
    positive = np.full((4, 3), 2.0)

    result = to_matrix([negative, positive])

    assert result.shape == (4, 3)
    assert np.allclose(result, 2.0), "to_matrix picked the wrong class"


def test_to_matrix_passes_arrays_through_unchanged():
    values = np.arange(12, dtype=float).reshape(4, 3)
    assert np.array_equal(to_matrix(values), values)


def test_to_matrix_does_not_collapse_a_three_class_list():
    """A 3-element list is multiclass, not binary, and must not be treated as [neg, pos]."""
    values = [np.zeros((2, 3)), np.ones((2, 3)), np.full((2, 3), 2.0)]
    result = to_matrix(values)
    assert result.shape == (3, 2, 3)


# --------------------------------------------------------------------- caption


def test_caption_ranks_the_driving_feature_first(tree_model, dataset):
    """The caption is what reaches the supplement, so its ranking has to be right."""
    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:20])
    # No manual reshaping: to_matrix is responsible for reducing the binary output, and this
    # test is the end-to-end proof that the advertised chain works unaided.
    matrix = to_matrix(values)

    caption = generate_shap_caption(matrix, list(X.columns), "RandomForest", "Parotid")

    assert "Parotid" in caption
    assert "RandomForest" in caption
    assert "1) mean_dose_gy" in caption, f"driving feature not ranked first: {caption}"


def test_caption_reports_three_features_and_is_deterministic(tree_model, dataset):
    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:20])
    matrix = to_matrix(values)

    first = generate_shap_caption(matrix, list(X.columns), "RandomForest", "Parotid")
    second = generate_shap_caption(matrix, list(X.columns), "RandomForest", "Parotid")

    assert first == second, "caption is not reproducible for identical input"
    for rank in ("1)", "2)", "3)"):
        assert rank in first


def test_caption_handles_a_synthetic_ranking_exactly():
    """Pin the ordering rule (mean |SHAP|, descending) without depending on a fitted model."""
    matrix = np.array(
        [
            [0.1, -5.0, 0.2, 1.0],
            [-0.1, 5.0, -0.2, -1.0],
        ]
    )

    caption = generate_shap_caption(matrix, FEATURES, "XGBoost", "Cord")

    assert "1) V20_pct" in caption      # mean |SHAP| = 5.0
    assert "2) volume_cc" in caption    # 1.0
    assert "3) age_years" in caption    # 0.2


def test_caption_uses_absolute_values_not_signed_means():
    """A feature that pushes both ways must not average out to unimportant."""
    matrix = np.array([[10.0, 1.0], [-10.0, 1.0]])

    caption = generate_shap_caption(matrix, ["swings", "steady"], "ANN", "Lung")

    assert "1) swings" in caption


# --------------------------------------------------------------------- plotting


def test_summary_bar_writes_a_png(tree_model, dataset, tmp_path):
    """dpi is lowered from the 1200 default: this asserts a file is produced, not its quality."""
    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:10])
    out = tmp_path / "shap_bar.png"

    plot_summary_bar(to_matrix(values), X.iloc[:10], out, dpi=72)

    assert out.exists() and out.stat().st_size > 0


def test_beeswarm_writes_a_png(tree_model, dataset, tmp_path):
    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:10])
    out = tmp_path / "shap_beeswarm.png"

    plot_beeswarm(to_matrix(values), X.iloc[:10], out, dpi=72)

    assert out.exists() and out.stat().st_size > 0


def test_plotting_closes_its_figures(tree_model, dataset, tmp_path):
    """Both helpers call plt.close(); a leak here would accumulate across a cohort run."""
    import matplotlib.pyplot as plt

    X, _ = dataset
    _, values = safe_shap_values(tree_model, X, X.iloc[:10])
    matrix = to_matrix(values)

    plt.close("all")
    before = len(plt.get_fignums())
    plot_summary_bar(matrix, X.iloc[:10], tmp_path / "a.png", dpi=72)
    plot_beeswarm(matrix, X.iloc[:10], tmp_path / "b.png", dpi=72)

    assert len(plt.get_fignums()) == before, "figures were left open"
