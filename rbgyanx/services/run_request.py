"""
Headless run request + validation (v2 Phase 4 · Slice 1).

``rbgyanx_gui.validate_inputs`` mixed three concerns: reading Tk variables, applying validation
rules, and showing a ``messagebox``. Only the middle one is real logic, so it lives here as a
pure function over a plain dataclass. The GUI keeps the Tk reading and the dialog; it delegates
the rules. Same rules, same order, same messages — see the equivalence tests.

PHI note: ``RunRequest`` holds file *paths* chosen by the operator, never patient data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["RunRequest", "ValidationResult", "validate_run_request"]

VALID_MODES = ("TCP", "NTCP", "BOTH")


@dataclass
class RunRequest:
    """Everything needed to start a run, with no toolkit dependency."""

    analysis_mode: str = ""  # "TCP" | "NTCP" | "BOTH"
    input_path: Path | None = None
    output_dir: Path | None = None
    clinical_file: Path | None = None
    input_source: str = "auto"  # "auto" | "dicom" | "dvh_txt"
    enable_ml: bool = False
    basic_mode: bool = True

    def normalised(self) -> RunRequest:
        """Coerce string paths to ``Path`` (the GUI hands over strings)."""
        return RunRequest(
            analysis_mode=(self.analysis_mode or "").strip(),
            input_path=Path(self.input_path) if self.input_path else None,
            output_dir=Path(self.output_dir) if self.output_dir else None,
            clinical_file=Path(self.clinical_file) if self.clinical_file else None,
            input_source=self.input_source or "auto",
            enable_ml=bool(self.enable_ml),
            basic_mode=bool(self.basic_mode),
        )


@dataclass
class ValidationResult:
    """Structured outcome — the caller decides how (or whether) to display it."""

    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def message(self) -> str:
        """The exact text the Tkinter app shows, so the dialog is unchanged."""
        if self.ok:
            return ""
        return "[X] Input Validation Failed:\n\n" + "\n".join(f"- {e}" for e in self.errors)


def validate_run_request(req: RunRequest) -> ValidationResult:
    """Apply the pre-flight rules. Pure: no dialogs, no logging, no side effects.

    Rule order matches the original ``validate_inputs`` so error text is identical.
    """
    r = req.normalised()
    errors: list[str] = []

    if not r.analysis_mode:
        errors.append("Analysis mode not selected (TCP only, NTCP only, or TCP + NTCP)")
    elif r.analysis_mode.upper() not in VALID_MODES:
        errors.append(f"Unknown analysis mode: {r.analysis_mode}")

    if not r.output_dir:
        errors.append("Output directory not selected")

    if not r.input_path:
        errors.append("Input folder not selected")
    else:
        p = r.input_path
        if not p.exists():
            errors.append(f"Input path does not exist: {p}")
        elif p.is_dir():
            if r.input_source == "dicom":
                if not _looks_like_dicom_dir(p):
                    errors.append(
                        f"Folder does not look like DICOM RT: {p}\n"
                        "Expected RTPLAN/RTDOSE/RTSTRUCT or .dcm files."
                    )
            else:
                dvh_files = list(p.glob("*.txt")) + list(p.glob("*.csv"))
                if not dvh_files:
                    errors.append(f"No TPS .txt/.csv DVH files in {p}")

    if r.enable_ml and not r.clinical_file:
        errors.append("Clinical data required for ML models")
    elif r.clinical_file and not r.clinical_file.exists():
        errors.append(f"Clinical data file does not exist: {r.clinical_file}")

    return ValidationResult(errors=errors)


def _looks_like_dicom_dir(path: Path) -> bool:
    """True if the folder plausibly holds DICOM RT (mirrors the GUI's engine-bridge check)."""
    if any(path.glob("*.dcm")):
        return True
    names = " ".join(p.name.upper() for p in path.iterdir() if p.is_file())
    return any(tag in names for tag in ("RTPLAN", "RTDOSE", "RTSTRUCT"))
