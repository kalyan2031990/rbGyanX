"""rbgyanx-engine — open-source TCP/NTCP radiobiology core for rbGyanX CDSS."""

from ._version import __version__

from rbgyanx_engine.engine import run_analysis
from rbgyanx_engine.run_config import EngineResult, RunConfig

__all__ = ["RunConfig", "EngineResult", "run_analysis", "__version__"]
