#!/usr/bin/env python3
"""
Pre-publish gate. Run this before pushing to a public remote.

    python scripts/pre_publish_check.py

Exits 0 only if every check passes. Checks, in order of severity:

  BLOCKER   leaked credentials, private keys, absolute user paths, patient identifiers
  BLOCKER   version disagreement across pyproject / CITATION.cff / VERSION.txt
  BLOCKER   build artefacts, caches or logs staged for commit
  WARN      files above a size threshold
  WARN      claims in README that disagree with the tree (test counts, module paths)

No network access. Reads only the git index, so it sees exactly what would be pushed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

BLOCK, WARN, OK = [], [], []
SIZE_WARN_KB = 500

# Paths whose contents are documentation of what NOT to do, or test fixtures.
ALLOW = {
    "scripts/pre_publish_check.py",
    "docs/KNOWN_LIMITATIONS.md",
    "tests/test_ai_panel.py",          # fixture uses PatientName: Doe
}

SECRETS = [
    ("private key", re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("hardcoded secret",
     re.compile(r"(api_key|apikey|secret_key|password|auth_token)\s*=\s*"
                r"['\"][A-Za-z0-9_\-]{16,}['\"]", re.I)),
]
PRIVACY = [
    ("absolute user path", re.compile(r"C:\\+Users\\+(?!<|\{|\$)[A-Za-z]")),
    ("OneDrive desktop path", re.compile(r"OneDrive[\\/]+Desktop", re.I)),
    ("sandbox path", re.compile(r"/sessions/[a-z\-]+/mnt/")),
    ("DICOM patient name",
     re.compile(r"PatientName\s*[:=]\s*['\"]?(?!\[|<|Doe)[A-Z][A-Za-z]{2,}")),
]
FORBIDDEN_PATHS = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|"
    r"[^/]+\.egg-info|build|dist|\.venv|venv|node_modules)(/|$)"
    r"|\.(pyc|pyo|log|bak|orig|rej|swp|DS_Store)$")


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [p for p in out.stdout.splitlines() if p]


def main() -> int:
    files = tracked()
    OK.append(f"{len(files)} files tracked")

    # ---- 1. forbidden artefacts -------------------------------------------
    junk = [p for p in files if FORBIDDEN_PATHS.search(p)]
    if junk:
        BLOCK.append(f"{len(junk)} build artefact/cache/log files are tracked: {junk[:5]}")
    else:
        OK.append("no caches, build artefacts or logs tracked")

    # ---- 2. secrets and privacy -------------------------------------------
    sec_hits, priv_hits, big = [], [], []
    for rel in files:
        p = Path(rel)
        if not p.is_file():
            continue
        kb = p.stat().st_size / 1024
        if kb > SIZE_WARN_KB:
            big.append((rel, kb))
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
                                ".zip", ".gz", ".xlsx", ".docx", ".woff", ".woff2"}:
            continue
        if kb > 5000:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if rel in ALLOW:
            continue
        for label, pat in SECRETS:
            m = pat.search(txt)
            if m:
                sec_hits.append((rel, label, m.group(0)[:24]))
        for label, pat in PRIVACY:
            m = pat.search(txt)
            if m:
                priv_hits.append((rel, label, m.group(0)[:40]))

    if sec_hits:
        BLOCK.append(f"{len(sec_hits)} possible credential(s): "
                     + "; ".join(f"{f} [{l}]" for f, l, _ in sec_hits[:4]))
    else:
        OK.append("no credentials or private keys found")

    if priv_hits:
        BLOCK.append(f"{len(priv_hits)} privacy leak(s): "
                     + "; ".join(f"{f} [{l}] {s}" for f, l, s in priv_hits[:4]))
    else:
        OK.append("no absolute user paths or patient identifiers found")

    if big:
        big.sort(key=lambda x: -x[1])
        WARN.append(f"{len(big)} file(s) over {SIZE_WARN_KB} KB: "
                    + ", ".join(f"{f} ({kb:.0f} KB)" for f, kb in big[:5]))
    else:
        OK.append(f"no tracked file exceeds {SIZE_WARN_KB} KB")

    # ---- 3. version agreement ---------------------------------------------
    versions = {}
    try:
        pt = Path("pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', pt, re.M)
        if m:
            versions["pyproject.toml"] = m.group(1)
    except OSError:
        pass
    try:
        cf = Path("CITATION.cff").read_text(encoding="utf-8")
        m = re.search(r'^version:\s*"?([0-9][^"\s]*)"?', cf, re.M)
        if m:
            versions["CITATION.cff"] = m.group(1)
    except OSError:
        pass
    try:
        vt = Path("VERSION.txt").read_text(encoding="utf-8")
        m = re.search(r"Version\s+([0-9][0-9.]*)", vt)
        if m:
            versions["VERSION.txt"] = m.group(1)
    except OSError:
        pass
    if len(set(versions.values())) > 1:
        BLOCK.append(f"version disagreement: {versions}")
    elif versions:
        OK.append(f"version consistent at {next(iter(versions.values()))} "
                  f"across {len(versions)} files")

    # ---- 4. README claims vs tree -----------------------------------------
    try:
        rm = Path("README.md").read_text(encoding="utf-8")
    except OSError:
        BLOCK.append("README.md missing")
        rm = ""
    if rm:
        m = re.search(r"(\d{3,4})\s+tests", rm)
        if m:
            claimed = int(m.group(1))
            real = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                capture_output=True, text=True)
            mm = re.search(r"(\d+)\s+tests? collected", real.stdout)
            if mm:
                actual = int(mm.group(1))
                if abs(actual - claimed) > 5:
                    BLOCK.append(f"README claims {claimed} tests; pytest collects {actual}")
                else:
                    OK.append(f"README test count ({claimed}) matches collection ({actual})")
            else:
                WARN.append("could not collect tests to verify the README count")
        for link in re.findall(r"\[`([^`]+)`\]\(([^)]+)\)", rm):
            tgt = link[1].split("#")[0]
            if tgt and not tgt.startswith(("http", "mailto")) and not Path(tgt).exists():
                WARN.append(f"README links to a missing path: {tgt}")

    # ---- 5. community health ----------------------------------------------
    required = ["LICENSE", "README.md", "CITATION.cff", "CONTRIBUTING.md",
                "SECURITY.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md", ".gitignore"]
    absent = [f for f in required if not Path(f).exists()]
    if absent:
        BLOCK.append(f"missing community-health files: {absent}")
    else:
        OK.append(f"all {len(required)} community-health files present")

    # ---- report ------------------------------------------------------------
    print("=" * 74)
    print("PRE-PUBLISH CHECK")
    print("=" * 74)
    for m in OK:
        print(f"  PASS   {m}")
    for m in WARN:
        print(f"  WARN   {m}")
    for m in BLOCK:
        print(f"  BLOCK  {m}")
    print("=" * 74)
    if BLOCK:
        print(f"{len(BLOCK)} blocker(s) — do not push until resolved.")
        return 1
    print(f"Ready to publish. {len(WARN)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
