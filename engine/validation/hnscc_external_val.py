"""Deprecated: use :mod:`validation.external_validation_harness`.

The module was named for one public collection; the harness itself -- the four-tier evaluation and
the MCD/CCS consistency check against whatever outcome endpoint the dataset carries -- is general,
so it was renamed in v1.5.0. This shim re-exports the new names and will be removed in the release
after next.
"""

from __future__ import annotations

import warnings

from validation.external_validation_harness import (  # noqa: F401
    DISCLAIMER,
    build_external_validation_report,
    run_external_validation,
)

warnings.warn(
    "validation.hnscc_external_val is deprecated; use "
    "validation.external_validation_harness. run_hnscc_external_validation is now "
    "run_external_validation.",
    DeprecationWarning,
    stacklevel=2,
)

#: Former name, kept so existing imports keep working.
run_hnscc_external_validation = run_external_validation

__all__ = [
    "DISCLAIMER",
    "build_external_validation_report",
    "run_external_validation",
    "run_hnscc_external_validation",
]
