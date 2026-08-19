"""
Path containment for the tool layer.

Every tool that touches the filesystem resolves through :func:`resolve_within`, which answers one
question: does this path, after every trick has been undone, land inside the directory the caller
is allowed to touch?

The tricks that have to be undone, all of which have been used to escape a naive prefix check:

  ``../../``            traversal, including when spelled with mixed separators
  absolute paths        ``/etc/passwd``, ``C:\\Windows\\...``
  drive-relative paths  ``C:foo`` on Windows resolves against that drive's *current* directory
  UNC paths             ``\\\\server\\share`` is neither relative nor under any local root
  symlinks              a link inside the tree pointing outside it
  NTFS alternate data streams  ``file.py:hidden`` reads a different stream
  case                  Windows filesystems are case-insensitive, so a prefix compare on the
                        raw string is not a containment proof

The implementation resolves both sides with :meth:`Path.resolve` and compares resolved paths, so
containment is decided by the filesystem rather than by string shape. This module is FROZEN.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath, PureWindowsPath

__all__ = ["PathRefused", "resolve_within", "is_within", "relative_label"]


class PathRefused(ValueError):
    """Raised when a path cannot be shown to be inside the permitted root."""


#: Filenames that are never readable through the tool layer, wherever they sit in the tree.
_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        "_netrc",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secrets.yaml",
        "secrets.yml",
        ".pypirc",
        ".git-credentials",
    }
)

#: Extensions that carry keys or patient data rather than source.
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".pfx", ".p12", ".dcm", ".env"})

#: Directories that hold data, outputs or version-control internals rather than source.
_FORBIDDEN_DIRS = frozenset(
    {
        ".git",
        "test_data",
        "Outputs",
        "outputs",
        "_pseudonym_maps",
        "_private_maps",
        "release_assets",
        "backups",
        "reports",
        "external_validation",
        "__pycache__",
    }
)


def _looks_absolute_or_rooted(raw: str) -> bool:
    """True for anything that is not a plain relative path, on either platform's rules."""
    if not raw:
        return True
    text = raw.strip()
    if text.startswith(("/", "\\")):
        return True  # POSIX absolute, or a UNC / rooted Windows path
    # Windows drive forms: "C:\x", "C:/x" and the drive-relative "C:x".
    if PureWindowsPath(text).drive:
        return True
    return bool(PurePath(text).is_absolute())


def _has_alternate_data_stream(raw: str) -> bool:
    """``file.py:stream`` reads a different NTFS stream than ``file.py``."""
    tail = raw.replace("\\", "/").split("/")[-1]
    return ":" in tail


def is_within(root: Path, candidate: Path) -> bool:
    """True when ``candidate`` resolves inside ``root``. Both sides are resolved first."""
    try:
        root_resolved = root.resolve()
        candidate_resolved = candidate.resolve()
    except (OSError, RuntimeError):  # RuntimeError: symlink loop
        return False
    try:
        candidate_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def resolve_within(
    root: Path,
    relative: str,
    *,
    must_exist: bool = True,
    allow_sensitive: bool = False,
) -> Path:
    """Resolve ``relative`` against ``root``, or raise :class:`PathRefused`.

    ``relative`` must be a genuinely relative path. Absolute, drive-rooted and UNC paths are
    refused outright rather than being reinterpreted, because silently reinterpreting a path the
    caller wrote as absolute is how a containment check turns into a false sense of one.
    """
    raw = str(relative)

    if _looks_absolute_or_rooted(raw):
        raise PathRefused(
            f"refusing {raw!r}: only paths relative to the rbGyanX install tree are readable"
        )
    if _has_alternate_data_stream(raw):
        raise PathRefused(f"refusing {raw!r}: alternate data streams are not readable")
    if "\x00" in raw:
        raise PathRefused("refusing a path containing a null byte")

    try:
        candidate = (root / raw).resolve()
    except (OSError, RuntimeError) as exc:
        raise PathRefused(f"refusing {raw!r}: {exc}") from exc

    if not is_within(root, candidate):
        raise PathRefused(
            f"refusing {raw!r}: it resolves outside the install tree "
            "(traversal, or a symlink pointing out of it)"
        )

    parts = set(candidate.relative_to(root.resolve()).parts)
    forbidden = parts & _FORBIDDEN_DIRS
    if forbidden:
        raise PathRefused(
            f"refusing {raw!r}: {sorted(forbidden)[0]!r} holds data or VCS internals, not source"
        )

    if not allow_sensitive:
        if candidate.name in _SENSITIVE_NAMES or candidate.name.lower() in _SENSITIVE_NAMES:
            raise PathRefused(f"refusing {raw!r}: this file may hold credentials")
        if candidate.suffix.lower() in _SENSITIVE_SUFFIXES:
            raise PathRefused(
                f"refusing {raw!r}: {candidate.suffix} files may hold credentials or patient data"
            )

    if must_exist and not candidate.exists():
        raise PathRefused(f"refusing {raw!r}: no such file in the install tree")
    if must_exist and not candidate.is_file():
        raise PathRefused(f"refusing {raw!r}: not a regular file")

    return candidate


def relative_label(root: Path, candidate: Path) -> str:
    """A repo-relative, forward-slashed label safe to show or transmit."""
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):  # pragma: no cover - defensive
        return os.path.basename(str(candidate))
