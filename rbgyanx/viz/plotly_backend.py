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

    def sankey(self, spec) -> RenderedFigure:
        """Interactive Sankey: dose → per-OAR NTCP → uncomplicated control."""
        import plotly.graph_objects as go

        node_colours = [n.color or PALETTE[i % len(PALETTE)] for i, n in enumerate(spec.nodes)]
        fig = go.Figure(
            go.Sankey(
                node=dict(
                    label=[n.label for n in spec.nodes],
                    color=node_colours,
                    pad=18,
                    thickness=18,
                    line=dict(color="rgba(0,0,0,0.25)", width=0.5),
                ),
                link=dict(
                    source=[link.source for link in spec.links],
                    target=[link.target for link in spec.links],
                    value=[link.value for link in spec.links],
                    label=[link.label for link in spec.links],
                    color=[_rgba(node_colours[link.source], 0.35) for link in spec.links],
                ),
            )
        )
        fig.update_layout(
            title=dict(text=spec.title, font=dict(size=14)),
            template=self.template,
            height=self.height,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        return RenderedFigure(fig, self.name)

    def cohort_flow(self, spec) -> RenderedFigure:
        """Interactive PRISMA-style inclusion flow with exclusion reasons on hover."""
        import plotly.graph_objects as go

        labels = [s.label for s in spec.stages]
        counts = [s.n for s in spec.stages]
        hover = [
            (
                f"{s.label}<br>n = {s.n}"
                + (f"<br>excluded {s.excluded}: {s.exclusion_reason}" if s.excluded else "")
            )
            for s in spec.stages
        ]
        fig = go.Figure(
            go.Bar(
                x=counts,
                y=labels,
                orientation="h",
                marker=dict(color=PALETTE[0]),
                text=[f"n={c}" for c in counts],
                textposition="auto",
                hovertext=hover,
                hoverinfo="text",
            )
        )
        for i, s in enumerate(spec.stages):
            if s.excluded:
                fig.add_annotation(
                    x=counts[i],
                    y=labels[i],
                    text=f"−{s.excluded}: {s.exclusion_reason}",
                    showarrow=False,
                    xanchor="left",
                    xshift=8,
                    font=dict(size=10, color=PALETTE[1]),
                )
        fig.update_layout(
            title=dict(text=spec.title, font=dict(size=14)),
            xaxis_title="patients",
            template=self.template,
            height=self.height,
            margin=dict(l=180, r=180, t=50, b=40),
            yaxis=dict(autorange="reversed"),
        )
        return RenderedFigure(fig, self.name)

    def shap(self, spec) -> RenderedFigure:
        """Interactive mean-|SHAP| bar; colour encodes the average push direction."""
        import plotly.graph_objects as go

        feats = spec.sorted_features()
        names = [f.name for f in feats]
        vals = [f.mean_abs_shap for f in feats]
        # Blue = pushes model output down on average, red = up. Direction only, not causation.
        colours = [PALETTE[1] if f.mean_signed_shap >= 0 else PALETTE[0] for f in feats]
        hover = [
            f"{f.name}<br>mean |SHAP| = {f.mean_abs_shap:.4f}"
            f"<br>mean signed = {f.mean_signed_shap:+.4f}"
            for f in feats
        ]
        fig = go.Figure(
            go.Bar(
                x=vals,
                y=names,
                orientation="h",
                marker=dict(color=colours),
                text=[f"{v:.3f}" for v in vals],
                textposition="auto",
                hovertext=hover,
                hoverinfo="text",
            )
        )
        subtitle = spec.title
        if spec.n_samples:
            subtitle += f"  (n={spec.n_samples})"
        fig.update_layout(
            title=dict(text=subtitle, font=dict(size=14)),
            xaxis_title=spec.x_label,
            template=self.template,
            height=self.height,
            margin=dict(l=160, r=40, t=50, b=45),
            yaxis=dict(autorange="reversed"),
        )
        return RenderedFigure(fig, self.name)
