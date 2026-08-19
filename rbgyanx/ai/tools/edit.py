"""
The write tool, and the boundary around it.

``edit_code`` is the only place the assistant can change a file, and it is wrapped in two
things that are not optional:

  THE FROZEN SET       - :func:`rbgyanx.ai.capability.frozen_reason` decides what may never be
                         touched, and lives in a frozen file so the list cannot be edited by the
                         thing it constrains. See the rationale in ``capability.py``.

  THE VERIFICATION LOOP - snapshot, apply, run the analytic positive controls, run the full
                         suite, and on ANY failure restore the snapshot automatically. The
                         restore is verified by hash: the tool reports the tree as reverted only
                         after confirming the bytes match what it saved.

Why the snapshot is file bytes rather than ``git stash``
--------------------------------------------------------
``git stash`` is repo-global. It would capture the user's own unrelated uncommitted work
alongside the agent's edit, and a conflicted ``stash pop`` leaves the tree neither in its
original state nor in the edited one - the precise opposite of the guarantee this loop exists to
provide. Worse, it fails differently depending on what the user happened to have in progress,
which is the last property you want in a safety mechanism. So the snapshot is the exact bytes of
the files this tool is about to touch, and the revert is a byte-for-byte restore. No git command
runs in the revert path at all.

Nothing is written silently: an edit must be reviewed as a diff and then confirmed.
"""

from __future__ import annotations

import difflib
import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rbgyanx.ai.capability import (
    Capability,
    _normalise,
    creation_reason,
    frozen_reason,
    is_allowed,
)
from rbgyanx.ai.scrubber import install_root
from rbgyanx.ai.tools.paths import PathRefused, relative_label, resolve_within
from rbgyanx.ai.tools.registry import Tool, ToolContext, ToolResult, register

__all__ = ["edit_code", "Snapshot", "POSITIVE_CONTROLS", "FULL_SUITE"]

#: The analytic positive controls: the fastest way to catch a changed number.
POSITIVE_CONTROLS = "tests/test_ntcp_positive_controls.py"

#: The whole suite. Slower, and run second, because the controls fail faster and more clearly.
FULL_SUITE = "tests"

VERIFY_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class Snapshot:
    """The exact bytes of one file before an edit, with the digest that proves a clean restore."""

    path: Path
    existed: bool
    content: bytes
    sha256: str

    @classmethod
    def take(cls, path: Path) -> Snapshot:
        if path.exists():
            content = path.read_bytes()
            return cls(path, True, content, hashlib.sha256(content).hexdigest())
        return cls(path, False, b"", hashlib.sha256(b"").hexdigest())

    def restore(self) -> bool:
        """Put the file back exactly as it was. Returns True when the bytes verify."""
        if not self.existed:
            try:
                if self.path.exists():
                    self.path.unlink()
                return not self.path.exists()
            except OSError:  # pragma: no cover - defensive
                return False
        try:
            self.path.write_bytes(self.content)
        except OSError:  # pragma: no cover - defensive
            return False
        return hashlib.sha256(self.path.read_bytes()).hexdigest() == self.sha256


def _run(selector: str, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", selector, "-p", "no:randomly", "--no-header", "-q"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=VERIFY_TIMEOUT_SECONDS,
        check=False,
    )


def _diff(old: str, new: str, label: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )


def edit_code(
    ctx: ToolContext,
    *,
    path: str,
    new_text: str,
    confirm: bool = False,
    controls: str = POSITIVE_CONTROLS,
    suite: str = FULL_SUITE,
) -> ToolResult:
    """Propose, and on confirmation apply, one edit to a non-frozen source file.

    Called without ``confirm`` it returns the unified diff and changes nothing - the review step
    is the default, not an option. With ``confirm=True`` it snapshots, applies, verifies and
    reverts automatically on any failure.
    """
    # The registry checks this before the tool is entered. Re-checking here costs nothing
    # and closes the path where something imports edit_code directly.
    decision = is_allowed(
        Capability.MODIFY_CODE,
        ctx.provider,
        ctx.install_type,
        base_url=ctx.base_url,
        env=ctx.env,
    )
    if not decision.allowed:
        return ToolResult.refused("edit_code", Capability.MODIFY_CODE.value, decision.reason)

    root = install_root()
    label = _normalise(str(path))

    # 1. The frozen set, before anything is read or written.
    reason = frozen_reason(label)
    if reason:
        return ToolResult.refused("edit_code", Capability.MODIFY_CODE.value, reason)

    target = root / label
    creating = not target.exists()
    if creating:
        reason = creation_reason(label)
        if reason:
            return ToolResult.refused("edit_code", Capability.MODIFY_CODE.value, reason)

    # 2. Containment. A frozen path reached by traversal is still a frozen path.
    try:
        target = resolve_within(root, label, must_exist=not creating)
    except PathRefused as exc:
        return ToolResult.refused("edit_code", Capability.MODIFY_CODE.value, str(exc))

    # Re-check the frozen set against the *resolved* path: "a/../tests/x.py" normalises to
    # something the string check above would have missed.
    resolved_label = relative_label(root, target)
    reason = frozen_reason(resolved_label)
    if reason:
        return ToolResult.refused("edit_code", Capability.MODIFY_CODE.value, reason)

    # newline="" on both sides. The default write_text translates a line feed to
    # os.linesep, which on Windows would silently rewrite every line ending in the file
    # and turn a one-line change into a whole-file diff.
    old_text = target.read_text(encoding="utf-8", newline="") if target.exists() else ""
    diff = _diff(old_text, new_text, resolved_label)

    if not diff:
        return ToolResult(
            ok=True,
            tool="edit_code",
            capability=Capability.MODIFY_CODE.value,
            output="",
            reason="no change: the file already has this content",
            metadata={"path": resolved_label, "applied": False},
        )

    # 3. Review before write. Never silent.
    if not confirm:
        return ToolResult(
            ok=True,
            tool="edit_code",
            capability=Capability.MODIFY_CODE.value,
            output=diff,
            reason="review this diff, then re-invoke with confirm=True to apply and verify",
            metadata={"path": resolved_label, "applied": False, "creating": creating},
        )

    # 4. Snapshot -> apply -> verify -> revert on any failure.
    snapshot = Snapshot.take(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8", newline="")

    failures: list[str] = []
    verdicts: dict[str, int] = {}
    for name, selector in (("positive_controls", controls), ("full_suite", suite)):
        try:
            completed = _run(selector, root)
        except subprocess.TimeoutExpired:
            failures.append(f"{name} ({selector}) exceeded {VERIFY_TIMEOUT_SECONDS}s")
            verdicts[name] = -1
            break
        verdicts[name] = completed.returncode
        if completed.returncode != 0:
            tail = ((completed.stdout or "") + (completed.stderr or "")).strip().splitlines()
            failures.append(f"{name} ({selector}) failed:\n" + "\n".join(tail[-15:]))
            break  # do not run the slower suite once the controls have failed

    if failures:
        reverted = snapshot.restore()
        return ToolResult(
            ok=False,
            tool="edit_code",
            capability=Capability.MODIFY_CODE.value,
            output=diff,
            reason=(
                "edit reverted automatically: verification failed and was not retried.\n\n"
                + "\n\n".join(failures)
            ),
            transmittable=False,
            metadata={
                "path": resolved_label,
                "applied": False,
                "reverted": reverted,
                "restored_sha256": snapshot.sha256,
                "verdicts": verdicts,
            },
        )

    return ToolResult(
        ok=True,
        tool="edit_code",
        capability=Capability.MODIFY_CODE.value,
        output=diff,
        reason="applied; positive controls and full suite both green",
        metadata={
            "path": resolved_label,
            "applied": True,
            "creating": creating,
            "verdicts": verdicts,
            "previous_sha256": snapshot.sha256,
        },
    )


register(
    Tool(
        name="edit_code",
        capability=Capability.MODIFY_CODE,
        func=edit_code,
        description=(
            "Propose a diff against a non-frozen source file; on confirmation apply it, run the "
            "positive controls and the full suite, and revert automatically on any failure."
        ),
    )
)
