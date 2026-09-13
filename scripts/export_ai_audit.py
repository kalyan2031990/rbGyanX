#!/usr/bin/env python3
"""
Export the AI assistant's audit log to CSV, with a short summary.

    python scripts/export_ai_audit.py                       # summary to stdout
    python scripts/export_ai_audit.py -o run_audit.csv      # ...and a CSV
    python scripts/export_ai_audit.py --log path/to/ai_audit.jsonl --include-rotated

This is what turns a run into analysable evidence later: how many transmissions, to which
providers, under which capabilities, and how often a guard refused to let something out.

It AGGREGATES; it does not ENRICH. Nothing here reads a prompt, a response, a file path or a
structure label, because the log does not contain them - and this script must not become the
reason someone starts putting them there. Every column it emits is a field the log already has.
The PHI-free-by-construction property of the log is only worth something if the tooling around
it preserves it, so the exporter is deliberately incapable of adding anything.

Exit code is 0 on success, 1 if the log cannot be read.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

# The columns the log defines. Listed explicitly so a future field has to be added here
# deliberately, rather than appearing in exports because it happened to be in the JSON.
COLUMNS = (
    "timestamp",
    "provider",
    "remote",
    "install_type",
    "capability",
    "outcome",
    "payload_bytes",
    "findings_redacted",
    "payload_sha256",
    "schema",
)


def _default_log() -> Path:
    from rbgyanx.ai.audit import audit_path

    return audit_path()


def load_records(log: Path, *, include_rotated: bool = False) -> list[dict]:
    """Read one JSONL log, optionally including its rotated generations, oldest first."""
    paths = [log]
    if include_rotated:
        rotated = sorted(
            log.parent.glob(log.name + ".*"),
            key=lambda p: int(p.suffix.lstrip(".") or 0),
            reverse=True,
        )
        paths = [*rotated, log]

    records: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # a truncated final line is not a reason to lose the rest
            if isinstance(obj, dict):
                records.append(obj)
    return records


def write_csv(records: list[dict], out: Path) -> None:
    """Write the records as CSV, one row per transmission, no derived content."""
    with open(out, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in COLUMNS})


def _table(title: str, counts: Counter, total: int) -> list[str]:
    if not counts:
        return [f"{title}: none", ""]
    width = max(len(str(k)) for k in counts)
    lines = [f"{title}:"]
    for key, count in counts.most_common():
        share = (100.0 * count / total) if total else 0.0
        lines.append(f"  {str(key):<{width}}  {count:>6}  {share:5.1f}%")
    lines.append("")
    return lines


def summarise(records: list[dict]) -> str:
    """A short, human-readable summary. Counts only - nothing is reconstructed."""
    total = len(records)
    if not total:
        return "No AI transmissions recorded.\n"

    sent = [r for r in records if r.get("outcome", "sent") == "sent"]
    refused = [r for r in records if r.get("outcome") == "refused"]
    remote_sent = [r for r in sent if r.get("remote")]
    stamps = sorted(str(r.get("timestamp", "")) for r in records if r.get("timestamp"))

    lines = [
        "=" * 66,
        "rbGyanX AI audit summary",
        "=" * 66,
        f"records                 : {total}",
        f"transmissions sent      : {len(sent)}",
        f"  of which remote       : {len(remote_sent)}",
        f"  of which local        : {len(sent) - len(remote_sent)}",
        f"guard refusals          : {len(refused)}",
        f"bytes transmitted       : {sum(int(r.get('payload_bytes') or 0) for r in sent):,}",
        f"identifiers redacted    : {sum(int(r.get('findings_redacted') or 0) for r in records):,}",
    ]
    if stamps:
        lines += [
            f"first record            : {stamps[0]}",
            f"last record             : {stamps[-1]}",
        ]
    lines += ["", "-" * 66, ""]

    lines += _table(
        "Transmissions by provider", Counter(r.get("provider") for r in sent), len(sent)
    )
    lines += _table(
        "Transmissions by capability", Counter(r.get("capability") for r in sent), len(sent)
    )
    lines += _table(
        "Transmissions by install type", Counter(r.get("install_type") for r in sent), len(sent)
    )
    if refused:
        lines += _table(
            "Refusals by capability", Counter(r.get("capability") for r in refused), len(refused)
        )

    unique = len({r.get("payload_sha256") for r in sent if r.get("payload_sha256")})
    if sent:
        lines += [
            f"distinct payloads       : {unique} of {len(sent)} "
            f"({len(sent) - unique} repeat transmission(s))",
            "",
        ]

    lines += [
        "This summary is aggregate only. The audit log holds no prompts, no responses and no",
        "patient data by construction, so none can appear here.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the rbGyanX AI audit log to CSV, with a summary."
    )
    parser.add_argument("--log", type=Path, default=None, help="path to ai_audit.jsonl")
    parser.add_argument("-o", "--output", type=Path, default=None, help="write CSV here")
    parser.add_argument(
        "--include-rotated", action="store_true", help="also read ai_audit.jsonl.1 ... .N"
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    args = parser.parse_args(argv)

    log = args.log or _default_log()
    if not log.exists() and not args.include_rotated:
        print(f"No audit log at {log}", file=sys.stderr)
        print(
            "Nothing has been transmitted, or RBGYANX_AUDIT_DIR points elsewhere.", file=sys.stderr
        )
        return 1

    records = load_records(log, include_rotated=args.include_rotated)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_csv(records, args.output)
        print(f"Wrote {len(records)} record(s) to {args.output}")

    if not args.quiet:
        print(summarise(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
