"""
Append-only audit log for every assistant transmission.

One JSONL record per transmission, written to the user's config directory - not the repo (a
clone must not carry another site's audit trail, and a frozen install has no repo), and not a
temp directory (an audit trail that evaporates on reboot is not an audit trail).

What a record contains, and what it deliberately does not
---------------------------------------------------------
Recorded: timestamp, provider key, whether that provider was remote, install type, the
capability invoked, the payload's byte count, how many scrubber findings were redacted, and a
SHA-256 of the payload.

Never recorded: the payload itself, any prompt, any response, any API key, any structure label,
any file path. The log is PHI-free by construction rather than by filtering - there is no field
in :class:`AuditRecord` that could carry patient content in the first place.

On the digest. A hash lets a site prove that two transmissions were identical, or match a
payload it already holds, without the log retaining the content. It is a plain SHA-256 of the
exact transmitted bytes. Note the honest limitation: a hash of a very short, low-entropy payload
is brute-forceable in principle. Real payloads carry a system prompt and a question and are far
past that threshold, but the digest is an integrity aid, not a confidentiality guarantee.

Rotation keeps the log bounded so it cannot fill a user's disk. Rotation preserves history by
renaming, never by truncating in place.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "AuditRecord",
    "audit_dir",
    "audit_path",
    "record_transmission",
    "read_records",
    "MAX_BYTES",
    "KEEP_ROTATIONS",
]

#: Rotate once the active log passes this size.
MAX_BYTES = 2 * 1024 * 1024  # 2 MB - tens of thousands of records

#: How many rotated files to keep (audit.jsonl.1 ... .N).
KEEP_ROTATIONS = 5

_SCHEMA = 1


@dataclass(frozen=True)
class AuditRecord:
    """One transmission. Every field is metadata; none can carry patient content."""

    timestamp: str
    provider: str
    remote: bool
    install_type: str
    capability: str
    payload_bytes: int
    findings_redacted: int
    payload_sha256: str
    schema: int = _SCHEMA

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def audit_dir(env: dict[str, str] | None = None) -> Path:
    """The user's config directory for rbGyanX, per platform convention."""
    env = dict(os.environ) if env is None else env

    override = env.get("RBGYANX_AUDIT_DIR")
    if override:
        return Path(override)

    if os.name == "nt":
        base = env.get("APPDATA") or env.get("LOCALAPPDATA")
        if base:
            return Path(base) / "rbGyanX"
        return Path.home() / "AppData" / "Roaming" / "rbGyanX"

    xdg = env.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "rbgyanx"
    if os.uname().sysname == "Darwin":  # pragma: no cover - platform specific
        return Path.home() / "Library" / "Application Support" / "rbGyanX"
    return Path.home() / ".config" / "rbgyanx"


def audit_path(env: dict[str, str] | None = None) -> Path:
    """The active audit log file."""
    return audit_dir(env) / "ai_audit.jsonl"


def _restrict(path: Path) -> None:
    """Best-effort owner-only permissions. A no-op where the platform does not support it."""
    with contextlib.suppress(OSError, NotImplementedError):  # pragma: no cover - platform
        os.chmod(path, 0o600)


def _rotate_if_needed(
    path: Path, *, max_bytes: int = MAX_BYTES, keep: int = KEEP_ROTATIONS
) -> bool:
    """Rotate ``path`` to ``path.1`` when it exceeds ``max_bytes``. Returns True if rotated.

    History is preserved by renaming, never by truncating: an audit trail that silently drops
    its own oldest entries in place would be worse than no audit trail.
    """
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return False
    except OSError:  # pragma: no cover - defensive
        return False

    oldest = path.with_suffix(path.suffix + f".{keep}")
    if oldest.exists():
        try:
            oldest.unlink()
        except OSError:  # pragma: no cover - defensive
            return False

    for index in range(keep - 1, 0, -1):
        src = path.with_suffix(path.suffix + f".{index}")
        if src.exists():
            src.replace(path.with_suffix(path.suffix + f".{index + 1}"))

    path.replace(path.with_suffix(path.suffix + ".1"))
    return True


def record_transmission(
    *,
    provider: str,
    remote: bool,
    install_type: str,
    capability: str,
    payload: str | bytes,
    findings_redacted: int = 0,
    path: Path | None = None,
    env: dict[str, str] | None = None,
) -> AuditRecord:
    """Append one record for a transmission and return it.

    ``payload`` is measured and hashed here and then dropped; it is never held, echoed or
    written. Callers pass the exact bytes that left the machine so the digest describes what
    actually went out rather than what was intended to.
    """
    raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    record = AuditRecord(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provider=str(provider),
        remote=bool(remote),
        install_type=str(install_type),
        capability=str(capability),
        payload_bytes=len(raw),
        findings_redacted=int(findings_redacted),
        payload_sha256=hashlib.sha256(raw).hexdigest(),
    )

    target = audit_path(env) if path is None else Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(target)

    # "a" is the whole point: existing records are never reopened for writing.
    with open(target, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.to_json() + "\n")
    _restrict(target)
    return record


def read_records(path: Path | None = None, env: dict[str, str] | None = None) -> list[dict]:
    """Read back the active log. Malformed lines are skipped rather than raising."""
    target = audit_path(env) if path is None else Path(path)
    if not target.exists():
        return []
    records: list[dict] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
