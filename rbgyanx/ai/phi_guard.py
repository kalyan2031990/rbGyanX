"""
PHI guard for the AI panel (v2 Phase 5 · Slice A).

Scans outgoing text for patterns that look like protected health information and reports what it
found. Per the owner's explicit, documented decision (2026-07-25, see
``docs/PHASE5_AI_PANEL_DESIGN.md``), this guard **warns but never blocks** — including for remote
providers. Its job is to *inform* the user before a send, not to prevent one.

The guard is deliberately conservative (better a false positive the user waves past than a silent
leak). It reports categories and locations; it never logs or stores the matched values, and the
``redacted`` helper masks them for on-screen display.

Nothing here performs I/O. It is a pure function over a string, so it is trivially testable and
carries no PHI itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["PhiFinding", "scan_for_phi", "redact"]


@dataclass(frozen=True)
class PhiFinding:
    """One suspected-PHI hit. ``sample`` is already masked — the raw value is never retained."""

    category: str
    start: int
    end: int
    sample: str

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)


def _mask(value: str) -> str:
    """Mask a matched value so the finding can be shown without echoing PHI."""
    value = value.strip()
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


# (category, compiled pattern). Order matters only for reporting; all patterns are scanned.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Explicit DICOM/record field labels — the strongest signal.
    (
        "dicom_field",
        re.compile(
            r"\b(PatientID|PatientName|PatientBirthDate|OtherPatientIDs|AccessionNumber|"
            r"StudyInstanceUID|SeriesInstanceUID|SOPInstanceUID|MRN|medical\s*record)\b",
            re.IGNORECASE,
        ),
    ),
    # DICOM UID: dotted numeric, 3+ groups (e.g. 1.2.840.10008...).
    ("dicom_uid", re.compile(r"\b\d(?:\.\d+){3,}\b")),
    # Long digit runs (MRN / account / SSN-like). 7+ digits, not part of a decimal.
    ("id_number", re.compile(r"(?<![\d.])\d{7,}(?![\d.])")),
    # SSN pattern.
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Dates that could be a DOB: yyyy-mm-dd, dd/mm/yyyy, mm/dd/yyyy, yyyymmdd.
    ("date", re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:19|20)\d{6})\b")),
    # "Last, First" name-like tokens (two capitalised words around a comma).
    ("name_like", re.compile(r"\b[A-Z][a-z]{1,20},\s*[A-Z][a-z]{1,20}\b")),
    # E-mail addresses.
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # Absolute filesystem paths, which often embed patient identifiers.
    ("file_path", re.compile(r"(?:[A-Za-z]:\\[^\s\"']+|/(?:home|Users|data|mnt)/[^\s\"']+)")),
]


def scan_for_phi(text: str) -> list[PhiFinding]:
    """Return every suspected-PHI finding in ``text`` (possibly empty).

    Findings are sorted by position. The guard never mutates the text and never raises on
    content — callers decide what to do (this project: warn, do not block).
    """
    if not text:
        return []
    findings: list[PhiFinding] = []
    for category, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            findings.append(
                PhiFinding(
                    category=category, start=m.start(), end=m.end(), sample=_mask(m.group(0))
                )
            )
    findings.sort(key=lambda f: (f.start, f.end))
    return findings


def redact(text: str, findings: list[PhiFinding] | None = None) -> str:
    """Return ``text`` with every suspected-PHI span replaced by ``[REDACTED:<category>]``.

    Provided for callers/tests that want a de-identified copy; the live panel does not redact by
    default (warn-not-block), but the same primitive backs the on-screen preview.
    """
    findings = findings if findings is not None else scan_for_phi(text)
    out = text
    for f in sorted(findings, key=lambda f: f.start, reverse=True):
        out = out[: f.start] + f"[REDACTED:{f.category}]" + out[f.end :]
    return out
