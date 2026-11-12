"""All surfaced version strings must match engine __version__."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read_version_txt() -> str:
    text = (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    m = re.search(r"(\d+\.\d+\.\d+)", text)
    assert m, "VERSION.txt must contain semver"
    return m.group(1)


def _read_citation_cff() -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = re.search(r'^version:\s*["\']?([^"\'\n]+)', text, re.M)
    assert m, "CITATION.cff must contain version:"
    return m.group(1).strip('"')


def _read_pyproject() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*["\']([^"\']+)', text, re.M)
    assert m
    return m.group(1)


def _read_feature_registry() -> str:
    """``app_info.version``, which the GUI surfaces to the user.

    Added for v1.5.0. This was a sixth declared version that neither this test nor
    ``scripts/check_release_version.py`` read, so it could drift from the source of truth and a
    release would still build. Its 1.4.0 value was correct only because someone edited it by hand.
    """
    data = json.loads((ROOT / "core" / "feature_registry.json").read_text(encoding="utf-8"))
    return str(data["app_info"]["version"])


def test_version_single_source_of_truth():
    from rbgyanx_engine import __version__ as engine_ver

    # Hand-pinned so a release has to state its version here deliberately. This test is the
    # only thing that checks the engine version at all - pre_publish_check.py looks at
    # pyproject, CITATION.cff and VERSION.txt, but not at rbgyanx_engine.__version__, which
    # is what the other three are supposed to agree WITH.
    assert engine_ver == "1.5.1"
    assert _read_version_txt() == engine_ver
    assert _read_citation_cff() == engine_ver
    assert _read_pyproject() == engine_ver
    assert _read_feature_registry() == engine_ver

    import rbgyanx

    assert rbgyanx.__version__ == engine_ver


def test_citation_release_date_matches_the_changelog_entry():
    """CITATION.cff's `date-released` must be this version's date, not the previous one.

    It said 2026-10-17 -- v1.4.0's release date -- beside `version: "1.5.0"`. Nothing asserted on
    it, which is the same gap that let a "1.3.0" string ship in v1.4.0.
    """
    import re as _re

    from rbgyanx_engine import __version__ as engine_ver

    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = _re.search(r"^date-released:\s*\"?(\d{4}-\d{2}-\d{2})", cff, _re.M)
    assert m, "CITATION.cff must carry a date-released"
    cff_date = m.group(1)

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = _re.search(
        rf"^## \[{_re.escape(engine_ver)}\]\s*-\s*(\d{{4}}-\d{{2}}-\d{{2}})",
        changelog, _re.M,
    )
    assert entry, f"CHANGELOG.md has no dated entry for {engine_ver}"
    assert cff_date == entry.group(1), (
        f"CITATION.cff date-released is {cff_date} but CHANGELOG dates {engine_ver} "
        f"at {entry.group(1)}"
    )


# --------------------------------------------------------- version strings in the docs
#
# The five declaration sites above are what `scripts/check_release_version.py` gates a release on.
# They are not where versions actually go stale. v1.4.0 shipped with a "1.3.0" string, and v1.5.0
# was about to ship a README whose install command named `rbgyanx_engine-1.4.0-py3-none-any.whl`
# -- a command that fails with file-not-found for anyone who copies it. Neither was caught, because
# nothing asserted on prose.
#
# These tests close the class rather than the instance.


# CHANGELOG.md is excluded by instruction: historical version numbers are the point of it.
# VERSION.txt likewise carries the rationale for earlier releases on purpose.
DOC_EXCLUDE = {
    "CHANGELOG.md",
    "VERSION.txt",
}
DOC_EXCLUDE_DIRS = ("docs/archive/", "legacy/", ".tmp/")

# A distribution artefact with a version baked into its name.
ARTEFACT_RE = re.compile(
    r"""(?ix)
    \b(
        rbgyanx(?:_engine)?-\d+\.\d+\.\d+[^\s`'"]*\.whl      # wheels
      | rbgyanx[\w.-]*-\d+\.\d+\.\d+[^\s`'"]*\.(?:tar\.gz|zip|exe)  # sdists, installers
      | rbGyanX-\d+\.\d+\.\d+-Qt-Setup\.exe                   # the Windows installer
    )\b
    """
)

# A bare "x.y.z" that claims to be THIS project's version, as opposed to a dependency pin, a
# citation of an older release, or a DOI. Only the forms that assert the current version.
CLAIMS_VERSION_RE = re.compile(
    r"""(?ix)
    (?:
        rbGyanX\s+(?:version\s+)?v?(\d+\.\d+\.\d+)
      | ^\s*version\s*[:=]\s*"?v?(\d+\.\d+\.\d+)
    )
    """,
    re.M,
)


def _doc_files() -> list[Path]:
    """Tracked Markdown only.

    `git ls-files`, not a filesystem glob: the working tree also holds gitignored scratch -- local
    runbooks, notes, drafts -- which is nobody's business and does not ship. Scanning the tree
    made this test fail on files that are deliberately not in the repository, which is exactly the
    false positive that teaches people to ignore a test.
    """
    import subprocess

    listed = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    out: list[Path] = []
    for rel in listed:
        if rel in DOC_EXCLUDE or rel.startswith(DOC_EXCLUDE_DIRS):
            continue
        p = ROOT / rel
        if p.is_file():
            out.append(p)
    return sorted(out)


def test_the_doc_sweep_actually_finds_documents():
    """Guard the guard: a glob that matches nothing would make both tests below vacuous."""
    files = _doc_files()
    assert len(files) >= 5, f"only {len(files)} documents found: {[f.name for f in files]}"
    assert any(f.name == "README.md" for f in files)


def test_no_hardcoded_wheel_or_installer_name_in_the_docs():
    """A file name with a version in it is stale the moment the next release is cut.

    Write `rbgyanx_engine-*.whl`, or link to the release page. This is the specific thing that
    left the README advertising a wheel two versions old.
    """
    offenders: list[str] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            # An exception has to be written down on the line itself. A reference to one
            # specific past release asset is legitimate -- that file exists, under that name,
            # on that release -- but it must be a deliberate annotation someone can see and
            # review, not a silent exclusion in this test.
            if "pinned-asset: historical" in line:
                continue
            for match in ARTEFACT_RE.finditer(line):
                offenders.append(
                    f"{path.relative_to(ROOT).as_posix()}:{lineno}: {match.group(0)}"
                )
    assert not offenders, (
        "hard-coded distribution artefact name(s) in the documentation:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse a wildcard (rbgyanx_engine-*.whl) or link to the release page."
    )


def test_every_version_claim_in_the_docs_matches_the_engine():
    """Any text asserting rbGyanX's version must assert the current one."""
    from rbgyanx_engine import __version__ as engine_ver

    offenders: list[str] = []
    for path in _doc_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            # A line about an older release on purpose says so; those read "at the v1.4.0 tag",
            # "removed in v1.5.0", "through v1.2.1" and so on, and are not version claims.
            if re.search(r"(?i)\b(tag|removed|through|until|since|earlier|previous|was|"
                         r"superseded|history|historical|deposited)\b", line):
                continue
            for match in CLAIMS_VERSION_RE.finditer(line):
                found = match.group(1) or match.group(2)
                if found and found != engine_ver:
                    offenders.append(
                        f"{path.relative_to(ROOT).as_posix()}:{lineno}: claims {found}, "
                        f"engine is {engine_ver}"
                    )
    assert not offenders, (
        "stale version claim(s) in the documentation:\n  " + "\n  ".join(offenders)
    )


# --------------------------------------------------------- analytic control count


def _collected_positive_controls() -> int:
    """The number of analytic positive controls, computed from the test module itself.

    A "control" is one collected test case, not one ``def``. Three of the functions in
    tests/test_ntcp_positive_controls.py are parametrised -- four TD50 values for probit, four
    for log-logistic, five seriality values for relative seriality -- so twelve functions expand
    to twenty-two independent checks. Counting ``def test_`` lines gives twelve and counting
    collected cases gives twenty-two; both are accurate about different things, which is how the
    documentation came to look self-contradictory.

    Computed rather than hardcoded so that adding a parametrise case updates the expected number
    and forces the documents to be updated with it.
    """
    import ast

    source = (ROOT / "tests" / "test_ntcp_positive_controls.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    total = 0
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        cases = 1
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = decorator.func
            name = getattr(target, "attr", None) or getattr(target, "id", None)
            if name != "parametrize" or len(decorator.args) < 2:
                continue
            values = decorator.args[1]
            if isinstance(values, (ast.List, ast.Tuple)):
                cases *= len(values.elts)
        total += cases
    return total


def test_analytic_control_count_is_twenty_two():
    """Pin the number the documents quote, so 12-vs-22 cannot resurface."""
    assert _collected_positive_controls() == 22


@pytest.mark.parametrize(
    "relative_path",
    [
        "README.md",
        "docs/AI_ASSISTANT_DESIGN.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ],
)
def test_documents_quote_the_real_analytic_control_count(relative_path: str):
    """Every document that states the count must state the same, correct one.

    Scoped to documents describing the current state. CHANGELOG.md entries are historical
    records of what was true at the time and are deliberately not rewritten.
    """
    expected = _collected_positive_controls()
    text = (ROOT / relative_path).read_text(encoding="utf-8")

    # Both orders occur in these documents: "22 analytic positive controls" and
    # "analytic positive controls (22)".
    before = re.findall(r"(\d+)\s+(?:\*\*)?(?:analytic|positive)[ \w-]*control", text, re.I)
    after = re.findall(r"(?:analytic|positive)[ \w-]*controls?\s*\((\d+)", text, re.I)
    counts = {int(m) for m in (*before, *after)}
    assert counts, f"{relative_path} no longer states an analytic control count"
    assert counts == {expected}, (
        f"{relative_path} states {sorted(counts)} analytic controls; the suite collects {expected}"
    )


# ------------------------------------------------- the release version gate


def test_release_version_script_agrees_with_the_code():
    """scripts/check_release_version.py is what the release workflow trusts.

    It gates every release artefact, so if it cannot read the version files it silently stops
    protecting anything. Exercised here so a change to any of those file formats fails in the
    test suite rather than at tag time.
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import check_release_version as crv
    finally:
        sys.path.pop(0)

    declared = crv.collect()
    assert len(set(declared.values())) == 1, f"version sources disagree: {declared}"

    from rbgyanx_engine import __version__ as engine_ver

    assert set(declared.values()) == {engine_ver}

    # The gate must accept the real version, with or without the tag's leading "v" ...
    assert crv.main(["check_release_version.py", engine_ver]) == 0
    assert crv.main(["check_release_version.py", f"v{engine_ver}"]) == 0
    # ... and reject anything else.
    assert crv.main(["check_release_version.py", "0.0.1"]) == 1
