"""Refuse to read DICOM through the obsolete ``dicom`` package instead of pydicom.

``dicompylercore.dicomparser`` guards its import like this::

    try:
        from pydicom.dicomio import read_file
    except ImportError:
        from dicom import read_file        # the 2017 "dicom" distribution

**pydicom 3 removed** ``pydicom.dicomio.read_file``, and no released version of dicompyler-core
(0.5.6 is the latest) has stopped importing it. So on an interpreter with pydicom >= 3 *and* the
obsolete ``dicom`` distribution installed, the ``try`` fails, the ``except`` succeeds, and every
DICOM read inside dicompyler-core goes through a library written for Python 2 that raises
``RuntimeError: generator raised StopIteration`` on Python 3.7+ (PEP 479).

The consequence is the dangerous kind: not an error at the top level, but **NaN everywhere** --
no dose grid is read, so no DVH is extracted, so every TCP and NTCP is NaN. A run completes and
writes a full output tree of nothing.

Both conditions are needed, which is why declaring ``pydicom<3`` is not enough on its own: this
project has declared that pin since v1.1.0, with a comment saying why, and the fault still
occurred on a developer machine whose pydicom was upgraded afterwards. A declaration constrains an
install; it cannot constrain an environment that has drifted. This module is the runtime check
that does.
"""

from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)

#: Reason code for a refused run.
OBSOLETE_DICOM_READER = "OBSOLETE_DICOM_READER"

_MESSAGE = """\
rbGyanX refuses to read DICOM: dicompyler-core has bound its reader to the obsolete 'dicom'
package instead of pydicom.

  dicompylercore.dicomparser.read_file resolves to : {module}
  pydicom version installed                        : {pydicom}
  dicompyler-core version installed                : {dicompylercore}

Why this happens: pydicom 3 removed pydicom.dicomio.read_file, which dicompyler-core still
imports, so its import guard falls back to the 'dicom' distribution published in 2017. That
library cannot read DICOM on Python 3.7 or later, and the failure is silent -- every dose grid
reads as nothing and every TCP and NTCP comes out NaN.

How to fix it, either way round:

  pip uninstall dicom              # remove the obsolete package; nothing current depends on it
  pip install "pydicom>=2.4,<3"    # the version dicompyler-core supports

rbGyanX declares pydicom>=2.4,<3 in its own requirements; this environment does not match them.
"""


@functools.lru_cache(maxsize=1)
def reader_diagnostics() -> dict:
    """What the DICOM reader actually resolved to, for the guard and for the run manifest."""
    info: dict = {
        "read_file_module": "",
        "pydicom": "",
        "dicompylercore": "",
        "is_pydicom": False,
        "error": "",
    }
    try:
        import pydicom

        info["pydicom"] = str(getattr(pydicom, "__version__", "?"))
    except Exception as exc:  # pragma: no cover - pydicom is a hard dependency
        info["error"] = f"pydicom unimportable: {exc}"
        return info
    try:
        import dicompylercore
        import dicompylercore.dicomparser as dicomparser

        info["dicompylercore"] = str(getattr(dicompylercore, "__version__", "?"))
        module = getattr(dicomparser.read_file, "__module__", "") or ""
        info["read_file_module"] = module
        info["is_pydicom"] = module.startswith("pydicom")
    except Exception as exc:
        info["error"] = f"dicompylercore unimportable: {exc}"
    return info


def assert_pydicom_reader() -> None:
    """Raise before any DICOM is read if the reader is not pydicom.

    Deliberately an exception rather than a warning or a NaN: a silent fallback here produces a
    complete run whose every radiobiological number is NaN, which is worse than a refusal.
    """
    info = reader_diagnostics()
    if info["is_pydicom"]:
        return
    if info["error"]:
        raise RuntimeError(
            f"rbGyanX cannot verify the DICOM reader ({OBSOLETE_DICOM_READER}): {info['error']}"
        )
    raise RuntimeError(
        _MESSAGE.format(
            module=info["read_file_module"] or "<unknown>",
            pydicom=info["pydicom"] or "<unknown>",
            dicompylercore=info["dicompylercore"] or "<unknown>",
        )
    )


def warn_if_not_pydicom() -> bool:
    """Log the same diagnosis without raising. Returns True when the reader is sound.

    For contexts that must not raise -- a GUI's start-up banner, a capability report -- where the
    operator still needs to be told before they trust a number.
    """
    info = reader_diagnostics()
    if info["is_pydicom"]:
        return True
    logger.error(
        "%s: dicompylercore.dicomparser.read_file resolves to %r (pydicom %s, "
        "dicompyler-core %s). Every DICOM read will fail and every TCP/NTCP will be NaN. "
        "Uninstall the obsolete 'dicom' package or install pydicom>=2.4,<3.",
        OBSOLETE_DICOM_READER,
        info["read_file_module"] or "<unknown>",
        info["pydicom"] or "<unknown>",
        info["dicompylercore"] or "<unknown>",
    )
    return False
