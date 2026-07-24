"""
On-board visualisation — one API, swappable engines (v2 Phase 4 · Slice 2).

    from rbgyanx.viz import get_backend, DVHSpec, DVHCurve

    fig = get_backend("plotly").dvh(spec)      # interactive (Qt / HTML)
    fig = get_backend("matplotlib").dvh(spec)  # publication (PNG/PDF)

Both backends render identical *data* because the numbers live in the specs
(:mod:`rbgyanx.viz.spec`), not in the plotting code.

Engine pattern adapted from Düzenli et al., *SoftwareX* 2026, 102773 (multi-engine rendering
behind a single visualisation interface).
"""

from __future__ import annotations

from rbgyanx.viz.base import RenderedFigure, VizBackend
from rbgyanx.viz.spec import (
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
)

__all__ = [
    "get_backend",
    "available_backends",
    "VizBackend",
    "RenderedFigure",
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

#: name -> "why you'd pick it"
_BACKENDS = {
    "plotly": "interactive (hover/zoom/toggle); embedded in Qt, exportable as HTML",
    "matplotlib": "publication-ready static figures (PNG/PDF/SVG)",
}


def available_backends() -> dict[str, str]:
    """Backends whose plotting library is importable, with their intended use."""
    import importlib.util

    return {
        name: why for name, why in _BACKENDS.items() if importlib.util.find_spec(name) is not None
    }


def get_backend(name: str = "matplotlib", **kwargs) -> VizBackend:
    """Instantiate a rendering backend by name.

    Raises a clear error naming the installable package if the engine is missing, rather than
    surfacing a bare ImportError from deep inside a plot call.
    """
    key = (name or "").strip().lower()
    if key not in _BACKENDS:
        raise ValueError(f"unknown viz backend {name!r}; available: {sorted(_BACKENDS)}")
    try:
        if key == "plotly":
            from rbgyanx.viz.plotly_backend import PlotlyBackend

            return PlotlyBackend(**kwargs)
        from rbgyanx.viz.matplotlib_backend import MatplotlibBackend

        return MatplotlibBackend(**kwargs)
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            f"viz backend {key!r} needs the '{key}' package: pip install {key}"
        ) from exc
