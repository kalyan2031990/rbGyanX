#!/usr/bin/env python3
"""Assert that every place the release version appears agrees with the tag being built.

``engine/rbgyanx_engine/_version.py`` is the single source of truth; ``pyproject.toml``,
``CITATION.cff`` and ``VERSION.txt`` are supposed to agree with it, and the git tag is supposed to
agree with all four. A release whose artefacts are named after a version the code does not claim
is exactly the failure this guards against -- the v1.2.1 release shipped an asset labelled 1.1.0.

Lives here rather than inline in the release workflow because the inline form needed several
layers of shell and YAML quoting to extract a value from a Python file, which is unreadable and
was in fact wrong the first time it was written. This version is importable and unit-testable
(see ``tests/test_version_consistency.py``).

Usage:
    python scripts/check_release_version.py 1.3.0     # explicit
    python scripts/check_release_version.py v1.3.0    # leading v is stripped
    python scripts/check_release_version.py           # just report, no comparison
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def engine_version() -> str:
    """The single source of truth."""
    text = (ROOT / "engine" / "rbgyanx_engine" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r"""__version__\s*=\s*["']([^"']+)["']""", text)
    if not match:
        raise SystemExit("could not parse __version__ from engine/rbgyanx_engine/_version.py")
    return match.group(1)


def pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("could not parse version from pyproject.toml")
    return match.group(1)


def citation_version() -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"?([^"\n]+)', text, re.M)
    if not match:
        raise SystemExit("could not parse version from CITATION.cff")
    return match.group(1).strip().strip('"')


def version_txt_version() -> str:
    text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    match = re.search(r"(\d+\.\d+\.\d+)", text)
    if not match:
        raise SystemExit("could not parse a semantic version from VERSION.txt")
    return match.group(1)


def collect() -> dict[str, str]:
    """Every declared version, by source."""
    return {
        "engine/rbgyanx_engine/_version.py": engine_version(),
        "pyproject.toml": pyproject_version(),
        "CITATION.cff": citation_version(),
        "VERSION.txt": version_txt_version(),
    }


def main(argv: list[str]) -> int:
    declared = collect()
    width = max(len(k) for k in declared)
    for source, value in declared.items():
        print(f"  {source:<{width}}  {value}")

    distinct = set(declared.values())
    if len(distinct) != 1:
        print(f"\nERROR: the declared versions disagree: {sorted(distinct)}", file=sys.stderr)
        return 1

    declared_version = distinct.pop()

    if len(argv) < 2:
        print(f"\nall sources agree: {declared_version} (no tag supplied, nothing compared)")
        return 0

    tag_version = argv[1].lstrip("vV")
    if tag_version != declared_version:
        print(
            f"\nERROR: tag version {tag_version!r} does not match the declared version "
            f"{declared_version!r}. Refusing to build a release whose artefacts would be named "
            f"after a version the code does not claim.",
            file=sys.stderr,
        )
        return 1

    print(f"\nall sources agree with tag: {declared_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
