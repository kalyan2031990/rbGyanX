# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.3.x   | Yes       |
| < 1.3   | No        |

Note for 1.3.0: sending suspected patient data to a remote AI provider is blocked in code with
no user override. Earlier versions warned and transmitted anyway. See `DISCLAIMER.md`.

## Reporting a vulnerability

Email the maintainer via GitHub issues (private security advisory preferred) at
[github.com/kalyan2031990/rbGyanX/security](https://github.com/kalyan2031990/rbGyanX/security).

Please include: affected version, reproduction steps, and impact assessment.

## Scope

- `engine/`, `rbgyanx/`, installer scripts
- Out of scope: third-party TPS exports, local PHI in `input_folders/`

## CI checks

Both are **blocking**. They previously ended in `|| true`, so the build went green whether or
not they passed; that mask is gone, and each was failing at the time it was removed.

- `bandit -c pyproject.toml` on engine core and app logic — must report zero findings.
- `pip-audit` on the installed dependency set — must report zero unignored vulnerabilities.

### Accepted findings

Everything bandit or pip-audit reports is either fixed or listed here with a reason. Nothing is
suppressed for convenience, and the suppression mechanism is per-finding rather than global.

#### pip-audit: PYSEC-2026-2266 (pydicom 2.4.5) — accepted, not exploitable here

*What it is.* Path traversal in `pydicom.fileset.FileSet`: a maliciously crafted DICOMDIR whose
`ReferencedFileID` points outside the File-set root is resolved only to check existence, not to
check containment. Affects pydicom 2.0.0-rc.1 through 3.0.1; fixed in 3.0.2.

*Why it is not fixed.* `pydicom` is pinned `>=2.4,<3.0` because `dicompyler-core` imports
`pydicom.pixel_data_handlers.util`, which pydicom 3.0 removed. dicompyler-core 0.5.6 is the
latest release and its fallback import path is the long-dead `dicom` package, so installing
pydicom 3.0.2 makes `import dicompylercore.dicomparser` fail with
`ModuleNotFoundError: No module named 'dicom'`. Verified directly, not inferred. Lifting the pin
therefore requires replacing or vendoring dicompyler-core, which is a change to the DVH
ingestion architecture rather than a dependency bump.

*Why exposure is nil.* The vulnerability lives entirely in the `FileSet` / DICOMDIR API. This
codebase never touches it: `FileSet`, `fileset`, `DICOMDIR` and `ReferencedFileID` appear nowhere
in it. DICOM is read as individual files through `dicompylercore.DicomParser` and
`pydicom.dcmread`, neither of which walks a File-set index.

*What would change this assessment.* Any of the following makes the ignore invalid and it must
be removed: code that constructs a `pydicom.fileset.FileSet`, reads a DICOMDIR, or follows
`ReferencedFileID`; a dicompyler-core release compatible with pydicom 3.x; or a backport of the
fix to the 2.4 series.

#### pip-audit: PYSEC-2026-3447 (setuptools) — FIXED, not ignored

The build requirement is now `setuptools>=83`, which contains the fix. Recorded here only to
note that it was resolved by upgrading rather than by suppression.

#### bandit: B404 / B603 / B607 — accepted, see `[tool.bandit]` in `pyproject.toml`

Subprocess use is deliberate: the analysis pipeline wraps the `code1`-`code7` scripts. Every
call site passes a fixed argv **list** with `shell=False`, built from `sys.executable` and
repo-relative paths, never from user text. B607 is the `git rev-parse HEAD` provenance call.
**B602 (`shell=True`) is deliberately not skipped** — that is the finding that would indicate a
real shell-injection risk.

Individually accepted `try/except/pass` and `try/except/continue` sites carry an inline
`# nosec B110` / `# nosec B112` with a per-site reason directly above, rather than a blanket
skip, so a careless new silent swallow is still caught.
