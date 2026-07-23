"""Plotly backend — INTERACTIVE views (v2 Phase 4 · Slice 2).

Rendered into the Qt app through ``QWebEngineView`` (Slice 3) and exportable as standalone
HTML for the supplement. Hover, legend-toggle and zoom come for free, which is what the
"watch it work" run view needs.
"""

from __future__ import annotations

import numpy as np

from rbgyanx.viz.base import RenderedFigure, VizBackend
from rbgyanx.viz.spec import DoseResponseSpec, DVHSpec, OptimismSpec

__all__ = ["PlotlyBackend"]

PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b"]


def _rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


class PlotlyBackend(VizBackend):
    """Interactive counterpart to :class:`MatplotlibBackend`, same specs."""

    name = "plotly"
    interactive = True

    def __init__(self, template: str = "plotly_white", height: int = 460) -> None:
        self.template = template
        self.height = height

    def _layout(self, fig, spec_title: str, x_label: str, y_label: str) -> None:
        fig.update_layout(
            title=dict(text=spec_title, font=dict(size=14)),
            xaxis_title=x_label,
            yaxis_title=y_label,
            template=self.template,
            height=self.height,
            margin=dict(l=60, r=20, t=50, b=50),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        )

    def dvh(self, spec: DVHSpec) -> RenderedFigure:
        import plotly.graph_objects as go

        fig = go.Figure()
        for i, c in enumerate(spec.curves):
            fig.add_trace(
                go.Scatter(
                    x=list(np.asarray(c.dose_gy, dtype=float)),
                    y=list(np.asarray(c.volume_pct, dtype=float)),
                    name=c.label,
                    mode="lines",
                    line=dict(color=c.color or PALETTE[i % len(PALETTE)], width=2),
                    hovertemplate="%{y:.1f}% at %{x:.1f} Gy<extra>" + c.label + "</extra>",
                )
            )
        self._layout(fig, spec.title, spec.x_label, spec.y_label)
        fig.update_yaxes(range=[0, 105])
        return RenderedFigure(fig, self.name)

    def dose_response(self, spec: DoseResponseSpec) -> RenderedFigure:
        import plotly.graph_objects as go

        fig = go.Figure()

        def _add(c, width: int, colour: str) -> None:
            d = list(np.asarray(c.dose_gy, dtype=float))
            if c.has_band:
                lo = list(np.asarray(c.band_lo, dtype=float))
                hi = list(np.asarray(c.band_hi, dtype=float))
                fig.add_trace(
                    go.Scatter(
                        x=d + d[::-1],
                        y=hi + lo[::-1],
                        fill="toself",
                        fillcolor=_rgba(colour, 0.15),
                        line=dict(width=0),
                        name=f"{c.label} (MC band)",
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x=d,
                    y=list(np.asarray(c.probability, dtype=float)),
                    name=c.label,
                    mode="lines",
                    line=dict(color=colour, width=width, dash="dash" if c.dashed else "solid"),
                    hovertemplate="%{y:.3f} at %{x:.1f} Gy<extra>" + c.label + "</extra>",
                )
            )

        for i, c in enumerate(spec.curves):
            _add(c, 2, c.color or PALETTE[i % len(PALETTE)])
        if spec.consensus is not None:
            _add(spec.consensus, 4, spec.consensus.color or "#000000")

        if spec.reference_dose_gy is not None:
            fig.add_vline(x=spec.reference_dose_gy, line=dict(color="grey", dash="dot"))
            fig.add_hline(y=0.5, line=dict(color="grey", dash="dot", width=1))
        self._layout(fig, spec.title, spec.x_label, spec.y_label)
        fig.update_yaxes(range=[0, 1.02])
        return RenderedFigure(fig, self.name)

    def optimism(self, spec: OptimismSpec) -> RenderedFigure:
        import plotly.graph_objects as go

        labels = [r.label for r in spec.rows]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=[r.apparent for r in spec.rows],
                name="apparent",
                mode="lines+markers",
                line=dict(color=PALETTE[0], width=2),
                hovertemplate="apparent %{y:.3f}<extra>%{x}</extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=[r.cross_validated for r in spec.rows],
                name="cross-validated",
                mode="lines+markers",
                line=dict(color=PALETTE[1], width=2, dash="dash"),
                hovertemplate="CV %{y:.3f}<extra>%{x}</extra>",
            )
        )
        for r in spec.rows:  # optimism gap
            if np.isfinite(r.apparent) and np.isfinite(r.cross_validated):
                fig.add_shape(
                    type="line",
                    x0=r.label,
                    x1=r.label,
                    y0=r.cross_validated,
                    y1=r.apparent,
                    line=dict(color="grey", width=1),
                )
        if spec.chance_level is not None:
            fig.add_hline(y=spec.chance_level, line=dict(color="grey", dash="dot", width=1))
        self._layout(fig, spec.title, "", spec.y_label)
        return RenderedFigure(fig, self.name)
