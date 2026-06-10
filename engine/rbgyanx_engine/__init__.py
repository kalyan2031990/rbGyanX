"""rbgyanx-engine — open-source TCP/NTCP radiobiology core for rbGyanX CDSS."""

__version__ = "1.0.0"

from rbgyanx_engine.engine import run_analysis
from rbgyanx_engine.run_config import EngineResult, RunConfig

__all__ = ["RunConfig", "EngineResult", "run_analysis", "__version__"]
