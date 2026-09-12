"""All surfaced version strings must match engine __version__."""

from __future__ import annotations

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


def test_version_single_source_of_truth():
    from rbgyanx_engine import __version__ as engine_ver

    # Hand-pinned so a release has to state its version here deliberately. This test is the
    # only thing that checks the engine version at all - pre_publish_check.py looks at
    # pyproject, CITATION.cff and VERSION.txt, but not at rbgyanx_engine.__version__, which
    # is what the other three are supposed to agree WITH.
    assert engine_ver == "1.3.0"
    assert _read_version_txt() == engine_ver
    assert _read_citation_cff() == engine_ver
    assert _read_pyproject() == engine_ver

    import rbgyanx

    assert rbgyanx.__version__ == engine_ver


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
        "docs/MANUSCRIPT_EVIDENCE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
    ],
)
def test_documents_quote_the_real_analytic_control_count(relative_path: str):
    """Every document that states the count must state the same, correct one.

    Scoped to documents describing the current state. CHANGELOG.md entries and
    analysis/preregistration_B.md are historical records of what was true at the time and are
    deliberately not rewritten.
    """
    expected = _collected_positive_controls()
    text = (ROOT / relative_path).read_text(encoding="utf-8")

    # Both orders occur in these documents: "22 analytic positive controls" (README) and
    # "Cohort-independent analytic positive controls (22)" (MANUSCRIPT_EVIDENCE).
    before = re.findall(r"(\d+)\s+(?:\*\*)?(?:analytic|positive)[ \w-]*control", text, re.I)
    after = re.findall(r"(?:analytic|positive)[ \w-]*controls?\s*\((\d+)", text, re.I)
    counts = {int(m) for m in (*before, *after)}
    assert counts, f"{relative_path} no longer states an analytic control count"
    assert counts == {expected}, (
        f"{relative_path} states {sorted(counts)} analytic controls; the suite collects {expected}"
    )
