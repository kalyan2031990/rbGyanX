"""
rbGyanX - Radiobiological Analysis Platform
===========================================

A governed scientific framework for radiotherapy reasoning.

Version: 1.0.0 (Phase 1 - 3-Layer Architecture)
"""

# Re-exported deliberately: rbgyanx.__version__ must agree with the engine, which is the
# single source of truth (tests/test_version_consistency.py pins this). The redundant
# alias is the documented way to mark a re-export so it is not read as a stray import.
from rbgyanx_engine import __version__ as __version__

