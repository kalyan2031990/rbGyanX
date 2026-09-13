"""Build-time check: TensorFlow import before PyInstaller (fail fast)."""
import sys

if sys.version_info >= (3, 13):
    raise SystemExit(
        "TensorFlow cannot be bundled on Python 3.13+. Use py -3.10 for -IncludeTensorFlow builds."
    )

import tensorflow as tf  # noqa: F401

try:
    from importlib.metadata import version as pkg_version

    ver = pkg_version("tensorflow")
except Exception:
    ver = getattr(tf, "__version__", None) or "unknown"
print(f"tensorflow OK ({ver})")
