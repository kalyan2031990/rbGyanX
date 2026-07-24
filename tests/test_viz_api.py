"""
Swappable visualisation API (v2 Phase 4 · Slice 2).

The contract under test: **both backends render the same data**. Specs hold the numbers, so a
backend cannot silently recompute or re-bin — an interactive Plotly view and the publication
Matplotlib figure must be two renderings of one truth.

Also covers spec validation (bad input rejected early, with a useful message) and the PHI rule
that specs carry curves and labels only.
"""

from __future__ import annotations

import numpy as np
import pytest
from rbgyanx.viz import (
    CohortFlowSpec,
    DoseResponseCurve,
    DoseResponseSpec,
    DVHCurve,
    DVHSpec,
    FlowStage,
    OptimismRow,
    OptimismSpec,
    SankeyLink,
    SankeyNode,
    SankeySpec,
    available_backends,
    get_backend,
)

pytestmark = pytest.mark.unit

BACKENDS = sorted(available_backends())


# --------------------------------------------------------------------------- specs


def _dvh_spec() -> DVHSpec:
    dose = np.linspace(0, 70, 60)
    return DVHSpec(
        curves=[
            DVHCurve("PTV70", dose, np.clip(100 - (dose / 70) ** 6 * 100, 0, 100)),
            DVHCurve("Parotid", dose, np.clip(100 * np.exp(-dose / 18), 0, 100)),
        ],
        title="Synthetic DVH",
    )


def _dose_response_spec() -> DoseResponseSpec:
    dose = np.linspace(0, 80, 50)
    probit = 1 / (1 + np.exp(-(dose - 40) / 6))
    loglog = 1 / (1 + (40 / np.maximum(dose, 1e-6)) ** 3)
    band = 0.06
    return DoseResponseSpec(
        curves=[
            DoseResponseCurve(
                "LKB probit",
                dose,
                probit,
                band_lo=np.clip(probit - band, 0, 1),
                band_hi=np.clip(probit + band, 0, 1),
            ),
            DoseResponseCurve("LKB log-logistic", dose, loglog, dashed=True),
        ],
        consensus=DoseResponseCurve(
            "uNTCP consensus",
            dose,
            (probit + loglog) / 2,
            band_lo=np.clip((probit + loglog) / 2 - band, 0, 1),
            band_hi=np.clip((probit + loglog) / 2 + band, 0, 1),
        ),
        reference_dose_gy=40.0,
        title="Synthetic dose-response",
    )


def _optimism_spec() -> OptimismSpec:
    return OptimismSpec(
        rows=[
            OptimismRow("classical", 0.60, 0.60),
            OptimismRow("covariate", 0.72, 0.64),
            OptimismRow("dosiomics RF", 1.00, 0.63),
        ]
    )


SPECS = {"dvh": _dvh_spec, "dose_response": _dose_response_spec, "optimism": _optimism_spec}


# --------------------------------------------------------------------- rendering


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("kind", sorted(SPECS))
def test_every_backend_renders_every_spec(backend, kind):
    fig = get_backend(backend).render(SPECS[kind]())
    assert fig.figure is not None
    assert fig.backend == backend


@pytest.mark.parametrize("backend", BACKENDS)
def test_saves_to_disk(backend, tmp_path):
    fig = get_backend(backend).dvh(_dvh_spec())
    suffix = ".html" if backend == "plotly" else ".png"
    out = fig.save(tmp_path / f"dvh{suffix}")
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.parametrize("backend", BACKENDS)
def test_to_html_works_for_both_backends(backend):
    html = get_backend(backend).optimism(_optimism_spec()).to_html()
    assert html.strip().lower().startswith(("<!doctype", "<html", "<div"))
    assert len(html) > 200


# ------------------------------------------------- the point: backends agree on data


def _plotly_series(fig) -> list[tuple[tuple, tuple]]:
    out = []
    for tr in fig.figure.data:
        if getattr(tr, "fill", None) == "toself":  # uncertainty band polygon
            continue
        if tr.x is not None and tr.y is not None:
            out.append((tuple(np.asarray(tr.x, dtype=float)), tuple(np.asarray(tr.y, dtype=float))))
    return out


def _mpl_series(fig) -> list[tuple[tuple, tuple]]:
    """Data series from a Matplotlib axes, skipping reference lines.

    ``axvline``/``axhline`` add 2-point guides whose data are plain lists, so filter on
    length and coerce explicitly.
    """
    ax = fig.figure.axes[0]
    out = []
    for ln in ax.get_lines():
        x = np.asarray(ln.get_xdata(orig=True), dtype=float)
        y = np.asarray(ln.get_ydata(orig=True), dtype=float)
        if x.size > 2:  # a real curve, not an axhline/axvline guide
            out.append((tuple(x), tuple(y)))
    return out


@pytest.mark.skipif(len(BACKENDS) < 2, reason="needs both backends installed")
def test_dvh_data_identical_across_backends():
    spec = _dvh_spec()
    p = _plotly_series(get_backend("plotly").dvh(spec))
    m = _mpl_series(get_backend("matplotlib").dvh(spec))
    assert len(p) == len(m) == len(spec.curves)
    for (px, py), (mx, my) in zip(p, m, strict=True):
        np.testing.assert_allclose(px, mx, rtol=0, atol=0)
        np.testing.assert_allclose(py, my, rtol=0, atol=0)


@pytest.mark.skipif(len(BACKENDS) < 2, reason="needs both backends installed")
def test_dose_response_curves_identical_across_backends():
    spec = _dose_response_spec()
    p = _plotly_series(get_backend("plotly").dose_response(spec))
    m = _mpl_series(get_backend("matplotlib").dose_response(spec))
    # 2 model curves + 1 consensus, in the same order, in both engines
    assert len(p) == len(m) == 3
    for (px, py), (mx, my) in zip(p, m, strict=True):
        np.testing.assert_allclose(px, mx, rtol=0, atol=0)
        np.testing.assert_allclose(py, my, rtol=0, atol=0)


@pytest.mark.skipif(len(BACKENDS) < 2, reason="needs both backends installed")
def test_optimism_values_identical_across_backends():
    spec = _optimism_spec()
    p = get_backend("plotly").optimism(spec)
    m = get_backend("matplotlib").optimism(spec)
    p_app = tuple(np.asarray(p.figure.data[0].y, dtype=float))
    m_app = tuple(_mpl_series(m)[0][1])
    np.testing.assert_allclose(p_app, m_app, rtol=0, atol=0)
    np.testing.assert_allclose(p_app, [r.apparent for r in spec.rows], rtol=0, atol=0)


# --------------------------------------------------------------------- validation


def test_backend_registry():
    assert "matplotlib" in available_backends()
    with pytest.raises(ValueError, match="unknown viz backend"):
        get_backend("gnuplot")


def test_dvh_curve_length_mismatch_rejected():
    with pytest.raises(ValueError, match="differ in length"):
        DVHCurve("bad", [1, 2, 3], [1, 2])


def test_dose_response_rejects_probability_outside_unit_interval():
    with pytest.raises(ValueError, match=r"probability outside"):
        DoseResponseCurve("bad", [1, 2], [0.5, 1.4])


def test_dose_response_band_needs_both_bounds():
    with pytest.raises(ValueError, match="band needs both"):
        DoseResponseCurve("bad", [1, 2], [0.1, 0.2], band_lo=[0.0, 0.1])


def test_empty_specs_rejected():
    for factory, msg in (
        (lambda: DVHSpec(curves=[]), "at least one curve"),
        (lambda: DoseResponseSpec(curves=[]), "at least one curve"),
        (lambda: OptimismSpec(rows=[]), "at least one row"),
    ):
        with pytest.raises(ValueError, match=msg):
            factory()


def test_optimism_row_computes_the_gap():
    assert OptimismRow("rf", 1.0, 0.63).optimism == pytest.approx(0.37)


def test_specs_carry_no_patient_identifiers():
    """Labels are structures/models; specs never hold ids or free text from a record."""
    spec = _dvh_spec()
    assert all(c.label in {"PTV70", "Parotid"} for c in spec.curves)
    assert not hasattr(spec, "patient_id")


# ------------------------------------------------- Sankey + cohort flow (Slice 5)


def _sankey_spec() -> SankeySpec:
    """dose -> per-OAR NTCP -> uncomplicated control (P+)."""
    return SankeySpec(
        nodes=[
            SankeyNode("Prescribed dose"),
            SankeyNode("Rectum NTCP"),
            SankeyNode("Bladder NTCP"),
            SankeyNode("Uncomplicated control (P+)"),
        ],
        links=[
            SankeyLink(0, 1, 60.0, "rectum share"),
            SankeyLink(0, 2, 40.0, "bladder share"),
            SankeyLink(1, 3, 54.0, "no rectal complication"),
            SankeyLink(2, 3, 36.0, "no bladder complication"),
        ],
    )


def _cohort_flow_spec() -> CohortFlowSpec:
    return CohortFlowSpec(
        stages=[
            FlowStage("Screened", 140),
            FlowStage("With contours", 128, excluded=12, exclusion_reason="no RTSTRUCT"),
            FlowStage("With dose", 124, excluded=4, exclusion_reason="no RTDOSE"),
            FlowStage("With endpoint", 121, excluded=3, exclusion_reason="outcome missing"),
            FlowStage("Analysed", 121),
        ]
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_backends_render_sankey_and_cohort_flow(backend):
    engine = get_backend(backend)
    assert engine.render(_sankey_spec()).figure is not None
    assert engine.render(_cohort_flow_spec()).figure is not None


@pytest.mark.parametrize("backend", BACKENDS)
def test_new_views_save_and_export(backend, tmp_path):
    engine = get_backend(backend)
    suffix = ".html" if backend == "plotly" else ".png"
    for name, spec in (("sankey", _sankey_spec()), ("flow", _cohort_flow_spec())):
        out = engine.render(spec).save(tmp_path / f"{name}{suffix}")
        assert out.exists() and out.stat().st_size > 0


def test_sankey_rejects_structurally_invalid_graphs():
    node = SankeyNode("only")
    with pytest.raises(ValueError, match="out of range"):
        SankeySpec(nodes=[node], links=[SankeyLink(0, 5, 1.0)])
    with pytest.raises(ValueError, match="own node"):
        SankeySpec(nodes=[node, SankeyNode("b")], links=[SankeyLink(0, 0, 1.0)])
    with pytest.raises(ValueError, match="value must be"):
        SankeyLink(0, 1, -3.0)
    with pytest.raises(ValueError, match="at least one node"):
        SankeySpec(nodes=[], links=[SankeyLink(0, 1, 1.0)])


def test_cohort_flow_must_be_monotone_non_increasing():
    """A flow diagram cannot gain patients; that would hide a data error."""
    with pytest.raises(ValueError, match="cohort grew"):
        CohortFlowSpec(stages=[FlowStage("Screened", 100), FlowStage("Analysed", 120)])


def test_cohort_flow_requires_a_reason_for_every_exclusion():
    """Exclusions must be auditable — a count with no reason is rejected."""
    with pytest.raises(ValueError, match="no reason given"):
        FlowStage("With contours", 90, excluded=10)


def test_cohort_flow_totals_are_internally_consistent():
    spec = _cohort_flow_spec()
    for a, b in zip(spec.stages, spec.stages[1:], strict=False):
        assert b.n <= a.n
        if b.excluded:
            assert a.n - b.n == b.excluded, f"{b.label}: drop != declared exclusions"


def test_sankey_conserves_flow_into_the_outcome_node():
    """P+ inflow cannot exceed what entered the OAR nodes (complications only subtract)."""
    spec = _sankey_spec()
    into_oars = sum(link.value for link in spec.links if link.target in (1, 2))
    into_pplus = sum(link.value for link in spec.links if link.target == 3)
    assert into_pplus <= into_oars
