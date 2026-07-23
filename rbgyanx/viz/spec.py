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
