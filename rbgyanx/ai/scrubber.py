"""
Fail-closed PHI scrubber for anything the assistant would transmit to a remote provider.

This is a different contract from :mod:`rbgyanx.ai.phi_guard`, and both are deliberately kept:

  * ``phi_guard`` WARNS and never blocks. It governs text the *user* typed and chose to send,
    and it stays warn-only for local providers per the documented 2026-07-25 decision.
  * ``scrubber`` (this module) FAILS CLOSED. It governs machine-generated text the assistant
    would forward on the user's behalf - tracebacks, test output, tool results - where there is
    no human reading every byte before it leaves. An unconfident scrub is a refusal, never a
    smaller payload.

Why ``confident`` exists at all
-------------------------------
A deny-list cannot prove the absence of PHI. Patient names are unbounded strings: a folder
``\\\\nas\\onc\\Mueller_A`` or a structure label ``Parotid_L_Smith`` matches no pattern anyone can
write in advance. So this module does two things rather than one:

  1. It redacts everything it *can* recognise (the deny-list, below).
  2. It then asks whether anything *unrecognisable but risky* survived, and if so reports
     ``confident=False`` so the caller refuses to transmit.

For tracebacks the module goes further and works by reconstruction rather than redaction: file
paths are re-derived from known-safe roots (the install tree, the interpreter, site-packages)
and anything outside those roots is dropped entirely rather than trimmed. A path outside the
software tree is a data path, and every component of it - not just the leaf - can be a name.
``C:\\Users\\<name>\\...`` leaks a person before you ever reach the patient folder.

The pattern set is kept deliberately in step with ``scripts/pre_publish_check.py``. It is
re-declared here rather than imported: that script chdirs at import time and is itself a frozen
file, so importing it would be both a side effect and a coupling. If you change one, change both.

Nothing here performs network I/O, and no matched value is ever retained or logged - findings
carry a masked sample only.
"""

from __future__ import annotations

import contextlib
import functools
import os
import re
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Finding",
    "ScrubResult",
    "ScrubRefused",
    "scrub",
    "scrub_traceback",
    "scrub_for_transmission",
    "structure_label_is_recognised",
    "reset_label_cache",
    "LABELS_ENV_VAR",
    "install_root",
]


class ScrubRefused(RuntimeError):
    """Raised when text cannot be confidently cleaned and therefore must not be transmitted."""


@dataclass(frozen=True)
class Finding:
    """One redaction. ``sample`` is masked - the raw value is never retained."""

    category: str
    sample: str


@dataclass(frozen=True)
class ScrubResult:
    """Outcome of a scrub. ``text`` is always a new string; the input is never mutated."""

    text: str
    findings: tuple[Finding, ...] = ()
    confident: bool = True
    #: Why confidence was withheld, for the user-facing refusal message.
    reasons: tuple[str, ...] = ()

    @property
    def safe_to_transmit(self) -> bool:
        return self.confident


def _mask(value: str) -> str:
    value = value.strip()
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


# --------------------------------------------------------------------------- deny-list
#
# Kept in step with scripts/pre_publish_check.py. Order matters: the most specific patterns run
# first so that a path is redacted as a path before its digits are redacted as an id.

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # UNC share paths - very often a departmental data mount.
    ("unc_path", re.compile(r"\\\\[^\s\"'<>|]+")),
    # Absolute Windows paths, including the author's-home case pre_publish_check blocks.
    ("windows_path", re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]*")),
    # POSIX data/home roots.
    (
        "posix_path",
        re.compile(r"/(?:home|Users|data|mnt|media|srv|export|scratch)/[^\s\"'<>|]*"),
    ),
    # DICOM person-name form (Last^First^Middle), which appears with or without brackets.
    ("person_name", re.compile(r"\b[A-Za-z][A-Za-z'\-]{1,30}\^[A-Za-z][A-Za-z'\-^]{1,60}")),
    # Explicit DICOM / record field labels together with their value. ``[ \t]`` rather than
    # ``\s`` so the match can never cross a newline and swallow the next record.
    (
        "dicom_field",
        re.compile(
            r"\b(?:PatientID|PatientName|PatientBirthDate|PatientSex|PatientAge|"
            r"OtherPatientIDs|AccessionNumber|InstitutionName|ReferringPhysicianName|"
            r"StudyInstanceUID|SeriesInstanceUID|SOPInstanceUID|MRN|medical[ \t]*record)\b"
            r"[ \t]*[:=]?[ \t]*[^\r\n,;)]{0,64}",
            re.IGNORECASE,
        ),
    ),
    # DICOM UID: dotted numeric, 3+ groups.
    ("dicom_uid", re.compile(r"\b\d(?:\.\d+){3,}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Long digit runs (MRN / accession), not part of a decimal.
    ("id_number", re.compile(r"(?<![\d.])\d{7,}(?![\d.])")),
    # Dates that could be a date of birth.
    ("date", re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:19|20)\d{6})\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # "Last, First".
    ("name_like", re.compile(r"\b[A-Z][a-z]{1,20},\s*[A-Z][a-z]{1,20}\b")),
)


# ------------------------------------------------------- residual-risk markers (allow-list side)
#
# Applied to what SURVIVES the deny-list. These do not redact; they withhold confidence, which
# makes the caller refuse. This is the half that makes the module honest: it is how the scrubber
# admits that it cannot recognise every name.

_RESIDUAL: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("an absolute path survived redaction", re.compile(r"[A-Za-z]:[\\/]|\\\\\w|/home/|/Users/")),
    ("a long digit run survived redaction", re.compile(r"(?<![\d.])\d{7,}(?![\d.])")),
    (
        "a capitalised token is adjacent to a patient-related keyword",
        re.compile(
            r"\b(?:patient|subject|case|mrn|name|dob|born)\b[^\r\n]{0,20}?\b[A-Z][a-z]{2,}\b",
            re.IGNORECASE,
        ),
    ),
)


# ------------------------------------------------------ structure labels (the hard case)
#
# A structure label is where a name hides in plain sight: "Parotid_L_Smith" matches no pattern
# above, because "Smith" is only identifying in context. Rather than guess, this checks the label
# against the vocabulary rbGyanX already ships - STRUCTURE_ALIASES and TG263_ALIASES - and treats
# any unrecognised segment sitting alongside a recognised anatomical one as a possible identifier.
# Refusing an oddly-named legitimate structure is the acceptable direction to be wrong in.

#: Laterality/qualifier segments that are legitimate anywhere in a label.
_MODIFIER_SEGMENTS = frozenset(
    [
        "l",
        "r",
        "a",
        "p",
        "s",
        "i",
        "lt",
        "rt",
        "left",
        "right",
        "ant",
        "post",
        "sup",
        "inf",
        "med",
        "lat",
        "bilat",
        "both",
        "combined",
        "total",
        "whole",
        "pair",
        "prv",
        "opt",
        "eval",
        "exp",
        "itv",
        "boost",
        "low",
        "high",
        "mid",
        "inner",
        "outer",
        "core",
        "rind",
        "ring",
        "shell",
        "margin",
        "sub",
        "gtv",
        "ctv",
        "ptv",
        "itv",
        "igtv",
        "oar",
        "body",
        "external",
        "skin",
        "bolus",
        "couch",
    ]
)


@functools.lru_cache(maxsize=1)
def _structure_vocabulary() -> frozenset[str]:
    """Every structure token rbGyanX recognises, lowercased and punctuation-stripped."""
    tokens: set[str] = set()

    def _add(raw: str) -> None:
        for seg in re.split(r"[^A-Za-z]+", raw):
            if len(seg) >= 2:
                tokens.add(seg.lower())

    try:
        from engine.config.structure_aliases import STRUCTURE_ALIASES

        for canonical, aliases in STRUCTURE_ALIASES.items():
            _add(canonical)
            for alias in aliases:
                _add(alias)
    except Exception:  # engine not importable: fall back to the built-in list below  # nosec B110
        pass
    try:
        from engine.config.tg263_aliases import TG263_ALIASES

        for canonical, aliases in TG263_ALIASES.items():
            _add(canonical)
            for alias in aliases:
                _add(alias)
    # Accepted: engine not importable: falls back to the built-in label list.
    except Exception:  # nosec B110
        pass

    # Minimal fallback so the scrubber still works if engine.config is unavailable.
    _add(
        "parotid submandibular lung kidney cochlea optic nerve chiasm hippocampus lacrimal "
        "temporal lobe brain brainstem stem spinal cord larynx esophagus oesophagus oral "
        "cavity mandible thyroid heart liver stomach bowel bladder rectum femur head neck "
        "breast chestwall pharynx constrictor lens eye globe pituitary trachea"
    )
    return frozenset(tokens)


# ------------------------------------------------- site-registered label vocabulary
#
# The residual checks above are calibrated on English structure names, and the non-ASCII check
# treats any non-ASCII letter as possibly a name with diacritics. That is right for "Mueller"
# and wrong for a department whose structures are named "Ohrspeicheldruese_L", "Parotida_izq"
# or a set written in a non-Latin script: those would refuse constantly, and a safety control
# that fires constantly gets switched off. That is the real failure mode, worse than the leak
# the control was protecting against.
#
# The escape hatch is declaration, not guesswork. A site registers its own label vocabulary
# once, exactly as it can ship its own reference pack, and thereafter its labels pass. A
# refusal that tells you how to fix it permanently gets fixed; a refusal with no remedy gets
# the feature turned off.
#
# Deliberately NOT a shipped multilingual alias set: a partial one works for the languages that
# happen to be included and fails for the next, which is the same constant-refusal problem made
# unpredictable, and medical terminology across languages is not something this file can verify.

#: Where a site declares its structure labels.
LABELS_ENV_VAR = "RBGYANX_STRUCTURE_LABELS"


def _key(text: str) -> str:
    """Whole-label key: lowercased, punctuation dropped.

    ``str.isalnum`` is Unicode-aware, so a label written in a non-Latin script keeps its
    characters here even though :func:`_label_segments` (which splits on ASCII letters) sees
    nothing in it. That is the point: a declared non-Latin label can still be matched verbatim.
    """
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def _labels_dir() -> Path:
    return Path(__file__).resolve().parent / "reference_packs"


def _label_files(env: dict | None = None) -> list[Path]:
    """Files that may declare site structure labels, most specific first."""
    import os as _os

    env = dict(_os.environ) if env is None else env
    found: list[Path] = []
    declared = env.get(LABELS_ENV_VAR)
    if declared:
        path = Path(declared)
        if path.is_dir():
            found.extend(sorted(path.glob("*.json")))
        elif path.is_file():
            found.append(path)
    found.extend(sorted(_labels_dir().glob("*.json")))
    return found


def _read_labels(path: Path) -> list[str]:
    """Labels from one file: a bare JSON list, or a "structure_labels" key in a pack."""
    import json as _json

    try:
        raw = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if isinstance(x, (str, int, float))]
    if isinstance(raw, dict):
        declared = raw.get("structure_labels")
        if isinstance(declared, list):
            return [str(x) for x in declared if isinstance(x, (str, int, float))]
    return []


@functools.lru_cache(maxsize=1)
def _site_labels() -> tuple[tuple[str, ...], frozenset[str], frozenset[str]]:
    """(raw labels, normalised whole labels, normalised segments) declared by this site."""
    raw: list[str] = []
    for path in _label_files():
        raw.extend(_read_labels(path))
    whole = {_key(label) for label in raw if _key(label)}
    segments: set[str] = set()
    for label in raw:
        segments.update(seg for seg in _label_segments(label) if len(seg) >= 2)
    return tuple(dict.fromkeys(raw)), frozenset(whole), frozenset(segments)


def reset_label_cache() -> None:
    """Forget cached vocabularies. For tests, and after a site edits its label file."""
    _site_labels.cache_clear()
    _structure_vocabulary.cache_clear()


def _registered_label_pattern() -> re.Pattern[str] | None:
    """A pattern matching any registered label verbatim, longest first."""
    raw, _whole, _segments = _site_labels()
    usable = sorted((r for r in raw if r and r.strip()), key=len, reverse=True)
    if not usable:
        return None
    return re.compile("|".join(re.escape(label) for label in usable), re.IGNORECASE)


def _strip_registered_labels(text: str) -> str:
    """Remove labels the site has declared before the residual checks run.

    A declared label is known vocabulary, so it must not be read as evidence of risk - which is
    what would otherwise happen to any label written in a non-Latin script.
    """
    pattern = _registered_label_pattern()
    return pattern.sub(" ", text) if pattern is not None else text


#: A compound token: alphanumeric segments joined by underscores or hyphens.
_COMPOUND_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[_-][A-Za-z0-9]+)+\b")


def _label_segments(label: str) -> list[str]:
    return [s.lower() for s in re.split(r"[^A-Za-z]+", label) if s]


def structure_label_is_recognised(label: str) -> bool:
    """True when every alphabetic segment of ``label`` is known vocabulary.

    Used by the tool layer before a structure label is forwarded to a remote provider.
    """
    _raw, site_whole, site_segments = _site_labels()
    if _key(label) in site_whole:
        return True  # declared verbatim by this site
    if _has_non_ascii_letter(label):
        # A non-Latin or accented label carries characters this vocabulary cannot speak to, and
        # the declaration check above has already had its chance. Returning True here would put
        # this function out of step with the scrub path, which refuses the same label - and two
        # guards that disagree are worse than one.
        return False
    segments = _label_segments(label)
    if not segments:
        return False
    vocabulary = _structure_vocabulary()
    return all(
        seg in vocabulary or seg in _MODIFIER_SEGMENTS or seg in site_segments for seg in segments
    )


def _has_unrecognised_structure_segment(text: str) -> bool:
    """True when a structure-like compound token carries a segment we cannot account for."""
    vocabulary = _structure_vocabulary()
    _raw, _whole, site_segments = _site_labels()
    for match in _COMPOUND_TOKEN.finditer(text):
        segments = _label_segments(match.group(0))
        anatomical = [s for s in segments if s in vocabulary]
        if not anatomical:
            continue  # not a structure label - e.g. run_controller, max_tokens
        unknown = [
            s
            for s in segments
            if len(s) >= 3
            and s not in vocabulary
            and s not in _MODIFIER_SEGMENTS
            and s not in site_segments
        ]
        if unknown:
            return True
    return False


#: The DICOM Patient module. Any value on such a line is identifying by definition.
_DICOM_PATIENT_TAG = re.compile(r"\(0010,[0-9A-Fa-f]{4}\)")
_DICOM_PATIENT_KEYWORD = re.compile(
    r"\b(?:PatientID|PatientName|PatientBirthDate|PatientSex|PatientAge|OtherPatientIDs|"
    r"AccessionNumber|ReferringPhysicianName|InstitutionName)\b",
    re.IGNORECASE,
)
_BRACKETED_VALUE = re.compile(r"\[[^\]\r\n]*\]")


def _redact_dicom_dump_lines(text: str) -> tuple[str, list[Finding]]:
    """Redact bracketed values on DICOM-dump lines.

    A tag dump prints ``(0010,0010) PN [Smith^John]  # PatientName`` - the value comes *before*
    the keyword, so a keyword-anchored pattern reading forwards never reaches it. Handling this
    line-wise is more reliable than trying to express it as one regex.
    """
    findings: list[Finding] = []
    out_lines: list[str] = []
    for line in text.splitlines():
        if _DICOM_PATIENT_TAG.search(line) or _DICOM_PATIENT_KEYWORD.search(line):

            def _sub(match: re.Match[str]) -> str:
                findings.append(Finding("dicom_value", _mask(match.group(0))))
                return "[REDACTED:dicom_value]"

            line = _BRACKETED_VALUE.sub(_sub, line)
        out_lines.append(line)
    out = "\n".join(out_lines)
    if text.endswith("\n"):
        out += "\n"
    return out, findings


def _apply_deny_list(text: str) -> tuple[str, list[Finding]]:
    out, findings = _redact_dicom_dump_lines(text)
    for category, pattern in _PATTERNS:

        def _sub(match: re.Match[str], _cat: str = category) -> str:
            findings.append(Finding(_cat, _mask(match.group(0))))
            return f"[REDACTED:{_cat}]"

        out = pattern.sub(_sub, out)
    return out, findings


#: Residual checks that need code rather than a regex.
def _has_non_ascii_letter(text: str) -> bool:
    """A non-ASCII *letter* may be a name with diacritics.

    Deliberately not "any byte above 0x7f": an en-dash in a numeric range or a bullet in a
    summary is typography, not an identifier. Refusing on those would make the gate fire on
    rbGyanX's own output, which is how a safety control ends up switched off.
    """
    return any(ch.isalpha() and ord(ch) > 127 for ch in text)


_RESIDUAL_CHECKS: tuple[tuple[str, object], ...] = (
    (
        "a non-ASCII letter is present, which may be a name with diacritics",
        _has_non_ascii_letter,
    ),
    (
        "a structure-like label carries an unrecognised segment, which may be a name",
        _has_unrecognised_structure_segment,
    ),
)


#: Our own markers. They must be stripped before the residual scan, or a redaction that
#: succeeded would itself read as evidence that something risky survived it.
_MARKER = re.compile(r"\[REDACTED:[^\]]*\]")


def _residual_reasons(text: str) -> list[str]:
    text = _MARKER.sub(" ", text)
    text = _strip_registered_labels(text)
    reasons = [reason for reason, pattern in _RESIDUAL if pattern.search(text)]
    reasons += [reason for reason, check in _RESIDUAL_CHECKS if check(text)]
    return reasons


def scrub(text: str) -> ScrubResult:
    """Redact recognisable identifiers, then report whether the result is safe to transmit.

    Never mutates the input. ``confident=False`` means the caller MUST refuse to transmit;
    it does not mean "send the redacted version anyway".
    """
    if not text:
        return ScrubResult("", (), True, ())
    cleaned, findings = _apply_deny_list(text)
    reasons = _residual_reasons(cleaned)
    return ScrubResult(cleaned, tuple(findings), not reasons, tuple(reasons))


# --------------------------------------------------------------------------- tracebacks


def install_root() -> Path:
    """The rbGyanX install tree - paths under here are software, not data."""
    return Path(__file__).resolve().parents[2]


def _safe_roots() -> list[tuple[str, Path]]:
    """Roots whose paths are software and therefore safe to name in cleartext."""
    roots: list[tuple[str, Path]] = [("", install_root())]
    for key in ("purelib", "platlib", "stdlib"):
        try:
            path = sysconfig.get_paths().get(key)
        except Exception:  # pragma: no cover - defensive
            path = None
        if path:
            roots.append((f"<{key}>", Path(path).resolve()))
    with contextlib.suppress(Exception):  # pragma: no cover - defensive
        roots.append(("<prefix>", Path(sys.prefix).resolve()))
    return roots


def _rewrite_path(raw: str) -> str:
    """Re-derive a file path from a known-safe root, or drop it entirely.

    Reconstruction, not trimming: anything outside the software tree is a data path, and every
    component of a data path can be an identifier - the home directory as readily as the patient
    folder. Trimming only the leaf would still publish ``C:\\Users\\<name>``.
    """
    # A path written in the OTHER platform's convention cannot be inside this platform's
    # install tree, and resolve() will not say so: on POSIX a backslash is an ordinary
    # character, so a drive-lettered path resolves to a relative name under the cwd and can
    # land inside the tree. Only applied off Windows, because on Windows a drive letter is
    # exactly how our own paths look.
    text = raw.strip()
    if os.name != "nt" and (text.startswith("\\\\") or text[1:2] == ":"):
        return "[REDACTED:external-path]"
    try:
        candidate = Path(raw).resolve()
    except (OSError, ValueError):
        return "[REDACTED:external-path]"
    for label, root in _safe_roots():
        try:
            rel = candidate.relative_to(root)
        except ValueError:
            continue
        rel_text = rel.as_posix()
        return f"{label}/{rel_text}" if label else rel_text
    return "[REDACTED:external-path]"


#: ``  File "<path>", line <n>, in <name>`` - the only traceback line that carries a path.
_TB_FILE_LINE = re.compile(r'^(?P<indent>\s*)File "(?P<path>.*?)", line (?P<line>\d+)(?P<rest>.*)$')


def scrub_traceback(text: str) -> ScrubResult:
    """Scrub a traceback by reconstructing its frames, then deny-list the remainder.

    Frame paths are re-derived from known-safe roots. Every other line (the exception message,
    and any source echo) is passed through the ordinary deny-list and residual-risk check,
    because those lines can carry values as easily as paths.
    """
    if not text:
        return ScrubResult("", (), True, ())

    findings: list[Finding] = []
    rebuilt: list[str] = []
    for line in text.splitlines():
        match = _TB_FILE_LINE.match(line)
        if not match:
            rebuilt.append(line)
            continue
        raw_path = match.group("path")
        new_path = _rewrite_path(raw_path)
        if new_path == "[REDACTED:external-path]":
            findings.append(Finding("external-path", _mask(raw_path)))
        rebuilt.append(
            f'{match.group("indent")}File "{new_path}", '
            f'line {match.group("line")}{match.group("rest")}'
        )

    intermediate = "\n".join(rebuilt)
    if text.endswith("\n"):
        intermediate += "\n"

    cleaned, more = _apply_deny_list(intermediate)
    findings.extend(more)
    reasons = _residual_reasons(cleaned)
    return ScrubResult(cleaned, tuple(findings), not reasons, tuple(reasons))


# --------------------------------------------------------------------------- the caller gate


def scrub_for_transmission(text: str, *, remote: bool, traceback: bool = False) -> str:
    """Return text safe to send, or refuse.

    This is the caller-side gate the hard constraint refers to. For a local provider the text is
    returned unchanged - the matrix grants raw access because nothing leaves the machine. For a
    remote provider the text is scrubbed, and an unconfident scrub raises :class:`ScrubRefused`
    rather than transmitting a best-effort payload.
    """
    if not remote:
        return text
    result = scrub_traceback(text) if traceback else scrub(text)
    if not result.confident:
        raise ScrubRefused(
            "refusing to transmit to a remote provider: the text could not be confidently "
            "cleaned (" + "; ".join(result.reasons) + "). Switch to a local provider to "
            "share this content, or send a summary you have checked yourself. If this is "
            "your department's own structure naming, declare it once via "
            + LABELS_ENV_VAR
            + " and it will stop being flagged."
        )
    return result.text
