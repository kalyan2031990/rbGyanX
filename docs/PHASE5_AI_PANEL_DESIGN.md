# Phase 5 — AI panel: data-flow & safety design (for approval)

**Status:** proposed — no network code written yet. This document is the gate: I implement
the live-request path only after you approve the boundary below.

Adopts the UMLBot pattern (Godwin & Melvin, *SoftwareX* 102789): one configurable
OpenAI-compatible LLM abstraction + a chat panel with self-correction/retry. ADVANCED-only,
opt-in, off by default.

---

## 1. The PHI boundary (what may and may not leave the machine)

The single most important rule: **no real patient data ever reaches an API.** Enforced in
layers, not by trust.

**MAY be sent** (only after passing the guard):
- The user's own typed text (their question / QA note draft).
- Derived, **aggregate** outputs: model names, NTCP/TCP values, AUCs, cohort *counts*,
  parameter values (TD50, m, γ). These are numbers about a *model*, not a person.
- Synthetic / example data shipped with the app.

**NEVER sent — blocked by construction:**
- Any per-patient row, DVH file contents, structure set, or DICOM field.
- Patient IDs, names, MRNs, dates of birth, accession numbers, file paths that embed IDs.
- The raw run result object. The panel can only see a **derived, aggregated summary** the
  app builds explicitly — it has no handle to `RunResult.structures[*].patient_id` etc.

## 2. Defence in depth

```
user text ─┐
           ├─► [1] context builder ──► [2] PHI guard ──► [3] LLM client ──► API
derived ───┘     (aggregate only,       (regex + heuristic     (opt-in, key
aggregates        never per-patient)      block/redact;          from env only)
                                          fails CLOSED)
```

- **[1] Context builder** — assembles the prompt from an allow-list of aggregate fields.
  Per-patient structures are never passed in. This is the primary control; the guard is a
  backstop, not the only line.
- **[2] PHI guard** — a pure, heavily-tested function that scans the *final* outgoing text for
  PHI patterns (MRN-like digit runs, DOB/date patterns, name-like `Last, First`, DICOM UID
  patterns, filesystem paths, `PatientID`/`PatientName` tokens). On a hit it **fails closed**:
  the request is blocked and the user told why. (Or redact-and-warn — see decision D2.)
- **[3] LLM client** — OpenAI-compatible (`base_url` + `model` + `api_key`). Key comes from
  env/config only, never committed, never logged. Feature disabled unless the user turns it on
  *and* a key is present. Self-correction/retry with capped attempts.

## 3. No persistence

- Prompts/responses are **never written to disk or logs** when they contain clinical content.
- No prompt cache. Chat history lives in memory for the session only and is cleared on close.
- The data-safety notice is shown in the panel every session.

## 4. Gating (already in place)

- `mode_controller.CAPABILITIES["ai_integration"]` → `requires_mode=ADVANCED`;
  `CAPABILITY_EXPOSURE[BASIC]["ai_integration"] = False`. **BASIC/clinic can never enable it.**
- `ui_policy.UiFeature.AI_PANEL` → `ai_integration`. The Qt panel is only built when
  `UiPolicy.allows(AI_PANEL)`.

## 5. Scope of the assistant (explanation-only)

Explains radiobiology outputs, drafts QA notes, assists with code, and can regenerate the
editable pipeline/architecture diagram (inspect source → regenerate). Per the capability
description: **no recommendations, no rankings, no automated actions, no per-patient advice.**

## 6. Proposed build order

- **5-A (no live network):** PHI guard + context builder + LLM-client abstraction with the HTTP
  call behind an interface and a `NullTransport` default; opt-in/gating tests; PHI-guard tests.
  Nothing can actually reach the network in this slice.
- **5-B (live path):** wire a real HTTP transport + the Qt chat panel; user must explicitly
  enable the feature and press send. Only built after 5-A + your approval of this doc.

## 7. Decisions — RESOLVED (owner, 2026-07-25)

- **D1 — providers:** three selectable presets over one OpenAI-compatible core —
  **Local** (Ollama/llama.cpp, localhost), **Claude** (Anthropic), **Kimi** (Moonshot).
- **D3 — default:** enabled in ADVANCED **when an API key is present** (otherwise off).

- **D2 — guard behaviour: WARN, NEVER BLOCK — including for remote providers.**
  This is an **explicit, informed policy change** made by the project owner on 2026-07-25,
  after being shown that it means **real patient data (PHI) can be transmitted to third-party
  APIs (Claude, Kimi)**, where it may be logged or retained by the provider, and that this is
  irreversible once sent. It **overrides** the earlier hard constraint in
  `docs/CLAUDE_CODE_FIX_AUDIT_GUI.md` ("NEVER send real patient data to any API") for the
  remote path.

  Safeguards that remain in force under this policy:
  - The PHI guard still **runs on every outgoing request** and surfaces exactly what it matched
    (category + location) as an on-screen caution. It informs; it does not block.
  - **Per-send confirmation** for remote providers: the dialog names the provider and states
    "this sends the shown text, which may include real patient data, over the internet."
  - **No persistence**: prompts/responses are never written to disk, logs, or any cache — the
    "save nothing" requirement is absolute and independent of the transmission policy.
  - **Local** endpoint: real data flows freely (never leaves the machine); the same guard runs
    as an FYI. This is the recommended setting for PHI work.
  - **BASIC/clinic can never enable any of this** (capability gating, unchanged).

  Rationale recorded so the decision is auditable and is not silently reverted by later work.
