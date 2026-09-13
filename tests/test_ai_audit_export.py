"""
Audit-log export (phase F).

The exporter is what turns a run into analysable evidence. Its one hard property is that it
aggregates and does not enrich: the log is PHI-free by construction, and that is only worth
something if the tooling around it cannot reintroduce what the log deliberately omits.
"""

from __future__ import annotations

import csv
import importlib.util
import json

import pytest
from rbgyanx.ai.audit import audit_path, record_refusal, record_transmission
from rbgyanx.ai.scrubber import install_root


def _module():
    spec = importlib.util.spec_from_file_location(
        "export_ai_audit", install_root() / "scripts" / "export_ai_audit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


export_ai_audit = _module()


@pytest.fixture()
def log(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))
    for _ in range(3):
        record_transmission(
            provider="kimi",
            remote=True,
            install_type="source",
            capability="explain aggregate results",
            payload="a question about a run",
        )
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain patient-level results",
        payload="a patient-level question",
        findings_redacted=2,
    )
    record_refusal(
        provider="kimi",
        remote=True,
        install_type="source",
        capability="read error / traceback",
    )
    return audit_path()


# ------------------------------------------------------------------------- reading


def test_it_reads_every_record(log):
    assert len(export_ai_audit.load_records(log)) == 5


def test_a_truncated_final_line_does_not_lose_the_rest(log):
    with open(log, "a", encoding="utf-8") as handle:
        handle.write('{"provider": "kimi", "outc')
    assert len(export_ai_audit.load_records(log)) == 5


def test_rotated_generations_can_be_included(log, tmp_path):
    rotated = tmp_path / "ai_audit.jsonl.1"
    rotated.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "provider": "claude",
                "remote": True,
                "install_type": "frozen",
                "capability": "literature quick-compare",
                "outcome": "sent",
                "payload_bytes": 10,
                "findings_redacted": 0,
                "payload_sha256": "0" * 64,
                "schema": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert len(export_ai_audit.load_records(log)) == 5
    assert len(export_ai_audit.load_records(log, include_rotated=True)) == 6


def test_a_missing_log_exits_non_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))
    assert export_ai_audit.main(["--log", str(tmp_path / "nope.jsonl")]) == 1
    assert "No audit log" in capsys.readouterr().err


# ----------------------------------------------------------------------------- CSV


def test_csv_has_one_row_per_record(log, tmp_path):
    out = tmp_path / "audit.csv"
    export_ai_audit.write_csv(export_ai_audit.load_records(log), out)
    with open(out, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5


def test_csv_columns_are_exactly_the_declared_ones(log, tmp_path):
    """A new log field must be added to COLUMNS deliberately, not leak in because it exists."""
    out = tmp_path / "audit.csv"
    export_ai_audit.write_csv(export_ai_audit.load_records(log), out)
    with open(out, encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    assert header == list(export_ai_audit.COLUMNS)


def test_csv_carries_the_outcome(log, tmp_path):
    out = tmp_path / "audit.csv"
    export_ai_audit.write_csv(export_ai_audit.load_records(log), out)
    with open(out, encoding="utf-8", newline="") as handle:
        outcomes = [row["outcome"] for row in csv.DictReader(handle)]
    assert outcomes.count("refused") == 1
    assert outcomes.count("sent") == 4


def test_an_unexpected_field_is_not_exported(log, tmp_path):
    """The exporter aggregates; it does not carry through whatever it happens to find."""
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"provider": "kimi", "prompt_text": "PatientID 004512237"}) + "\n")
    out = tmp_path / "audit.csv"
    export_ai_audit.write_csv(export_ai_audit.load_records(log), out)
    text = out.read_text(encoding="utf-8")
    assert "prompt_text" not in text
    assert "004512237" not in text


# ------------------------------------------------------------------------- summary


def test_summary_counts_sends_and_refusals(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "transmissions sent      : 4" in text
    assert "guard refusals          : 1" in text


def test_summary_splits_remote_from_local(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "of which remote       : 3" in text
    assert "of which local        : 1" in text


def test_summary_breaks_down_by_provider_capability_and_install(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "Transmissions by provider" in text
    assert "Transmissions by capability" in text
    assert "Transmissions by install type" in text
    assert "kimi" in text and "local" in text
    assert "explain aggregate results" in text


def test_summary_reports_refusals_by_capability(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "Refusals by capability" in text
    assert "read error / traceback" in text


def test_summary_counts_redactions(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "identifiers redacted    : 2" in text


def test_summary_notes_repeat_payloads(log):
    """Three identical sends share a digest; the summary says so without storing them."""
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "distinct payloads" in text
    assert "repeat transmission" in text


def test_an_empty_log_summarises_without_crashing():
    assert "No AI transmissions recorded." in export_ai_audit.summarise([])


def test_summary_states_that_it_is_aggregate_only(log):
    text = export_ai_audit.summarise(export_ai_audit.load_records(log))
    assert "aggregate only" in text
    assert "no prompts" in text


# ------------------------------------------------------------- it cannot enrich


def test_the_exporter_never_reads_content_it_was_not_given(log):
    """Structural guard: the script must not learn to open anything but the log."""
    source = (install_root() / "scripts" / "export_ai_audit.py").read_text(encoding="utf-8")
    for forbidden in ("summarise_run", "scrub(", "llm_client", "http_transport", "urllib"):
        assert forbidden not in source, f"the exporter must not reference {forbidden}"


def test_no_payload_can_appear_in_any_output(log, tmp_path):
    out = tmp_path / "audit.csv"
    records = export_ai_audit.load_records(log)
    export_ai_audit.write_csv(records, out)
    combined = out.read_text(encoding="utf-8") + export_ai_audit.summarise(records)
    for token in ("a question about a run", "a patient-level question"):
        assert token not in combined


# ----------------------------------------------------------------------------- CLI


def test_cli_writes_csv_and_prints_a_summary(log, tmp_path, capsys):
    out = tmp_path / "run.csv"
    assert export_ai_audit.main(["--log", str(log), "-o", str(out)]) == 0
    captured = capsys.readouterr().out
    assert out.exists()
    assert "Wrote 5 record(s)" in captured
    assert "rbGyanX AI audit summary" in captured


def test_cli_quiet_suppresses_the_summary(log, tmp_path, capsys):
    out = tmp_path / "run.csv"
    assert export_ai_audit.main(["--log", str(log), "-o", str(out), "--quiet"]) == 0
    assert "rbGyanX AI audit summary" not in capsys.readouterr().out


def test_cli_defaults_to_the_configured_log(log, capsys):
    assert export_ai_audit.main([]) == 0
    assert "transmissions sent" in capsys.readouterr().out
