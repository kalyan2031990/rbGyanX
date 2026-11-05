"""Every relative Markdown link in the repository must resolve to a file that exists (defect #55).

Defect #55: the v1.5.0 scope cleanup removed 69 paths and left references to them behind. Most were
prose pointers, but two were live Markdown links in `README.md`'s documentation table
(`analysis/README.md` and `docs/DOSIOMICS_DATA_PROVENANCE.md`), so the repository's front page
offered a reader two links that went nowhere. Others were pointers inside module docstrings and two
strings printed at run time by `scripts/make_run_report.py` and `scripts/build_zenodo_bundle.ps1`.

Only the link case can be checked mechanically. Prose that *names* a removed path is not
distinguishable by a regex from prose that names it in order to say it is absent -- which is exactly
what the corrected text does, deliberately, so a reader looking for the analysis record is told
where it went rather than left to find a dead path. This test therefore pins the part that has an
objective answer: a link that claims to point at something in this repository must point at
something in this repository.

Fails on v1.4.0 only in the sense that the defect did not exist there (the targets were present);
it fails on the v1.5.0 tree as it stood before this fix, with the two README rows above.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# [text](target) -- target captured up to the closing paren or a whitespace-separated title.
LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "data:")

# Directories whose contents are historical records, not maintained documentation.
SKIP_DIRS = ("docs/archive/", "legacy/")


def _tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO_ROOT / rel for rel in out if not rel.startswith(SKIP_DIRS)]


def _broken_links(path: Path) -> list[tuple[int, str, str]]:
    broken: list[tuple[int, str, str]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in LINK.finditer(line):
            target = match.group("target")
            if target.startswith(SKIP_PREFIXES):
                continue
            # Strip an in-page anchor: docs/X.md#section -> docs/X.md
            bare = target.split("#", 1)[0]
            if not bare:
                continue
            resolved = (path.parent / bare).resolve()
            if not resolved.exists():
                broken.append((lineno, match.group("text"), target))
    return broken


def test_at_least_one_markdown_file_is_checked():
    """Guard the guard: a `git ls-files` that returns nothing would make this suite vacuous."""
    files = _tracked_markdown()
    assert len(files) >= 10, f"only {len(files)} markdown files found; the collection step is wrong"


@pytest.mark.parametrize("path", _tracked_markdown(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_relative_markdown_links_resolve(path: Path):
    """#55: no link may point at a path that is not in the repository."""
    broken = _broken_links(path)
    assert not broken, "broken relative links in {}:\n{}".format(
        path.relative_to(REPO_ROOT),
        "\n".join(f"  line {n}: [{text}]({target})" for n, text, target in broken),
    )
