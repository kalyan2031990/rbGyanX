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
