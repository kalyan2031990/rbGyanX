"""
Plot data contracts (v2 Phase 4 · Slice 2).

Backends render these; they never compute them. Keeping the numbers in plain dataclasses means
the Plotly (interactive) and Matplotlib (publication) renderings of a figure are guaranteed to
show the *same* data — a backend cannot quietly recompute or re-bin anything.

PHI: specs carry curves, labels and metrics only. ``label`` fields are structure/model names
(e.g. "Parotid", "LKB probit"), never patient identifiers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "DVHCurve",
    "DVHSpec",
    "DoseResponseCurve",
    "DoseResponseSpec",
    "OptimismRow",
    "OptimismSpec",
    "SankeyNode",
    "SankeyLink",
    "SankeySpec",
    "FlowStage",
    "CohortFlowSpec",
    "ShapFeature",
    "ShapSpec",
    "shap_spec_from_values",
]


@dataclass
class DVHCurve:
    """One structure's dose-volume histogram."""

    label: str
    dose_gy: Sequence[float]
    volume_pct: Sequence[float]
    color: str | None = None

    def __post_init__(self) -> None:
        if len(self.dose_gy) != len(self.volume_pct):
            raise ValueError(
                f"DVH '{self.label}': dose and volume differ in length "
                f"({len(self.dose_gy)} vs {len(self.volume_pct)})"
            )


@dataclass
class DVHSpec:
    """A DVH panel: one or more structures, cumulative %."""

    curves: list[DVHCurve]
    title: str = "Dose-volume histogram"
    x_label: str = "Dose (Gy)"
    y_label: str = "Volume (%)"

    def __post_init__(self) -> None:
        if not self.curves:
            raise ValueError("DVHSpec needs at least one curve")


@dataclass
class DoseResponseCurve:
    """A model's dose-response, optionally with a Monte-Carlo uncertainty band."""

    label: str
    dose_gy: Sequence[float]
    probability: Sequence[float]
    band_lo: Sequence[float] | None = None
    band_hi: Sequence[float] | None = None
    color: str | None = None
    dashed: bool = False

    def __post_init__(self) -> None:
        if len(self.dose_gy) != len(self.probability):
            raise ValueError(f"'{self.label}': dose and probability differ in length")
        p = np.asarray(self.probability, dtype=float)
        finite = p[np.isfinite(p)]
        if finite.size and (finite.min() < -1e-9 or finite.max() > 1 + 1e-9):
            raise ValueError(f"'{self.label}': probability outside [0, 1]")
        if (self.band_lo is None) != (self.band_hi is None):
            raise ValueError(f"'{self.label}': band needs both band_lo and band_hi")
        if self.band_lo is not None and len(self.band_lo) != len(self.dose_gy):
            raise ValueError(f"'{self.label}': band length must match dose")

    @property
    def has_band(self) -> bool:
        return self.band_lo is not None and self.band_hi is not None


@dataclass
class DoseResponseSpec:
    """Multi-model dose-response panel (TCP/NTCP), with optional consensus overlay."""

    curves: list[DoseResponseCurve]
    consensus: DoseResponseCurve | None = None
    title: str = "Dose-response"
    x_label: str = "Dose (Gy)"
    y_label: str = "Probability"
    reference_dose_gy: float | None = None  # e.g. TD50 marker

    def __post_init__(self) -> None:
        if not self.curves:
            raise ValueError("DoseResponseSpec needs at least one curve")


@dataclass
class OptimismRow:
    """One model's apparent vs cross-validated performance."""

    label: str
    apparent: float
    cross_validated: float

    @property
    def optimism(self) -> float:
        return float(self.apparent - self.cross_validated)


@dataclass
class OptimismSpec:
    """The apparent-vs-CV view — the study's central honesty message."""

    rows: list[OptimismRow]
    title: str = "Apparent vs cross-validated AUC"
    y_label: str = "AUC"
    chance_level: float | None = 0.5
    annotations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("OptimismSpec needs at least one row")


@dataclass
class SankeyNode:
    """One stage in the uncomplicated-control composition."""

    label: str
    color: str | None = None


@dataclass
class SankeyLink:
    """Flow between two nodes, by index into ``SankeySpec.nodes``."""

    source: int
    target: int
    value: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"Sankey link '{self.label}': value must be >= 0")


@dataclass
class SankeySpec:
    """dose → per-OAR NTCP → UTCP (P+), showing how uncomplicated control is composed.

    Adapted from Düzenli et al., SoftwareX 2026, 102773 (Sankey for pipeline composition).
    """

    nodes: list[SankeyNode]
    links: list[SankeyLink]
    title: str = "Dose → OAR NTCP → uncomplicated control"

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("SankeySpec needs at least one node")
        if not self.links:
            raise ValueError("SankeySpec needs at least one link")
        n = len(self.nodes)
        for link in self.links:
            if not (0 <= link.source < n and 0 <= link.target < n):
                raise ValueError(
                    f"Sankey link ({link.source}->{link.target}) is out of range for {n} nodes"
                )
            if link.source == link.target:
                raise ValueError("Sankey link cannot point at its own node")


@dataclass
class FlowStage:
    """One PRISMA-style stage: how many entered, and why any were excluded."""

    label: str
    n: int
    excluded: int = 0
    exclusion_reason: str = ""

    def __post_init__(self) -> None:
        if self.n < 0 or self.excluded < 0:
            raise ValueError(f"Flow stage '{self.label}': counts must be >= 0")
        if self.excluded and not self.exclusion_reason:
            raise ValueError(
                f"Flow stage '{self.label}': {self.excluded} excluded but no reason given"
            )


@dataclass
class CohortFlowSpec:
    """PRISMA-style inclusion flow: screened → contours → dose → endpoint → analysed.

    Maps directly onto the readiness gates, so the figure is publication-ready and the
    exclusions are auditable rather than implicit.
    """

    stages: list[FlowStage]
    title: str = "Cohort flow"

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("CohortFlowSpec needs at least one stage")
        for a, b in zip(self.stages, self.stages[1:], strict=False):
            if b.n > a.n:
                raise ValueError(
                    f"cohort grew from '{a.label}' ({a.n}) to '{b.label}' ({b.n}); "
                    "a flow diagram must be monotone non-increasing"
                )


@dataclass
class ShapFeature:
    """One predictor's global SHAP attribution for an ML model.

    ``mean_abs_shap`` is the mean absolute SHAP value across samples (global importance, always
    >= 0). ``mean_signed_shap`` is the mean signed value: its sign says which way the feature
    pushes the model output on average (e.g. higher dose -> higher predicted complication). It is
    shown as direction only, never as a causal claim.
    """

    name: str
    mean_abs_shap: float
    mean_signed_shap: float = 0.0

    def __post_init__(self) -> None:
        if self.mean_abs_shap < -1e-12:
            raise ValueError(f"SHAP feature '{self.name}': mean_abs_shap must be >= 0")


@dataclass
class ShapSpec:
    """Global feature-attribution panel (mean |SHAP|) for a trained ML model.

    This is an *explanation of a model*, not of the patient: it reports how much each input moved
    the model's output on the data it was fitted to. It only exists when a model was actually
    trained — the app never fabricates SHAP values from a run that had no outcomes.
    """

    features: list[ShapFeature]
    title: str = "Feature attribution (mean |SHAP|)"
    x_label: str = "Mean |SHAP| (impact on model output)"
    base_value: float | None = None
    n_samples: int | None = None

    def __post_init__(self) -> None:
        if not self.features:
            raise ValueError("ShapSpec needs at least one feature")

    def sorted_features(self) -> list[ShapFeature]:
        """Features from most to least important — the canonical SHAP ordering."""
        return sorted(self.features, key=lambda f: f.mean_abs_shap, reverse=True)


def shap_spec_from_values(
    feature_names: Sequence[str],
    shap_values,
    *,
    base_value: float | None = None,
    title: str = "Feature attribution (mean |SHAP|)",
) -> ShapSpec:
    """Build a :class:`ShapSpec` from a model's raw SHAP values.

    ``shap_values`` is a ``(n_samples, n_features)`` array (the per-sample attributions a SHAP
    explainer returns). Each feature's global importance is ``mean(|shap|)`` over samples and its
    direction is ``mean(shap)``. NaNs are ignored per column (exclude-and-count, never impute), so
    a degenerate column does not poison the whole panel.
    """
    sv = np.asarray(shap_values, dtype=float)
    if sv.ndim != 2:
        raise ValueError(f"shap_values must be 2-D (samples x features); got shape {sv.shape}")
    if sv.shape[1] != len(feature_names):
        raise ValueError(
            f"feature_names ({len(feature_names)}) does not match shap_values columns "
            f"({sv.shape[1]})"
        )
    with np.errstate(invalid="ignore"):
        mean_abs = np.nanmean(np.abs(sv), axis=0)
        mean_signed = np.nanmean(sv, axis=0)
    features = [
        ShapFeature(
            name=str(name),
            mean_abs_shap=float(a) if np.isfinite(a) else 0.0,
            mean_signed_shap=float(s) if np.isfinite(s) else 0.0,
        )
        for name, a, s in zip(feature_names, mean_abs, mean_signed, strict=True)
    ]
    return ShapSpec(features=features, title=title, base_value=base_value, n_samples=int(sv.shape[0]))
