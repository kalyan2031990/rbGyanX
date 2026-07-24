"""Matplotlib backend — PUBLICATION figures (v2 Phase 4 · Slice 2)."""

from __future__ import annotations

import numpy as np

from rbgyanx.viz.base import RenderedFigure, VizBackend
from rbgyanx.viz.spec import DoseResponseSpec, DVHSpec, OptimismSpec

__all__ = ["MatplotlibBackend"]

PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b"]


class MatplotlibBackend(VizBackend):
    """Static, print-ready output for the manuscript's ≤5 main figures."""

    name = "matplotlib"
    interactive = False

    def __init__(self, figsize: tuple[float, float] = (7.0, 4.5), dpi: int = 150) -> None:
        self.figsize = figsize
        self.dpi = dpi

    def _new(self):
        import matplotlib

        matplotlib.use("Agg", force=False)  # headless-safe; Qt embeds via FigureCanvasQTAgg
        import matplotlib.pyplot as plt

        return plt.subplots(figsize=self.figsize, dpi=self.dpi)

    def dvh(self, spec: DVHSpec) -> RenderedFigure:
        fig, ax = self._new()
        for i, c in enumerate(spec.curves):
            ax.plot(
                np.asarray(c.dose_gy, dtype=float),
                np.asarray(c.volume_pct, dtype=float),
                label=c.label,
                color=c.color or PALETTE[i % len(PALETTE)],
                lw=1.6,
            )
        ax.set_xlabel(spec.x_label)
        ax.set_ylabel(spec.y_label)
        ax.set_title(spec.title, fontsize=10)
        ax.set_ylim(0, 105)
        ax.grid(alpha=0.3, lw=0.5)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        return RenderedFigure(fig, self.name)

    def dose_response(self, spec: DoseResponseSpec) -> RenderedFigure:
        fig, ax = self._new()
        for i, c in enumerate(spec.curves):
            colour = c.color or PALETTE[i % len(PALETTE)]
            d = np.asarray(c.dose_gy, dtype=float)
            if c.has_band:
                ax.fill_between(
                    d,
                    np.asarray(c.band_lo, dtype=float),
                    np.asarray(c.band_hi, dtype=float),
                    color=colour,
                    alpha=0.15,
                    lw=0,
                )
            ax.plot(
                d,
                np.asarray(c.probability, dtype=float),
                label=c.label,
                color=colour,
                lw=1.6,
                ls="--" if c.dashed else "-",
            )
        if spec.consensus is not None:
            k = spec.consensus
            d = np.asarray(k.dose_gy, dtype=float)
            if k.has_band:
                ax.fill_between(
                    d,
                    np.asarray(k.band_lo, dtype=float),
                    np.asarray(k.band_hi, dtype=float),
                    color=k.color or "black",
                    alpha=0.12,
                    lw=0,
                )
            ax.plot(
                d,
                np.asarray(k.probability, dtype=float),
                label=k.label,
                color=k.color or "black",
                lw=2.4,
            )
        if spec.reference_dose_gy is not None:
            ax.axvline(spec.reference_dose_gy, color="grey", ls=":", lw=1.0)
            ax.axhline(0.5, color="grey", ls=":", lw=0.8)
        ax.set_xlabel(spec.x_label)
        ax.set_ylabel(spec.y_label)
        ax.set_title(spec.title, fontsize=10)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3, lw=0.5)
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        return RenderedFigure(fig, self.name)

    def optimism(self, spec: OptimismSpec) -> RenderedFigure:
        fig, ax = self._new()
        x = np.arange(len(spec.rows))
        app = [r.apparent for r in spec.rows]
        cv = [r.cross_validated for r in spec.rows]
        ax.plot(x, app, "o-", color=PALETTE[0], label="apparent")
        ax.plot(x, cv, "s--", color=PALETTE[1], label="cross-validated")
        for xi, a, c in zip(x, app, cv, strict=False):
            if np.isfinite(a) and np.isfinite(c):
                ax.vlines(xi, c, a, color="grey", lw=0.8, alpha=0.6)
        if spec.chance_level is not None:
            ax.axhline(spec.chance_level, color="grey", ls=":", lw=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels([r.label for r in spec.rows], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel(spec.y_label)
        ax.set_title(spec.title, fontsize=10)
        ax.legend(fontsize=8, frameon=False, loc="lower left")
        fig.tight_layout()
        return RenderedFigure(fig, self.name)

    def sankey(self, spec) -> RenderedFigure:
        """Publication Sankey rendered as a layered flow diagram.

        Matplotlib has no native Sankey that handles arbitrary DAGs well, so nodes are placed
        in columns by depth and links drawn as width-proportional ribbons. Same data as the
        Plotly view (the specs are shared), just static.
        """
        fig, ax = self._new()

        # Depth of each node = longest path from any source (columns, left to right).
        depth = [0] * len(spec.nodes)
        for _ in range(len(spec.nodes)):
            for link in spec.links:
                depth[link.target] = max(depth[link.target], depth[link.source] + 1)

        columns: dict[int, list[int]] = {}
        for idx, d in enumerate(depth):
            columns.setdefault(d, []).append(idx)

        pos: dict[int, tuple[float, float]] = {}
        for d, members in columns.items():
            for row, idx in enumerate(members):
                y = 1.0 - (row + 0.5) / len(members)
                pos[idx] = (float(d), y)

        max_value = max((link.value for link in spec.links), default=1.0) or 1.0
        for link in spec.links:
            x0, y0 = pos[link.source]
            x1, y1 = pos[link.target]
            ax.plot(
                [x0 + 0.08, x1 - 0.08],
                [y0, y1],
                lw=1.0 + 6.0 * (link.value / max_value),
                alpha=0.35,
                color=spec.nodes[link.source].color or PALETTE[link.source % len(PALETTE)],
                solid_capstyle="round",
            )

        for idx, node in enumerate(spec.nodes):
            x, y = pos[idx]
            ax.scatter([x], [y], s=90, zorder=3, color=node.color or PALETTE[idx % len(PALETTE)])
            ax.annotate(
                node.label,
                (x, y),
                xytext=(0, 11),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )

        ax.set_xlim(-0.5, max(depth) + 0.5)
        ax.set_ylim(-0.05, 1.15)
        ax.axis("off")
        ax.set_title(spec.title, fontsize=10)
        fig.tight_layout()
        return RenderedFigure(fig, self.name)

    def cohort_flow(self, spec) -> RenderedFigure:
        """Publication PRISMA-style inclusion flow with exclusion annotations."""
        fig, ax = self._new()
        labels = [s.label for s in spec.stages]
        counts = [s.n for s in spec.stages]
        y = np.arange(len(spec.stages))

        ax.barh(y, counts, color=PALETTE[0], height=0.55)
        for i, s in enumerate(spec.stages):
            ax.text(counts[i], y[i], f" n={s.n}", va="center", fontsize=8)
            if s.excluded:
                ax.annotate(
                    f"−{s.excluded}: {s.exclusion_reason}",
                    xy=(counts[i], y[i]),
                    xytext=(12, -14),
                    textcoords="offset points",
                    fontsize=7,
                    color=PALETTE[1],
                )
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("patients")
        ax.set_title(spec.title, fontsize=10)
        ax.grid(axis="x", alpha=0.3, lw=0.5)
        fig.tight_layout()
        return RenderedFigure(fig, self.name)
