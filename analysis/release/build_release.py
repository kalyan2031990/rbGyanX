"""Phase 30/31 - build a clean de-identified release repository and a Zenodo package.

The source tree is COPIED, never modified: the working repository stays exactly as it is, and the
release is a fresh directory that can be inspected before anything is published. Nothing is pushed.

Three gates run over the copy before it is declared clean:
  1. PHI scan  - identifier-shaped tokens (MRN-like digit runs, dates of birth, accession numbers);
  2. path scan - absolute Windows/OneDrive paths and the operator's home directory;
  3. secret scan - API keys and tokens.

A gate failure is reported with the offending file and line. Nothing is auto-redacted, because silently
rewriting source before release is worse than refusing to ship it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import shutil
from datetime import date
from pathlib import Path

# legacy/ is retained: tests/test_tcp_analysis.py and friends execute those scripts, so
# dropping the directory turns a green suite red.
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "dist", "build", "venv", ".venv",
                ".venv-build", "htmlcov", "rbgyanx.egg-info", "backups", "temp_output",
                "gui_screenshots", "plots", "reports", "temp", ".eggs",
                ".hypothesis", ".ruff_cache", ".mypy_cache", "node_modules", ".idea", ".vscode"}
EXCLUDE_GLOBS = ("*.pyc", "*.pyo", "*.log", "*.dcm", "*.zip", "*.coverage", "temp_*.py",
                 "*.egg-info", "hnscc_*.txt", "dicom_search.txt", "*.v1bak")

TEXT_EXT = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".cff", ".toml", ".cfg", ".ini",
            ".ps1", ".sh", ".csv", ".html"}

PHI_PATTERNS = {
    "mrn_like": re.compile(r"\b\d{7,10}\b"),
    "dob_like": re.compile(r"\b(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b"),
    "accession": re.compile(r"\bACC[-_ ]?\d{6,}\b", re.I),
}
PATH_PATTERNS = {
    "windows_abs": re.compile(r"[A-Za-z]:[\\/](?:Users|Sampa)", re.I),
    "onedrive": re.compile(r"OneDrive", re.I),
    "user_home": re.compile(r"[\\/]Users[\\/][A-Za-z0-9_.-]+", re.I),
}
SECRET_PATTERNS = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    "aws": re.compile(r"AKIA[0-9A-Z]{16}"),
}
# lines that legitimately contain digit runs / the word OneDrive without being a leak
ALLOW = re.compile(r"(example|placeholder|<path>|your[-_ ]?path|dummy|synthetic|test_data|"
                   r"0522c|HN-CHUM|HN-HGJ|HN-HMR|HN-CHUS|HNSCC-|1\.2\.840|1\.3\.6\.1)", re.I)


def should_copy(p: Path, root: Path) -> bool:
    rel = p.relative_to(root)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    return not any(p.match(g) for g in EXCLUDE_GLOBS)


def tracked_files(root: Path) -> list[Path] | None:
    """Every file git tracks under ``root``, or None if this is not a git checkout.

    The release is the committed tree. Selecting by rglob+denylist shipped whatever happened to be
    sitting in the working directory - operator-specific workspace builders full of absolute paths
    into one machine's home directory came along that way. Anything worth releasing is worth
    committing first.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, text=True, check=True).stdout
    except Exception:
        return None
    return [root / rel for rel in out.split("\0") if rel]


# The scanner's own pattern definitions match the patterns, for obvious reasons.
SCAN_SELF_EXEMPT = {"analysis/release/build_release.py"}


def scan(root: Path) -> list[dict]:
    hits = []
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in TEXT_EXT:
            continue
        if str(f.relative_to(root)).replace("\\", "/") in SCAN_SELF_EXEMPT:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if ALLOW.search(line):
                continue
            for group, pats in (("PHI", PHI_PATTERNS), ("PATH", PATH_PATTERNS),
                                ("SECRET", SECRET_PATTERNS)):
                for name, rx in pats.items():
                    m = rx.search(line)
                    if m:
                        hits.append({"gate": group, "pattern": name,
                                     "file": str(f.relative_to(root)).replace("\\", "/"),
                                     "line": i, "match": m.group(0)[:60],
                                     "context": line.strip()[:120]})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path)
    ap.add_argument("--workspace", required=True, type=Path)
    a = ap.parse_args()

    if a.dest.exists():
        shutil.rmtree(a.dest)
    a.dest.mkdir(parents=True)

    candidates = tracked_files(a.source)
    selection = "git-tracked files"
    if candidates is None:
        candidates = [p for p in a.source.rglob("*") if p.is_file()]
        selection = "filesystem walk (source is not a git checkout)"

    n = 0
    for p in candidates:
        if not p.is_file() or not should_copy(p, a.source):
            continue
        rel = p.relative_to(a.source)
        (a.dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, a.dest / rel)
        n += 1
    print(f"selection: {selection}")

    hits = scan(a.dest)
    by_gate: dict[str, int] = {}
    for h in hits:
        by_gate[h["gate"]] = by_gate.get(h["gate"], 0) + 1

    (a.dest / "RELEASE_SCAN_REPORT.json").write_text(
        json.dumps({"generated": date.today().isoformat(), "files_copied": n,
                    "hits_by_gate": by_gate, "hits": hits[:400]}, indent=2), encoding="utf-8")
    print(f"copied {n} files | hits: {by_gate or 'none'}")
    for h in hits[:25]:
        print(f"  [{h['gate']}/{h['pattern']}] {h['file']}:{h['line']}  {h['match']}")
    if len(hits) > 25:
        print(f"  ... {len(hits) - 25} more (see RELEASE_SCAN_REPORT.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
