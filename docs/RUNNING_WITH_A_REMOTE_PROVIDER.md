# Running rbGyanX with a remote provider (Kimi K3)

Read this **before** starting a cohort run, not after. The one thing to know going in:

> **Kimi K3 is a remote provider. It will never receive patient-level data.** Patient-level
> explanation is refused on Kimi. That is the capability matrix working correctly — it is not a
> bug, and it is not something to work around.

Everything else in the tool still works on real cohorts. Only the assistant's view of
patient-level detail is restricted, and only when the provider is remote.

---

## Check before you start

```bash
python scripts/ai_capability_report.py --provider kimi
```

This reads the **implemented** matrix, not this document, so it cannot drift from what the code
does. Run it once before the run and you will not be surprised mid-way.

## What Kimi K3 is granted and denied

From the implemented matrix, on a source install:

| Capability | Kimi K3 | Why |
|---|---|---|
| explain aggregate results | **GRANTED** | aggregate results carry no patient identifiers |
| literature quick-compare | **GRANTED** | compares published reference values, not patient data |
| read source code | **GRANTED** | source is present and carries no patient data |
| modify source code | **GRANTED** | edits are reviewed, verified and auto-reverted on failure |
| run tests | **GRANTED** | a test run needs a dev environment; output is scrubbed |
| run on synthetic data | **GRANTED** | synthetic data contains no patient information |
| read error / traceback | **GRANTED, scrubbed** | the traceback is scrubbed before transmission |
| **explain patient-level results** | **DENIED** | requires a local on-machine provider |
| **run on real patient data** | **DENIED** | requires a local on-machine provider |

Seven granted, two denied. The two denials are the whole point of the design.

### What "denied" looks like in practice

You ask the assistant to explain a specific patient's parotid NTCP while Kimi is selected. You get
the **aggregate** summary plus an explicit note:

> patient-level detail withheld: this capability requires a local on-machine provider; the
> selected provider is remote

It does not silently give you less than you asked for, and it does not fail. If you need the
patient-level answer, switch provider (below) and ask again.

### What still works on real cohorts

The engine itself is unaffected — TCP/NTCP/UTCP, DICOM/DVH ingest, validation, reporting and
export all run exactly as they do without the assistant. **The assistant never computes, adjusts
or influences a TCP, NTCP or UTCP value in any configuration.** What a remote provider changes is
only what the *assistant* may look at.

With Kimi selected you can still:

- have aggregate run results explained (cohort counts, model ranges, dose statistics);
- run literature quick-compare against the reference packs;
- have source code read and edits proposed, verified and auto-reverted;
- run the test suite, with output scrubbed before it is transmitted;
- run against the shipped synthetic data or a directory you have declared synthetic;
- have a traceback read, reconstructed and scrubbed.

## Using the local provider for the patient-level parts

Nothing else has to change — same run, same data, same window. Select **Local
(Ollama / llama.cpp)** in the panel's provider dropdown, or:

```bash
python scripts/ai_capability_report.py --provider local
```

With a local provider on loopback, all nine capabilities are granted, including patient-level
explanation and running against real patient data.

**A local provider means loopback, not "a machine you trust".** If you point the Local preset at
a LAN box — say `http://192.168.1.5:11434/v1` — it is treated as **remote**, because the data does
leave this machine. The send dialog will say so, naming the endpoint. That is deliberate.

A practical pattern: keep Kimi selected for code, tests and literature work, and switch to the
local provider for the patient-level questions. The audit log records which provider each
transmission went to, so the split is visible afterwards.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `MOONSHOT_API_KEY` *or* `KIMI_API_KEY` | Kimi credential. Read from the environment only — never stored, never logged. Either name works; `MOONSHOT_API_KEY` is checked first. |
| `RBGYANX_AI_DISABLE_REMOTE=1` | Institutional kill switch. Removes **every** remote provider from the registry before anything sees it. Cannot be re-enabled from the interface. |
| `RBGYANX_AUDIT_DIR` | Where the audit log is written. Defaults to the user config directory (below). |
| `RBGYANX_STRUCTURE_LABELS` | Your department's structure-label vocabulary, if labels are not English. See `docs/AI_ASSISTANT_DESIGN.md`. |
| `RBGYANX_SITE_CONFIG` | Path to a site config file, an alternative to the kill-switch variable. |

```bash
export MOONSHOT_API_KEY="..."            # Windows: set MOONSHOT_API_KEY=...
export RBGYANX_AUDIT_DIR="D:/run_2026_08/audit"
```

Setting `RBGYANX_AUDIT_DIR` to a per-run directory is worth doing: it keeps the run's evidence
together and separate from any earlier work.

## The audit log

**Location** (unless `RBGYANX_AUDIT_DIR` overrides it):

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\rbGyanX\ai_audit.jsonl` |
| Linux | `$XDG_CONFIG_HOME/rbgyanx/ai_audit.jsonl`, else `~/.config/rbgyanx/ai_audit.jsonl` |
| macOS | `~/Library/Application Support/rbGyanX/ai_audit.jsonl` |

Deliberately **not** in the repo — a clone must not carry another site's audit trail — and not in
a temp directory, because a trail that evaporates on reboot is not a trail.

One record per transmission and per guard refusal: timestamp, provider, remote flag, install type,
capability, outcome, byte count, redaction count, and a SHA-256 of the payload. **Never the
payload.** There is no field in the record that could hold a prompt, a response or patient data.

It is on by default and needs no configuration. Rotation is automatic at 2 MB, keeping five
generations.

### Exporting it afterwards

```bash
python scripts/export_ai_audit.py                                   # summary to stdout
python scripts/export_ai_audit.py -o run_audit.csv                  # ...and a CSV
python scripts/export_ai_audit.py --include-rotated -o all.csv      # include rotated files
```

The summary reports transmissions by provider, by capability and by install type, remote versus
local, guard refusals by capability, bytes transmitted, identifiers redacted, and how many
payloads were repeats. It aggregates and cannot enrich — every column is a field the log already
holds.

For a write-up, `run_audit.csv` plus the printed summary is the evidence base: it shows what was
sent, to whom, under which capability, and how often a guard refused.

---

## Before the run — checklist

1. `python scripts/ai_capability_report.py --provider kimi` — confirm the table above.
2. `echo $MOONSHOT_API_KEY` — confirm the key is set (`ready to send: yes`).
3. Set `RBGYANX_AUDIT_DIR` to a per-run directory.
4. If your structure labels are not English, declare them via `RBGYANX_STRUCTURE_LABELS`,
   or expect refusals when tracebacks and test output mention them.
5. Decide the split: Kimi for code/tests/literature, local for patient-level questions.
6. Confirm the assistant is enabled — it is **off by default** (ADVANCED mode, then the
   "Enable assistant tools" checkbox).

## After the run

1. `python scripts/export_ai_audit.py -o run_audit.csv`
2. Keep `run_audit.csv` with the run outputs.
3. Any literature comparison marked **unverified** — including every entry in the shipped
   QUANTEC pack, which is awaiting review — must be checked against the primary source before it
   goes into a manuscript. The export carries that notice, and the rows stay marked.

## Two things that will look like bugs and are not

**"The assistant refused to explain patient 12 on Kimi."** Correct. Remote providers never receive
patient-level data. Switch to the local provider.

**"It refused to send a traceback that mentions our structure names."** The scrubber could not
confidently clean text containing labels it does not recognise, so it refused rather than sending
a best-effort payload. Declare your vocabulary once via `RBGYANX_STRUCTURE_LABELS` and it will
stop. The refusal message says so.
