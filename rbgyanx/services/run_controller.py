"""
Headless run controller (v2 Phase 4 · Slice 3).

Drives a DVH-text run end-to-end without importing a GUI toolkit: validate the request, read
the DVHs through the canonical engine reader, compute the classical models, and report progress
through a :class:`~rbgyanx.services.progress.ProgressReporter`.

Both the Tkinter app and the Qt app can call this; tests call it directly. The scientific
computation is delegated to the validated engine — nothing is reimplemented here, so classical
numerics stay byte-identical.

PHI: results are held in memory and returned to the caller. Nothing is written to disk unless
the caller asks, and no identifier ever leaves the process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rbgyanx.services.progress import NullReporter, ProgressReporter
from rbgyanx.services.run_request import RunRequest, validate_run_request

__all__ = ["StructureResult", "RunResult", "RunController"]


@dataclass
class StructureResult:
    """Per-structure outcome of a run."""

    label: str
    patient_id: str
    dose_gy: list[float] = field(default_factory=list)
    volume_pct: list[float] = field(default_factory=list)
    mean_dose_gy: float = float("nan")
    volume_cc: float = float("nan")
    ntcp: dict[str, float] = field(default_factory=dict)
    source_file: str = ""


@dataclass
class RunResult:
    """Everything a view needs to render a completed run."""

    ok: bool
    structures: list[StructureResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    n_files: int = 0

    @property
    def summary(self) -> str:
        if not self.ok:
            return f"Run failed ({len(self.errors)} error(s))"
        return f"{len(self.structures)} structure(s) from {self.n_files} file(s)"


class RunController:
    """UI-independent orchestration of a DVH-text run."""

    def __init__(self, reporter: ProgressReporter | None = None) -> None:
        self.reporter: ProgressReporter = reporter or NullReporter()

    # ---------------------------------------------------------------- public API

    def validate(self, request: RunRequest):
        """Pre-flight the request (shared rule set)."""
        return validate_run_request(request)

    def run_dvh_text(
        self,
        request: RunRequest,
        *,
        ntcp_models: dict[str, dict[str, Any]] | None = None,
    ) -> RunResult:
        """Parse every DVH in the input folder and compute the classical NTCP models.

        ``ntcp_models`` maps a display name to ``{"model": ..., "params": {...}}`` using the
        engine's model names (``lkb_probit``, ``lkb_loglogit``, ``rs_poisson``).
        """
        rep = self.reporter
        validation = self.validate(request)
        if not validation.ok:
            rep.status("Validation failed")
            for e in validation.errors:
                rep.log(f"[X] {e}")
            return RunResult(ok=False, errors=list(validation.errors))

        req = request.normalised()
        rep.status("Scanning input folder")
        rep.progress(0.0)

        try:
            files = self._list_dvh_files(req.input_path)
        except FileNotFoundError as exc:
            rep.log(f"[X] {exc}")
            return RunResult(ok=False, errors=[str(exc)])

        rep.log(f"Found {len(files)} DVH file(s)")
        results: list[StructureResult] = []
        errors: list[str] = []

        for i, path in enumerate(files, start=1):
            rep.status(f"Reading {i}/{len(files)}")
            try:
                results.append(self._read_one(path, ntcp_models or {}))
                rep.log(f"[OK] {path.name}")
            except Exception as exc:  # one bad file must not sink the run
                msg = f"{path.name}: {exc}"
                errors.append(msg)
                rep.log(f"[!] {msg}")
            rep.progress(i / max(len(files), 1))

        rep.status("Done")
        rep.progress(1.0)
        return RunResult(ok=bool(results), structures=results, errors=errors, n_files=len(files))

    # ---------------------------------------------------------------- internals

    @staticmethod
    def _list_dvh_files(folder: Path | None) -> list[Path]:
        from dicom_io.txt_dvh_reader import iter_dvh_text_files

        if folder is None:
            raise FileNotFoundError("no input folder supplied")
        return list(iter_dvh_text_files(folder))

    @staticmethod
    def _read_one(path: Path, ntcp_models: dict[str, dict[str, Any]]) -> StructureResult:
        """Parse one DVH file and evaluate the requested engine NTCP models."""
        from dicom_io.txt_dvh_reader import parse_dvh_text_file
        from radiobiology import dvh_object_to_dataframe
        from validation.ntcp_benchmark import classical_ntcp

        parsed = parse_dvh_text_file(path)
        diff = dvh_object_to_dataframe(parsed.dvh_object)

        dose: list[float] = []
        vol_pct: list[float] = []
        if diff is not None and not diff.empty:
            # Differential -> cumulative % for display (matches the DVH view's contract).
            import numpy as np

            d = diff["dose_gy"].to_numpy(dtype=float)
            v = diff["volume_frac"].to_numpy(dtype=float)
            cum = np.cumsum(v[::-1])[::-1]
            if cum[0] > 0:
                cum = cum / cum[0] * 100.0
            dose, vol_pct = list(d), list(cum)

        ntcp: dict[str, float] = {}
        for label, cfg in ntcp_models.items():
            model = cfg["model"]
            params = cfg["params"]
            try:
                if model == "rs_poisson":
                    value = float(classical_ntcp(model, params, dvhs=[diff])[0])
                else:
                    value = float(classical_ntcp(model, params, dose_metric=[parsed.dmean_gy])[0])
            except Exception:
                value = float("nan")
            ntcp[label] = value

        return StructureResult(
            label=parsed.raw_name or path.stem,
            patient_id=parsed.patient_id,
            dose_gy=dose,
            volume_pct=vol_pct,
            mean_dose_gy=float(parsed.dmean_gy),
            volume_cc=float(parsed.total_volume_cc),
            ntcp=ntcp,
            source_file=path.name,
        )
