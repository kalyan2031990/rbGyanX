"""
Cohort runner (Phase 5) — one resumable, idempotent, deterministic command per cohort.

Wraps the per-patient engine (``run_analysis``) with: deterministic patient discovery (Phase-2
``cohort_discovery`` for DICOM; filename grouping for TPS text), **pseudonymisation with the map held
OUTSIDE the repo** (constraint C2), the mandated output tree, sixteen always-written machine-readable
CSVs with stable columns, a run manifest, per-patient log records, and a cohort summary. Re-running skips
already-completed patients (5.2). No PHI is ever written to the output tree — only pseudonyms.

Nothing here changes a radiobiological number; it orchestrates and reports.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import platform
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# The 16 guaranteed cohort-level exports (written even when empty, stable column order).
COHORT_CSVS: dict[str, list[str]] = {
    "patient_features.csv": ["pseudonym", "site", "site_confidence", "n_structures", "n_mapped",
                             "n_unmapped", "dvh_mode", "plan_selected", "degraded_mode"],
    "physical_metrics.csv": ["pseudonym", "structure", "category", "volume_cc", "Dmean_gy",
                             "Dmax_gy", "D2_gy", "D98_gy"],
    "tcp_results.csv": ["pseudonym", "structure", "model", "tcp"],
    "ntcp_results.csv": ["pseudonym", "structure", "model", "ntcp", "site_params_key",
                         "definition_ok", "reason_codes",
                         "uNTCP_mean", "uNTCP_sd", "uNTCP_p5", "uNTCP_p95", "uNTCP_n"],
    "plan_quality.csv": ["pseudonym", "target", "HI", "CI", "GI_pct"],
    "site_detection.csv": ["pseudonym", "site", "confidence", "evidence"],
    "structure_mapping.csv": ["pseudonym", "roi_number", "raw_name", "canonical", "category",
                              "confidence", "status"],
    "dvh_summary.csv": ["pseudonym", "structure", "volume_cc", "Dmean_gy", "Dmax_gy", "dvh_mode"],
    "benchmark.csv": ["pseudonym", "structure", "endpoint", "model", "value"],
    "ML_features.csv": ["pseudonym", "feature", "value"],
    "ML_predictions.csv": ["pseudonym", "model", "prediction"],
    "XAI_attributions.csv": ["pseudonym", "feature", "attribution"],
    "PINN_predictions.csv": ["pseudonym", "model", "prediction"],
    "QA.csv": ["pseudonym", "reason_code", "detail"],
    "cohort_summary.csv": ["metric", "value"],
    "failures.csv": ["pseudonym", "stage", "reason_code", "detail"],
}

_PHI_KEYS = {  # never written to the output tree (constraint C2)
    "primarypatientid", "anonpatientid", "anon_patient_id", "patientid", "patient_id", "patientname",
    "patient_name", "patientdob", "patient_dob", "patientbirthdate", "studydate", "study_date",
    "institution", "institutionname", "accessionnumber", "mrn", "folder_path", "folderpath",
}


@dataclass
class RunnerConfig:
    input_root: Path
    cohort: str
    output_root: Path
    validation: str = "ExternalValidation"  # InternalValidation | ExternalValidation
    input_kind: str = "dicom"               # dicom | dvh_txt
    limit: int | None = None
    seed: int = 0
    mode: str = "basic"
    site: str | None = None
    endpoint: str = "both"
    pseudonym_map_dir: Path | None = None   # MUST be outside the repo; defaults beside output_root
    file_pattern: str = "*.txt"             # dvh_txt only: which files form the cohort (e.g. one study arm)
    preserve_txt_canonical: bool = False    # dvh_txt: keep true ROI canonical (OARs) so NTCP can apply
    dose_per_fraction: float = 2.0          # TPS text: exports often omit fractionation entirely
                                            # ("Prescribed dose: not defined"), and the reader then
                                            # ASSUMES this value. Wrong for hypofractionation/SBRT.
    n_mc: int = 1000                        # advanced: uNTCP Monte-Carlo draws
    outcome_csv: Path | None = None         # advanced: required by the engine's ML/XAI branch


@dataclass
class PatientRecord:
    pseudonym: str
    status: str = "pending"                 # completed | skipped | failed
    processing_seconds: float = 0.0
    n_structures: int = 0
    n_mapped: int = 0
    n_missing: int = 0
    dvh_mode: str = ""
    plan_selected: str = ""
    degraded_mode: str = ""
    warnings: list[str] = field(default_factory=list)
    failure_reason: str = ""


# --------------------------------------------------------------------- helpers

def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip()
    except Exception:
        return "unknown"


def _strip_phi(row: dict) -> dict:
    return {k: v for k, v in row.items() if k.lower() not in _PHI_KEYS and not str(k).startswith("_")}


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    """Write a CSV with a fixed column order, even when empty. Deterministic (no timestamps)."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def _config_hash(cfg: RunnerConfig) -> str:
    payload = {k: str(v) for k, v in asdict(cfg).items() if k != "pseudonym_map_dir"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


# --------------------------------------------------------------------- discovery

def _discover_units(cfg: RunnerConfig) -> list[tuple[str, dict]]:
    """Return a deterministic, sorted list of (raw_patient_key, unit_info)."""
    root = Path(cfg.input_root)
    if cfg.input_kind == "dvh_txt":
        groups: dict[str, list[Path]] = {}
        for f in sorted(root.rglob(cfg.file_pattern)):
            m = re.match(r"([^_/\\]+)_", f.name)
            stem_key = m.group(1) if m else f.stem
            # Qualify with the file's folder relative to the root. Cohorts that restart patient
            # numbering per centre (e.g. "Center 1/.../Pat01" and "Center 4/.../Pat01" are DIFFERENT
            # people) would otherwise be merged into one patient. Folder-qualified keys keep them apart.
            rel_parent = f.parent.relative_to(root).as_posix()
            key = stem_key if rel_parent in ("", ".") else f"{rel_parent}/{stem_key}"
            groups.setdefault(key, []).append(f)
        return [(k, {"kind": "dvh_txt", "files": groups[k]}) for k in sorted(groups)]
    # dicom — deterministic discovery + selection (Phase 2)
    from dicom_io.cohort_discovery import discover_cohort

    units: list[tuple[str, dict]] = []
    for m in discover_cohort(root):
        key = m.patient_key or f"__NOID__{m.frame_of_reference[:12]}"
        units.append((key, {"kind": "dicom", "manifest": m}))
    return sorted(units, key=lambda kv: kv[0])


# --------------------------------------------------------------------- pseudonymisation

def _load_or_build_pseudonym_map(cfg: RunnerConfig, raw_keys: list[str], map_dir: Path) -> dict[str, str]:
    map_dir.mkdir(parents=True, exist_ok=True)
    map_path = map_dir / f"{cfg.cohort}_pseudonym_map.csv"
    mapping: dict[str, str] = {}
    if map_path.exists():
        with map_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                mapping[row["raw_patient_key"]] = row["pseudonym"]
    # assign new pseudonyms deterministically in sorted key order
    next_idx = len(mapping) + 1
    for key in sorted(raw_keys):
        if key not in mapping:
            mapping[key] = f"{cfg.cohort}-{next_idx:04d}"
            next_idx += 1
    with map_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_patient_key", "pseudonym"])
        for k in sorted(mapping):
            w.writerow([k, mapping[k]])
    return mapping


# --------------------------------------------------------------------- per-patient processing

def _stage_dicom(manifest, tmp: Path) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    for attr in ("rtplan_path", "rtdose_path", "rtstruct_path"):
        p = getattr(manifest, attr)
        if p:
            shutil.copy2(p, tmp / Path(p).name)
    return tmp


def _process_patient(cfg: RunnerConfig, pseudonym: str, unit: dict, patient_dir: Path,
                     tmp_root: Path) -> tuple[PatientRecord, dict]:
    """Run the engine on one patient's staged inputs; harvest PHI-free result rows. Never raises.

    The engine writes its (potentially raw-ID-bearing) files to a TEMP dir and its console output is
    suppressed; only PHI-stripped, pseudonymised rows and a sanitised summary leave this function (C2).
    """
    import contextlib
    import io

    from rbgyanx_engine import RunConfig, run_analysis

    rec = PatientRecord(pseudonym=pseudonym)
    harvest: dict = {k: [] for k in ("tcp", "ntcp", "physical", "site", "mapping", "qa")}
    t0 = time.perf_counter()
    engine_out = tmp_root / pseudonym / "engine_out"  # TEMP — never in the shared tree
    try:
        if unit["kind"] == "dvh_txt":
            stage = tmp_root / pseudonym / "in"
            stage.mkdir(parents=True, exist_ok=True)
            for f in unit["files"]:
                shutil.copy2(f, stage / f.name)
            input_dir, input_kind = stage, "dvh_txt"
        else:
            man = unit["manifest"]
            rec.degraded_mode = man.degraded_mode
            rec.plan_selected = Path(man.rtplan_path).name if man.rtplan_path else ""
            rec.warnings = list(man.reason_codes)
            # A DVH needs BOTH a dose grid and contours. Missing either is a documented reduced-output
            # mode (recorded with its reason code), not a failure — the engine would just raise.
            if man.degraded_mode in ("INSUFFICIENT", "NO_DOSE", "NO_STRUCT"):
                rec.status = "skipped"
                rec.failure_reason = man.degraded_mode
                return rec, harvest
            input_dir = _stage_dicom(man, tmp_root / pseudonym / "in")
            input_kind = "dicom"

        engine_out.mkdir(parents=True, exist_ok=True)
        cfg2 = RunConfig(
            endpoint=cfg.endpoint, input_kind=input_kind, input_dir=input_dir,
            output_dir=engine_out, site=cfg.site, mode=cfg.mode,
            # ADVANCED turns on the research depth: uNTCP Monte-Carlo uncertainty, the dosiomics /
            # PINN-registration extensions, and the ML path (which additionally needs an outcome CSV).
            # BASIC keeps the clinic-safe, fast defaults exactly as before.
            enable_ml=(cfg.mode == "advanced"),
            no_uncertainty=(cfg.mode != "advanced"),
            n_mc=cfg.n_mc,
            outcome_csv=cfg.outcome_csv,
            cohort=False, dvh_glob="*.txt", dose_per_fraction=cfg.dose_per_fraction,
            preserve_txt_canonical=cfg.preserve_txt_canonical,
        )
        # Suppress BOTH console streams and the logging tree. The engine logs the source-header
        # patient id on MC/uNTCP failures (pipeline warns with AnonPatientID); logging handlers hold
        # their own stream references and are NOT covered by redirect_stdout/stderr, so we mute the
        # engine loggers for the duration of the call (C2).
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _prev = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                result = run_analysis(cfg2)
            finally:
                logging.disable(_prev)
        for r in result.tcp_results:
            harvest["tcp"].append(_strip_phi(r))
        for r in result.ntcp_results:
            harvest["ntcp"].append(_strip_phi(r))
        rec.n_structures = len({r.get("canonical_name") or r.get("structure") for r in
                                harvest["tcp"] + harvest["ntcp"]})
        rec.status = "completed" if result.exit_code == 0 else "failed"
        if result.exit_code != 0:
            rec.failure_reason = "ENGINE_NONZERO_EXIT"
        # sanitised per-patient summary (pseudonym only) into the shared tree
        (patient_dir / "summary.json").write_text(
            json.dumps({"pseudonym": pseudonym, "status": rec.status,
                        "n_tcp_rows": len(harvest["tcp"]), "n_ntcp_rows": len(harvest["ntcp"]),
                        "degraded_mode": rec.degraded_mode}, indent=2), encoding="utf-8")
    except Exception as exc:  # fail soft, log loud (C4)
        rec.status = "failed"
        rec.failure_reason = type(exc).__name__
        # Log the pseudonym + exception TYPE only. Exception *messages* can quote source paths or
        # file content, which may carry identifiers (C2) — never log them.
        logger.warning("patient %s failed: %s", pseudonym, type(exc).__name__)
    finally:
        rec.processing_seconds = round(time.perf_counter() - t0, 3)
        shutil.rmtree(tmp_root / pseudonym, ignore_errors=True)  # drop temp engine files + raw inputs
    return rec, harvest


_ID_HEADER_RE = re.compile(r"^﻿?\s*Patient\s+(Name|ID)\s*:\s*(.+?)\s*$", re.I | re.M)


def harvest_source_identifiers(root: Path, patterns: tuple[str, ...] = ("*.txt",)) -> set[str]:
    """Read identifier VALUES out of TPS-text headers (Patient Name / Patient ID) so the post-run scan
    can prove they never reached an output. Values are held in memory only and never written."""
    ids: set[str] = set()
    for pat in patterns:
        for f in root.rglob(pat):
            try:
                head = f.read_text(encoding="utf-8", errors="ignore")[:1200]
            # Accepted: an unreadable header line is skipped, not fatal to the scan.
            except Exception:  # nosec B112
                continue
            for _field, value in _ID_HEADER_RE.findall(head):
                v = value.strip()
                if len(v) < 3:
                    continue
                ids.add(v)
                # also the constituent word/number tokens (a surname alone must not leak either)
                for tok in re.split(r"[^\w]+", v):
                    if len(tok) >= 4 and not tok.isdigit() or tok.isdigit() and len(tok) >= 5:
                        ids.add(tok)
    return ids


def verify_outputs_phi_free(out_dir: Path, identifiers: set[str]) -> dict:
    """Scan every file under out_dir for any source identifier. Returns a verdict dict; the caller
    fails loudly on a hit. This is the 'grep your own outputs before declaring done' guarantee (C2)."""
    hits: list[str] = []
    scanned = 0
    lowered = {i.lower() for i in identifiers if i}
    for f in out_dir.rglob("*"):
        if not f.is_file():
            continue
        scanned += 1
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        # Accepted: an unmatched identifier is skipped, not fatal to the scan.
        except Exception:  # nosec B112
            continue
        for ident in lowered:
            if ident in text:
                hits.append(f"{f.name}::<identifier len={len(ident)}>")  # never echo the value
                break
    return {"files_scanned": scanned, "identifiers_checked": len(lowered),
            "clean": not hits, "hits": hits}


def _structure_of(r: dict) -> str:
    return str(r.get("canonical_name") or r.get("Structure_Canonical") or r.get("structure") or "")


def _accumulate(cfg: RunnerConfig, pseudonym: str, rec: PatientRecord, harvest: dict,
                accum: dict[str, list[dict]], reason_counts: dict[str, int]) -> None:
    """Build PHI-free cohort rows from one patient's harvested engine rows. Deterministic order."""
    site_written = False
    for r in harvest.get("tcp", []):
        struct = _structure_of(r)
        for key in sorted(k for k in r if k.startswith("TCP_") and not k.endswith(("_mean", "_range"))):
            accum["tcp_results.csv"].append({"pseudonym": pseudonym, "structure": struct,
                "model": key[4:], "tcp": r.get(key, "")})
            accum["benchmark.csv"].append({"pseudonym": pseudonym, "structure": struct,
                "endpoint": "tcp", "model": key[4:], "value": r.get(key, "")})
        accum["physical_metrics.csv"].append({"pseudonym": pseudonym, "structure": struct,
            "category": r.get("target_type", ""), "volume_cc": r.get("total_volume_cc", ""),
            "Dmean_gy": r.get("Dmean_gy", ""), "Dmax_gy": r.get("Dmax_gy", ""),
            "D2_gy": r.get("D2_gy", ""), "D98_gy": r.get("D98_gy", "")})
        accum["dvh_summary.csv"].append({"pseudonym": pseudonym, "structure": struct,
            "volume_cc": r.get("total_volume_cc", ""), "Dmean_gy": r.get("Dmean_gy", ""),
            "Dmax_gy": r.get("Dmax_gy", ""), "dvh_mode": r.get("extraction_mode", rec.dvh_mode)})
        accum["structure_mapping.csv"].append({"pseudonym": pseudonym, "roi_number": r.get("roi_number", ""),
            "raw_name": r.get("raw_name", ""), "canonical": struct, "category": r.get("target_type", ""),
            "confidence": r.get("site_confidence", ""), "status": "mapped"})
        if r.get("target_type") in ("PTV", "GTV", "CTV"):
            accum["plan_quality.csv"].append({"pseudonym": pseudonym, "target": struct,
                "HI": r.get("HI", ""), "CI": r.get("CI", ""), "GI_pct": r.get("GI_pct", "")})
        if not site_written:
            accum["site_detection.csv"].append({"pseudonym": pseudonym, "site": r.get("site", cfg.site or ""),
                "confidence": r.get("site_confidence", ""), "evidence": str(r.get("site_evidence", ""))})
            site_written = True
    for r in harvest.get("ntcp", []):
        struct = _structure_of(r)
        # OAR dose metrics must reach physical_metrics/dvh_summary too. Cohorts whose only structures
        # are OARs (e.g. a parotid-only TPS export) have NO TCP rows by design, so populating those
        # tables from TCP rows alone left them empty even though the DVH was extracted correctly.
        accum["physical_metrics.csv"].append({"pseudonym": pseudonym, "structure": struct,
            "category": "OAR", "volume_cc": r.get("total_volume_cc", ""),
            "Dmean_gy": r.get("Dmean_gy", ""), "Dmax_gy": r.get("Dmax_gy", ""),
            "D2_gy": r.get("D2_gy", ""), "D98_gy": r.get("D98_gy", "")})
        accum["dvh_summary.csv"].append({"pseudonym": pseudonym, "structure": struct,
            "volume_cc": r.get("total_volume_cc", ""), "Dmean_gy": r.get("Dmean_gy", ""),
            "Dmax_gy": r.get("Dmax_gy", ""), "dvh_mode": r.get("extraction_mode", rec.dvh_mode)})
        # Phase-3 applicability guard: record whether the ROI's definition matches what the model's
        # published parameters assume (e.g. a side-less "Parotid" silently canonicalised to Parotid_R
        # is NOT a verified single gland). Recorded per row so the hazard is visible, not hidden.
        try:
            from radiobiology.ntcp_applicability import evaluate_ntcp_applicability
            verdict = evaluate_ntcp_applicability(struct, "OAR", str(r.get("raw_name", struct)))
            definition_ok, codes = verdict["definition_ok"], ";".join(verdict["reason_codes"])
        except Exception:
            definition_ok, codes = "", ""
        for key in sorted(k for k in r if k.startswith("NTCP_")):
            model = key[5:]
            u = r.get(f"uNTCP_{model}") or {}
            if not isinstance(u, dict):
                u = {}
            accum["ntcp_results.csv"].append({"pseudonym": pseudonym, "structure": struct,
                "model": model, "ntcp": r.get(key, ""), "site_params_key": r.get("site_params_key", ""),
                "definition_ok": definition_ok, "reason_codes": codes,
                "uNTCP_mean": u.get("mean", ""), "uNTCP_sd": u.get("sd", ""),
                "uNTCP_p5": u.get("p5", ""), "uNTCP_p95": u.get("p95", ""),
                "uNTCP_n": u.get("n_valid", "")})
            accum["benchmark.csv"].append({"pseudonym": pseudonym, "structure": struct,
                "endpoint": "ntcp", "model": key[5:], "value": r.get(key, "")})
    # Dosiomics (ADVANCED): the dose3d module attaches dosio_<organ>_<feature> keys to NTCP rows.
    # Emit them as long-form ML features so they are machine-readable, not buried in the harvest.
    for r in harvest.get("ntcp", []) + harvest.get("tcp", []):
        for k, v in r.items():
            if k.startswith("dosio_"):
                accum["ML_features.csv"].append({"pseudonym": pseudonym, "feature": k, "value": v})

    accum["patient_features.csv"].append({"pseudonym": pseudonym, "site": cfg.site or "",
        "n_structures": rec.n_structures, "n_mapped": rec.n_structures, "n_unmapped": rec.n_missing,
        "dvh_mode": rec.dvh_mode, "plan_selected": rec.plan_selected, "degraded_mode": rec.degraded_mode})
    for code in rec.warnings:
        accum["QA.csv"].append({"pseudonym": pseudonym, "reason_code": code, "detail": ""})
        reason_counts[code] = reason_counts.get(code, 0) + 1
    if rec.status == "failed":
        accum["failures.csv"].append({"pseudonym": pseudonym, "stage": "process",
            "reason_code": rec.failure_reason, "detail": ""})


# --------------------------------------------------------------------- orchestration

def run_cohort(cfg: RunnerConfig, progress: bool = False) -> dict:
    """Run a whole cohort. Resumable, idempotent, deterministic. Returns the cohort summary dict."""
    start_utc = datetime.now(timezone.utc).isoformat()
    repo_root = Path(__file__).resolve().parents[2]
    out = Path(cfg.output_root) / cfg.validation / cfg.cohort
    subdirs = {name: out / name for name in ("PatientLevel", "CohortLevel", "Figures", "QA", "Logs")}
    for d in subdirs.values():
        d.mkdir(parents=True, exist_ok=True)
    map_dir = Path(cfg.pseudonym_map_dir) if cfg.pseudonym_map_dir else out.parent / "_pseudonym_maps"
    tmp_root = out / ".staging"
    tmp_root.mkdir(parents=True, exist_ok=True)

    units = _discover_units(cfg)
    if cfg.limit:
        units = units[: cfg.limit]
    mapping = _load_or_build_pseudonym_map(cfg, [k for k, _ in units], map_dir)

    accum: dict[str, list[dict]] = {name: [] for name in COHORT_CSVS}
    records: list[PatientRecord] = []
    reason_counts: dict[str, int] = {}

    for i, (raw_key, unit) in enumerate(units, 1):
        pseudonym = mapping[raw_key]
        pdir = subdirs["PatientLevel"] / pseudonym
        done_marker = pdir / "_COMPLETED.json"
        harvest_path = pdir / "harvest.json"

        if done_marker.exists() and harvest_path.exists():  # 5.2 resumable + idempotent
            rec = PatientRecord(**json.loads((subdirs["Logs"] / f"{pseudonym}.json").read_text("utf-8")))
            harvest = json.loads(harvest_path.read_text("utf-8"))
            cached = True
        else:
            pdir.mkdir(parents=True, exist_ok=True)
            rec, harvest = _process_patient(cfg, pseudonym, unit, pdir, tmp_root)
            harvest_path.write_text(json.dumps(harvest), encoding="utf-8")
            (subdirs["Logs"] / f"{pseudonym}.json").write_text(
                json.dumps(asdict(rec), indent=2), encoding="utf-8")
            if rec.status in ("completed", "skipped"):
                done_marker.write_text(json.dumps({"status": rec.status}), encoding="utf-8")
            cached = False

        records.append(rec)
        _accumulate(cfg, pseudonym, rec, harvest, accum, reason_counts)
        if progress:
            tag = "cached" if cached else f"{rec.status} ({rec.processing_seconds}s)"
            print(f"  [{i}/{len(units)}] {pseudonym}: {tag}, {rec.n_structures} structures", flush=True)

    # cohort summary (5.7)
    counts = {s: sum(1 for r in records if r.status == s) for s in ("completed", "skipped", "failed")}
    accum["cohort_summary.csv"] = (
        [{"metric": "attempted", "value": len(records)}]
        + [{"metric": k, "value": v} for k, v in counts.items()]
        + [{"metric": f"reason:{c}", "value": n} for c, n in sorted(reason_counts.items())]
    )

    # write all 16 CSVs (even empty) with stable columns
    for name, columns in COHORT_CSVS.items():
        _write_csv(subdirs["CohortLevel"] / name, columns, accum.get(name, []))

    # run manifest (5.5)
    manifest = {
        "cohort": cfg.cohort, "validation": cfg.validation, "input_kind": cfg.input_kind,
        "engine_version": (repo_root / "VERSION.txt").read_text(encoding="utf-8").splitlines()[0]
        if (repo_root / "VERSION.txt").exists() else "unknown",
        "git_commit": _git_commit(repo_root), "config_hash": _config_hash(cfg), "seed": cfg.seed,
        "python": platform.python_version(), "packages": _pkg_versions(),
        "start_utc": start_utc, "end_utc": datetime.now(timezone.utc).isoformat(),
        "input_inventory": {"n_units_discovered": len(units), "n_processed": len(records)},
        "per_patient_status": {r.pseudonym: r.status for r in records},
        "pseudonym_map_location": str(map_dir.resolve()),
        "note": "No PHI in this tree; raw IDs live only in the gitignored pseudonym map above.",
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(tmp_root, ignore_errors=True)

    # --- C2 self-verification: prove no source identifier reached any output -------------------
    phi = {"skipped": True}
    if cfg.input_kind == "dvh_txt":
        idents = harvest_source_identifiers(Path(cfg.input_root), (cfg.file_pattern,))
        phi = verify_outputs_phi_free(out, idents)
        (subdirs["QA"] / "phi_scan.json").write_text(
            json.dumps({k: v for k, v in phi.items() if k != "hits"} |
                       {"n_hits": len(phi.get("hits", []))}, indent=2), encoding="utf-8")
        if not phi["clean"]:
            logger.error("PHI SCAN FAILED for cohort %s: %d file(s) contain a source identifier",
                         cfg.cohort, len(phi["hits"]))
    return {"cohort": cfg.cohort, "output": str(out), **counts, "attempted": len(records),
            "phi_scan_clean": phi.get("clean", None)}


def _pkg_versions() -> dict:
    out = {}
    for m in ("numpy", "pandas", "scipy", "pydicom", "sklearn", "torch"):
        try:
            out[m] = __import__(m).__version__
        except Exception:
            out[m] = "absent"
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    import contextlib
    import sys

    for stream in (sys.stdout, sys.stderr):  # UTF-8 console for PowerShell (Phase 2 T7)
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    p = argparse.ArgumentParser(
        prog="rbgyanx-cohort",
        description="Run one rbGyanX cohort: resumable, idempotent, deterministic, pseudonymised.",
    )
    p.add_argument("--input-root", required=True, type=Path, help="Folder of DICOM-RT or TPS DVH text")
    p.add_argument("--cohort", required=True, help="Cohort name (also the pseudonym prefix)")
    p.add_argument("--output-root", required=True, type=Path, help="Root for the Outputs/ tree")
    p.add_argument("--validation", choices=["InternalValidation", "ExternalValidation"],
                   default="ExternalValidation")
    p.add_argument("--input-kind", choices=["dicom", "dvh_txt"], default="dicom")
    p.add_argument("--limit", type=int, default=None, help="Process at most N patients")
    p.add_argument("--site", default=None, help="Override site detection (e.g. HN, LUNG)")
    p.add_argument("--mode", choices=["basic", "advanced"], default="basic")
    p.add_argument("--endpoint", choices=["tcp", "ntcp", "both"], default="both")
    p.add_argument("--file-pattern", default="*.txt",
                   help="dvh_txt only: which files form the cohort (e.g. '*PlanSumwithKIM.txt')")
    p.add_argument("--dose-per-fraction", type=float, default=2.0,
                   help="TPS text: dose per fraction when the export omits it "
                        "(e.g. 7.25 for a 36.25 Gy / 5 fraction SBRT prescription)")
    p.add_argument("--n-mc", type=int, default=1000, help="advanced: uNTCP Monte-Carlo draws")
    p.add_argument("--outcome-csv", type=Path, default=None,
                   help="advanced: outcome labels; REQUIRED by the engine's ML/XAI branch")
    p.add_argument("--preserve-structure-canonical", action="store_true",
                   help="TPS text: keep the ROI's true canonical (Parotid_R, Rectum, ...) instead of "
                        "coercing to a target type, so classical NTCP can be applied to OAR exports")
    p.add_argument("--pseudonym-map-dir", type=Path, default=None,
                   help="Where the raw-ID↔pseudonym map lives — MUST be OUTSIDE the repo (gitignored)")
    args = p.parse_args(argv)

    cfg = RunnerConfig(
        input_root=args.input_root, cohort=args.cohort, output_root=args.output_root,
        validation=args.validation, input_kind=args.input_kind, limit=args.limit, site=args.site,
        mode=args.mode, endpoint=args.endpoint, pseudonym_map_dir=args.pseudonym_map_dir,
        file_pattern=args.file_pattern,
        preserve_txt_canonical=args.preserve_structure_canonical,
        n_mc=args.n_mc, outcome_csv=args.outcome_csv,
        dose_per_fraction=args.dose_per_fraction,
    )
    print(f"[rbGyanX] cohort={cfg.cohort} kind={cfg.input_kind} → {cfg.output_root}", flush=True)
    summary = run_cohort(cfg, progress=True)
    print(f"[rbGyanX] done: {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
