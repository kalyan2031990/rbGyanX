"""
The read-only tools: read_code, read_error, run_tests, run_synthetic, explain_run.

Each declares the capability it needs; the registry refuses before the function is entered, so
nothing here re-checks the matrix. What these functions *do* enforce is the part the matrix
cannot express: which paths are legitimate, which pytest selectors are legitimate, and which
fields of a run summary are patient-level.

Two constraints run through all of them:

  * Nothing here computes, adjusts or influences a TCP/NTCP/UTCP value. ``explain_run`` reads a
    result the deterministic engine already produced and formats it. There is no path from this
    module into the numeric core.
  * Anything bound for a remote provider goes through :mod:`rbgyanx.ai.scrubber` and is refused
    if it cannot be confidently cleaned.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from rbgyanx.ai.capability import Capability
from rbgyanx.ai.scrubber import (
    ScrubRefused,
    install_root,
    scrub,
    scrub_for_transmission,
    scrub_traceback,
)
from rbgyanx.ai.tools.paths import PathRefused, is_within, relative_label, resolve_within
from rbgyanx.ai.tools.registry import Tool, ToolContext, ToolResult, register

__all__ = ["read_code", "read_error", "run_tests", "run_synthetic", "explain_run"]

#: Refuse to read a file large enough to be data rather than source.
MAX_READ_BYTES = 256 * 1024

#: How long a test run may take before it is killed.
TEST_TIMEOUT_SECONDS = 900


# --------------------------------------------------------------------------- read_code


def read_code(ctx: ToolContext, *, path: str) -> ToolResult:
    """Read one source file, by a path relative to the install tree."""
    root = install_root()
    try:
        target = resolve_within(root, path)
    except PathRefused as exc:
        return ToolResult.refused("read_code", Capability.READ_CODE.value, str(exc))

    try:
        size = target.stat().st_size
    except OSError as exc:  # pragma: no cover - defensive
        return ToolResult.refused("read_code", Capability.READ_CODE.value, str(exc))
    if size > MAX_READ_BYTES:
        return ToolResult.refused(
            "read_code",
            Capability.READ_CODE.value,
            f"refusing {path!r}: {size} bytes exceeds the {MAX_READ_BYTES}-byte source limit",
        )

    text = target.read_text(encoding="utf-8", errors="replace")
    label = relative_label(root, target)

    # Source in our own tree is software, not data, but it is still scrubbed for a remote
    # provider: a checked-in fixture or a stray comment can carry an identifier.
    if ctx.remote:
        try:
            text = scrub_for_transmission(text, remote=True)
        except ScrubRefused as exc:
            return ToolResult.refused("read_code", Capability.READ_CODE.value, str(exc))

    return ToolResult(
        ok=True,
        tool="read_code",
        capability=Capability.READ_CODE.value,
        output=text,
        metadata={"path": label, "bytes": size},
    )


# -------------------------------------------------------------------------- read_error


def read_error(ctx: ToolContext, *, traceback: str) -> ToolResult:
    """Read a traceback. Scrubbed for a remote provider, raw for a local one."""
    if not ctx.remote:
        return ToolResult(
            ok=True,
            tool="read_error",
            capability=Capability.READ_ERROR.value,
            output=traceback,
            metadata={"scrubbed": False},
        )

    try:
        cleaned = scrub_for_transmission(traceback, remote=True, traceback=True)
    except ScrubRefused as exc:
        return ToolResult.refused("read_error", Capability.READ_ERROR.value, str(exc))

    result = scrub_traceback(traceback)
    return ToolResult(
        ok=True,
        tool="read_error",
        capability=Capability.READ_ERROR.value,
        output=cleaned,
        findings_redacted=len(result.findings),
        metadata={"scrubbed": True},
    )


# --------------------------------------------------------------------------- run_tests


#: A pytest node id: a path, optionally with ``::class::function`` and a parametrisation id.
_SELECTOR_OK = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*(::[A-Za-z0-9_\-\[\]. ]+)*$")


def _validate_selector(selector: str) -> str:
    """Reject anything that is not a plain node id.

    A pytest selector is passed to a subprocess argv, where ``-p``, ``-c``, ``--rootdir`` and
    ``--pdb`` all change what code runs - ``-p`` loads an arbitrary plugin, and ``-c`` points at
    a config that can name one. So the selector is validated as data, never accepted as a flag.
    """
    text = str(selector).strip()
    if not text:
        raise ValueError("empty test selector")
    if text.startswith("-"):
        raise ValueError(f"refusing selector {selector!r}: options are not accepted, only node ids")
    if not _SELECTOR_OK.match(text):
        raise ValueError(
            f"refusing selector {selector!r}: expected a path or path::node id, "
            "with no shell metacharacters"
        )
    if ".." in text.split("::")[0].split("/"):
        raise ValueError(f"refusing selector {selector!r}: path traversal is not accepted")
    return text


def run_tests(ctx: ToolContext, *, selector: str = "tests") -> ToolResult:
    """Run pytest on a validated selector and return its output."""
    root = install_root()
    try:
        node = _validate_selector(selector)
    except ValueError as exc:
        return ToolResult.refused("run_tests", Capability.RUN_TESTS.value, str(exc))

    path_part = node.split("::")[0]
    target = (root / path_part).resolve()
    if not is_within(root, target):
        return ToolResult.refused(
            "run_tests",
            Capability.RUN_TESTS.value,
            f"refusing selector {selector!r}: it resolves outside the install tree",
        )
    if not target.exists():
        return ToolResult.refused(
            "run_tests",
            Capability.RUN_TESTS.value,
            f"refusing selector {selector!r}: no such test path",
        )

    argv = [sys.executable, "-m", "pytest", node, "-p", "no:randomly", "--no-header", "-q"]
    try:
        completed = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult.refused(
            "run_tests",
            Capability.RUN_TESTS.value,
            f"the test run exceeded {TEST_TIMEOUT_SECONDS}s and was stopped",
        )

    output = (completed.stdout or "") + (completed.stderr or "")
    findings = 0
    if ctx.remote:
        try:
            output = scrub_for_transmission(output, remote=True, traceback=True)
        except ScrubRefused as exc:
            return ToolResult.refused("run_tests", Capability.RUN_TESTS.value, str(exc))
        findings = len(scrub(output).findings)

    return ToolResult(
        ok=True,
        tool="run_tests",
        capability=Capability.RUN_TESTS.value,
        output=output,
        findings_redacted=findings,
        metadata={"selector": node, "returncode": completed.returncode},
    )


# ----------------------------------------------------------------------- run_synthetic


def _declared_synthetic_roots(ctx: ToolContext) -> list[Path]:
    """``examples/data`` plus any directory the user has explicitly declared synthetic."""
    roots = [install_root() / "examples" / "data"]
    roots.extend(Path(p) for p in ctx.synthetic_roots)
    return roots


def run_synthetic(ctx: ToolContext, *, input_path: str) -> ToolResult:
    """Run against synthetic data only.

    The check is an allow-list of declared synthetic directories, not a deny-list of known
    patient directories. A path is refused unless it is provably inside somewhere the user has
    said is synthetic - so an undeclared directory is refused whether or not it holds real data,
    and regardless of which provider is selected.
    """
    candidate = Path(input_path)
    roots = _declared_synthetic_roots(ctx)

    if not any(is_within(root, candidate) for root in roots):
        declared = ", ".join(str(r) for r in roots)
        return ToolResult.refused(
            "run_synthetic",
            Capability.RUN_SYNTHETIC.value,
            f"refusing {input_path!r}: it is not inside a declared synthetic directory "
            f"({declared}). Declare the directory as synthetic first; this tool never runs "
            "against real patient data, for any provider.",
        )

    if not candidate.exists():
        return ToolResult.refused(
            "run_synthetic",
            Capability.RUN_SYNTHETIC.value,
            f"refusing {input_path!r}: no such directory",
        )

    files = (
        sorted(p.name for p in candidate.iterdir() if p.is_file())[:50]
        if candidate.is_dir()
        else [candidate.name]
    )
    return ToolResult(
        ok=True,
        tool="run_synthetic",
        capability=Capability.RUN_SYNTHETIC.value,
        output="\n".join(files),
        metadata={"input_path": str(candidate), "n_files": len(files)},
    )


# ------------------------------------------------------------------------- explain_run


def explain_run(ctx: ToolContext, *, result, include_patient_level: bool = False) -> ToolResult:
    """Summarise a completed run for the assistant to explain.

    Wraps :func:`rbgyanx.ai.context.summarise_run`. Patient-level detail is gated on the
    capability, so asking for it on a remote provider yields the aggregate summary and says so
    rather than silently returning less than was asked for.
    """
    from rbgyanx.ai.capability import is_allowed
    from rbgyanx.ai.context import summarise_run

    patient_level_granted = is_allowed(
        Capability.EXPLAIN_PATIENT_LEVEL,
        ctx.provider,
        ctx.install_type,
        base_url=ctx.base_url,
        env=ctx.env,
    )
    wanted = bool(include_patient_level)
    granted = wanted and patient_level_granted.allowed

    text = summarise_run(result, include_patient_level=granted)

    note = ""
    if wanted and not granted:
        note = f"patient-level detail withheld: {patient_level_granted.reason}"

    if ctx.remote and text:
        try:
            text = scrub_for_transmission(text, remote=True)
        except ScrubRefused as exc:
            return ToolResult.refused("explain_run", Capability.EXPLAIN_AGGREGATE.value, str(exc))

    return ToolResult(
        ok=True,
        tool="explain_run",
        capability=Capability.EXPLAIN_AGGREGATE.value,
        output=text,
        reason=note,
        metadata={"patient_level": granted, "patient_level_requested": wanted},
    )


# --------------------------------------------------------------------------- registration

register(
    Tool(
        name="read_code",
        capability=Capability.READ_CODE,
        func=read_code,
        description="Read one source file, by a path relative to the install tree.",
    )
)
register(
    Tool(
        name="read_error",
        capability=Capability.READ_ERROR,
        func=read_error,
        description="Read a traceback; scrubbed for remote providers, raw for local ones.",
    )
)
register(
    Tool(
        name="run_tests",
        capability=Capability.RUN_TESTS,
        func=run_tests,
        description="Run pytest on a validated node id and return its output.",
    )
)
register(
    Tool(
        name="run_synthetic",
        capability=Capability.RUN_SYNTHETIC,
        func=run_synthetic,
        description="Run against a declared synthetic data directory only.",
        touches_patient_data=False,
    )
)
register(
    Tool(
        name="explain_run",
        capability=Capability.EXPLAIN_AGGREGATE,
        func=explain_run,
        description="Summarise a completed run; patient-level fields gated on capability.",
    )
)
