"""
The visualisation interface (v2 Phase 4 · Slice 2).

One API, swappable engines — the pattern from Düzenli et al., *SoftwareX* **2026**, 102773:

    Plotly      -> INTERACTIVE views (embedded in the Qt app via QWebEngineView)
    Matplotlib  -> PUBLICATION figures (the manuscript's static panels)

Callers ask for a backend by name and render a spec; they never import a plotting library
directly. That keeps the Qt app, the CLI and the paper pipeline on one code path, and makes
adding an engine (e.g. Graphviz for flow diagrams) a backend, not a rewrite.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rbgyanx.viz.spec import (
    CohortFlowSpec,
    DoseResponseSpec,
    DVHSpec,
    OptimismSpec,
    SankeySpec,
)

__all__ = ["VizBackend", "RenderedFigure"]


class RenderedFigure:
    """A backend-native figure plus a uniform way to persist it.

    ``figure`` is the raw object (a ``plotly.graph_objects.Figure`` or a
    ``matplotlib.figure.Figure``) so advanced callers keep full control; everything routine
    goes through ``save`` / ``to_html``.
    """

    def __init__(self, figure: Any, backend: str) -> None:
        self.figure = figure
        self.backend = backend

    def save(self, path: str | Path, **kwargs: Any) -> Path:
        """Write the figure to disk (format inferred from the suffix)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.backend == "plotly":
            if path.suffix.lower() in {".html", ".htm"}:
                self.figure.write_html(str(path), include_plotlyjs="cdn", **kwargs)
            else:
                self.figure.write_image(str(path), **kwargs)  # needs kaleido
        else:
            self.figure.savefig(
                str(path),
                dpi=kwargs.pop("dpi", 150),
                bbox_inches=kwargs.pop("bbox_inches", "tight"),
                **kwargs,
            )
        return path

    def to_html(self, *, full_page: bool = True) -> str:
        """Standalone interactive HTML (Plotly), for embedding or the supplement.

        Matplotlib figures are returned as a base64 <img> so the same call works everywhere.
        """
        if self.backend == "plotly":
            return self.figure.to_html(include_plotlyjs="cdn", full_html=full_page)
        import base64
        import io

        buf = io.BytesIO()
        self.figure.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        img = f'<img alt="figure" src="data:image/png;base64,{b64}"/>'
        return f"<!doctype html><meta charset='utf-8'><body>{img}</body>" if full_page else img


class VizBackend(ABC):
    """Every backend renders the same specs."""

    name: str = "abstract"
    interactive: bool = False

    @abstractmethod
    def dvh(self, spec: DVHSpec) -> RenderedFigure:
        """Dose-volume histogram."""

    @abstractmethod
    def dose_response(self, spec: DoseResponseSpec) -> RenderedFigure:
        """Multi-model dose-response with Monte-Carlo bands and consensus overlay."""

    @abstractmethod
    def optimism(self, spec: OptimismSpec) -> RenderedFigure:
        """Apparent vs cross-validated performance."""

    @abstractmethod
    def sankey(self, spec: SankeySpec) -> RenderedFigure:
        """dose -> per-OAR NTCP -> uncomplicated control (P+)."""

    @abstractmethod
    def cohort_flow(self, spec: CohortFlowSpec) -> RenderedFigure:
        """PRISMA-style inclusion flow with exclusion reasons."""

    def render(
        self,
        spec: DVHSpec | DoseResponseSpec | OptimismSpec | SankeySpec | CohortFlowSpec,
    ) -> RenderedFigure:
        """Dispatch on spec type, so callers can stay generic."""
        if isinstance(spec, DVHSpec):
            return self.dvh(spec)
        if isinstance(spec, DoseResponseSpec):
            return self.dose_response(spec)
        if isinstance(spec, OptimismSpec):
            return self.optimism(spec)
        if isinstance(spec, SankeySpec):
            return self.sankey(spec)
        if isinstance(spec, CohortFlowSpec):
            return self.cohort_flow(spec)
        raise TypeError(f"unsupported spec type: {type(spec).__name__}")
