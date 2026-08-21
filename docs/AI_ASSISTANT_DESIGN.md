# Governed AI assistant — design, threat model and boundaries

**Status: experimental. ADVANCED-only, opt-in, off by default, absent entirely in BASIC.**

rbGyanX is a decision-**support** framework distributed to medical physicists and radiobiology
researchers. It is general-purpose software: it is not built for one user, one institution or
one protocol, so every rule below has to hold for a stranger who installs it.

The assistant **explains outputs the deterministic engine has already produced**. It never
computes, adjusts or influences a TCP, NTCP or UTCP value, and there is no code path from the
tool layer into the numeric core. A test asserts the tool modules import nothing from
`engine/radiobiology`.

---

## 1. The capability matrix

Capability is granted on two axes, both enforced in code (`rbgyanx/ai/capability.py`) as a
literal table rather than as scattered conditionals.

| Capability | FROZEN+remote | FROZEN+local | SOURCE+remote | SOURCE+local | CI |
|---|---|---|---|---|---|
| explain aggregate results | yes | yes | yes | yes | no |
| explain patient-level results | **NO** | yes | **NO** | yes | no |
| literature quick-compare | yes | yes | yes | yes | no |
| read source code | no | no | yes | yes | no |
| modify source code | no | no | yes | yes | no |
| run tests | no | no | yes | yes | no |
| run on synthetic data | no | no | yes | yes | no |
| run on real patient data | **NO** | **NO** | **NO** | yes | no |
| read error / traceback | yes, scrubbed | yes, raw | yes, scrubbed | yes, raw | no |

All 45 cells are asserted individually in `tests/test_ai_capability.py`, with the expected value
written out as a literal. The tests deliberately do not loop over the table: a test that reads
the table to check the table proves only that the table equals itself.

Every cell carries a user-facing reason string naming the condition that failed, so the panel
can say *why* something is unavailable instead of hiding it.

### Axis 1 — data locality

A provider is **remote** when using it would move bytes off this machine. Remote providers never
receive patient data, under any capability, in any install type.

`Provider.remote` is a declaration, not a guarantee, because `AiConfig.base_url` is
user-overridable. A preset flagged local but pointed at `https://elsewhere.example/v1` would
otherwise be rated safe for patient data. So `effective_remote()` requires **both** the local
flag **and** a resolved URL on loopback (`localhost`, `127.0.0.0/8`, `::1`).

There is no DNS resolution: a name that merely resolves to loopback today is not a guarantee,
and resolving would be network I/O in what must stay a pure function. A LAN endpoint — an Ollama
box at `192.168.1.5` — is therefore **remote**, which is correct: the data does leave the machine.

### Axis 2 — install type

Detected at runtime, never asked of the user, most-restrictive-first:

1. **CI** — any of `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, `JENKINS_URL`, and five more. Wins over
   everything, including `sys.frozen`. The assistant is disabled outright.
2. **FROZEN** — `sys.frozen` is set. A PyInstaller/Inno binary has no git, no venv and no pytest.
3. **SOURCE** — a `.git` directory is present.

A plain `pip install` (no git, not frozen) is classified **FROZEN**, the more restrictive of the
two: it has no test suite to run and no source tree to edit, so granting SOURCE capabilities
would grant things that cannot work anyway.

### Axis 3 — institutional kill switch

Set **either**:

```bash
RBGYANX_AI_DISABLE_REMOTE=1
```

**or** in a site config file — `%PROGRAMDATA%\rbGyanX\site.yaml`, `/etc/rbgyanx/site.yaml`, or a
path in `RBGYANX_SITE_CONFIG`:

```yaml
ai:
  disable_remote: true
```

Every remote provider is then removed from the registry **before anything else sees it**, so it
is not selectable rather than merely refused at send time. Most restrictive source wins, and an
unreadable site config is not treated as permission to enable remote. `is_allowed()` independently
refuses a remote provider that reaches it anyway.

IT departments can enforce this without editing code, and it cannot be re-enabled from the UI.

---

## 2. PHI handling

Two guards with deliberately different contracts, both retained:

| | `phi_guard.py` | `scrubber.py` |
|---|---|---|
| Governs | text the **user** typed and chose to send | text the assistant **forwards on the user's behalf** |
| On detection | warns, never blocks (2026-07-25 decision, unchanged) | **fails closed** |
| Rationale | a human is reading every byte before it goes | no human is |

### Why `confident` exists

A deny-list cannot prove the absence of PHI. Patient names are unbounded strings: a folder
`\\nas\onc\Mueller_A` or a structure label `Parotid_L_Smith` matches no pattern anyone can write
in advance. So `scrub()` does two things:

1. redacts everything it *can* recognise; then
2. asks whether anything **unrecognisable but risky** survived, and if so reports
   `confident=False`.

`scrub_for_transmission(text, remote=True)` raises `ScrubRefused` on an unconfident scrub. Fail
closed means **refuse**, never "send a smaller payload".

### Tracebacks are reconstructed, not redacted

Frame paths are re-derived against known-safe roots (the install tree, stdlib, site-packages,
`sys.prefix`). Anything outside those is dropped **whole**, not trimmed to its leaf: every
component of a data path can be an identifier, and `C:\Users\jsmith\...` leaks a person before
you reach the patient folder. Frames inside the software tree stay fully readable, so debugging
value is retained.

### Structure labels

Checked against the vocabulary rbGyanX already ships (`STRUCTURE_ALIASES`, `TG263_ALIASES`) plus
a laterality/qualifier set. A compound token containing a recognised anatomical segment *and* an
unaccounted-for segment withholds confidence. `Parotid_L` passes; `Parotid_L_Smith` refuses.
Code identifiers such as `run_controller` are not flagged.

### Non-English and site-specific labels

The checks above are calibrated on English structure names, and the non-ASCII check treats any
non-ASCII letter as possibly a name with diacritics. That is right for `Müller` and wrong for a
department whose structures are named `Ohrspeicheldrüse_L`, `耳下腺_L` or `Околоушная_L`. Those
would refuse constantly — and **a safety control that fires constantly gets switched off**, which
is a worse outcome than the leak it was guarding against.

Two things follow.

*Latin-script labels already pass.* `Ohrspeicheldruese_L`, `Parotida_izq` and
`Glande_parotide_G` contain no recognised anatomical segment, so there is no appended-name
pattern to suspect, and they are treated as neutral rather than risky.

*Anything else is declared, not guessed.* A site registers its own label vocabulary once:

```bash
export RBGYANX_STRUCTURE_LABELS=/etc/rbgyanx/labels.json    # a file, or a directory of them
```

```json
{ "structure_labels": ["Ohrspeicheldrüse_L", "Ohrspeicheldrüse_R", "Rückenmark", "耳下腺_L"] }
```

A bare JSON list works too, and a reference pack may carry `structure_labels` alongside its
entries, so a site declares everything in one place. Declared labels are removed from the text
before the residual checks run, so they cannot be read as evidence of risk.

The refusal message names the environment variable, because a refusal that tells you how to fix
it permanently gets fixed, whereas one with no remedy gets the feature turned off.

**What is deliberately not done:** shipping a multilingual alias set. A partial one works for the
languages that happen to be included and fails for the next, which is the same constant-refusal
problem made unpredictable — and medical terminology across languages is not something this
module can verify. Declaring a name-bearing label such as `Parotid_L_Smith` remains possible but
is a site's explicit act, never an accident: `Parotid_L_Smith` still refuses by default, before
and after any declaration.

---

## 3. The frozen set

**This is a software safety property, not a policy preference.** A radiobiology CDSS computes
numbers a clinician may act on. An agent that can edit the numeric core — or the tests that
verify it — can change what a complication probability means and then make the suite green, and
the change would look like a passing build. Freezing both closes that.

None of it is configurable. A setting that can switch off a safety property is not a safety
property.

**What produces the numbers**
`engine/radiobiology/**`, `engine/uncertainty/**`, `engine/validation/**`,
`engine/statistical_models/epv_guard.py`, `engine/config/**`, `baseline_numerics.json`

`engine/config/**` is included because it holds the LKB parameter triples. Editing a TD50 changes
a complication probability exactly as surely as editing the model that consumes it.

**What verifies the numbers**
`tests/**`, `pyproject.toml`, any `conftest.py` / `pytest.ini` / `setup.cfg` / `tox.ini`,
`.github/workflows/**`

The configuration is frozen alongside the tests. `addopts` can inject `--ignore` or `-p no:…`,
and a `conftest.py` can autouse-skip; freezing tests while leaving their configuration writable
leaves the identical hole open.

**What constrains the agent**
`rbgyanx/ai/capability.py`, `scrubber.py`, `audit.py`, `config.py`, `tools/registry.py`,
`tools/paths.py`, `ask_rbgyanx/scope_guard.py`, `rbgyanx/logic/mode_controller.py`,
`scripts/pre_publish_check.py`

`config.py` is here because `Provider.remote` is the entire basis of data locality. The registry
and path guard are here because freezing a policy while leaving its enforcement point editable
achieves nothing.

### Creation rules

Restricting edits is not enough. Without touching a single frozen file, a new `sitecustomize.py`,
`usercustomize.py`, `.pth` (executes at interpreter start-up) or `conftest.py` re-opens
everything — and a package directory named after a frozen module
(`rbgyanx/ai/capability/__init__.py`) shadows it outright. All refused.

### The verification loop

Around **every** confirmed edit:

1. snapshot the exact file bytes
2. apply
3. run `tests/test_ntcp_positive_controls.py` (22 analytic controls)
4. run the full suite
5. any failure → **automatic revert**, report what failed, no silent retry

The snapshot is file bytes, **not `git stash`**. `git stash` is repo-global: it would capture the
user's own unrelated uncommitted work, and a conflicted `stash pop` leaves the tree neither
original nor edited — the opposite of the guarantee. It also fails differently depending on what
the user happened to have in progress, which is the last property you want in a safety
mechanism. No git command runs in the revert path. The restore is verified by SHA-256.

Edits are presented as reviewable diffs; `confirm` defaults to `False`, so a caller that forgets
it cannot write silently.

---

## 4. Literature quick-compare and the export gate

A recalled number and a checked number look identical once they are in the same table, and a
table is what gets pasted into a QA document six months later.

| Provenance | Meaning | Treatment |
|---|---|---|
| `SHIPPED_REFERENCE` | computed from a versioned pack | arithmetic, reproducible with no model in the loop; citation + pack version rendered |
| `MODEL_RECALL` | the model said so | marked unverified; any DOI replaced with `unverified - resolve before citing` |
| `WEB_RETRIEVED` | fetched at run time | unverified — retrieval proves a page said it, not that the page is right |

Provenance is always a visible column. Mixing tiers is permitted; hiding the mix is not.

### Reference packs

`rbgyanx/ai/reference_packs/*.json`, versioned, each entry carrying organ, endpoint, metric,
value, units, citation and pack version. Packs are **additive**: a site drops its own file into
the directory and it is loaded alongside the shipped ones. rbGyanX runs in many countries and
under many protocols, so asserting one institution's tolerances as universal would be wrong.

- `quantec-2010` — selected QUANTEC constraints. Orientation values for a single organ at a
  time; not a plan-acceptance standard, and they do not compose.
- `rbgyanx-lkb-defaults` — the tool's own shipped parameters, generated from
  `engine/config/site_params_ntcp_default.yaml`. A test walks all 139 values to catch drift.

### The export gate

Any export (report, CSV, clipboard, saved figure) containing a `MODEL_RECALL` row:

- is prefixed with the orientation notice, **verbatim**, in both Markdown and CSV so it cannot
  be lost by choosing a format;
- keeps the rows marked inside the exported artefact;
- **refuses** to drop the provenance column while unverified rows are present. That single
  operation is what would let someone produce a clean-looking table out of recalled content by
  accident, which is what this gate exists to stop.

> Quick orientation only. Values marked unverified come from model recall, not a checked source.
> Any comparison intended for publication, QA documentation or clinical use must be performed and
> verified by a human against primary literature.

An all-shipped export carries no notice — a notice on everything means nothing.

---

## 5. Audit log

Append-only JSONL in the user's config directory (`%APPDATA%\rbGyanX`,
`$XDG_CONFIG_HOME/rbgyanx`, Application Support; override with `RBGYANX_AUDIT_DIR`). Not the
repo — a clone must not carry another site's audit trail, and a frozen install has no repo. Not
a temp directory — a trail that evaporates on reboot is not a trail.

One record per transmission: timestamp, provider, remote flag, install type, capability, payload
byte count, scrubber findings count, SHA-256 of the payload. **Never the payload.** The log is
PHI-free by construction: `AuditRecord` has nine scalar fields and no field that could carry
patient content, and a test pins the key set.

Rotation at 2 MB keeping 5 generations, by renaming rather than truncating.

**Honest limitation:** the digest is a plain SHA-256. A hash of a very short, low-entropy payload
is brute-forceable in principle. Real payloads carry a system prompt and a question and are far
past that threshold, but the digest is an integrity aid, not a confidentiality guarantee.

---

## 6. Threat model

| Threat | Control |
|---|---|
| Patient data reaches a hosted LLM | Axis 1; patient-level capabilities denied for remote; scrubber fails closed |
| A "local" provider is pointed off-machine | `effective_remote()` requires a loopback URL, not just the flag |
| A name survives regex scrubbing | residual-risk check withholds confidence → caller refuses |
| An identifier hides in a structure label | label checked against the shipped TG-263 vocabulary |
| The agent widens its own permissions | `capability.py` frozen; the registry that enforces it is frozen |
| The agent weakens its own PHI guard | `scrubber.py` frozen |
| The agent silences its own audit trail | `audit.py` frozen; append-only |
| The agent changes a dose-response number | `engine/radiobiology`, `engine/uncertainty`, `engine/config` frozen |
| The agent makes a broken suite pass | `tests/**` **and** the test configuration frozen |
| The agent bypasses the freeze with a new file | creation rules refuse hook and shadowing files |
| A bad edit lands silently | review-then-confirm; snapshot/verify/auto-revert |
| Path traversal out of the install tree | resolved-path containment, symlinks and NTFS streams handled |
| Code execution via a test selector | selector validated as data; `-p`, `-c`, `--pdb` refused |
| Real data reaches a "synthetic" run | allow-list of declared synthetic directories, both providers |
| Unverified values enter a citable artefact | provenance column + export gate |
| An institution cannot enforce policy | kill switch via env or site config, not editable from the UI |

### What this does *not* defend against

- **A user pasting patient data into the chat box on a remote provider.** `phi_guard` warns; per
  the documented 2026-07-25 decision it does not block text the user typed themselves.
- **A malicious local operator.** Someone who can edit the installed source can remove any of
  this. The frozen set constrains the *assistant*, not a determined human with write access.
- **The correctness of model output.** Nothing here makes an explanation true. That is what the
  scope guard, the deterministic engine and human review are for.

---

## 7. Related work

Qi et al., *Generative AI, foundation models and large language models in radiation therapy
physics*, Medical Physics 2026;53:e70616, surveys this area. It is noted as related work only:
its full text was not available while this design was written, so no specific claim here is
attributed to it, and the design has not been checked for agreement with its recommendations.
Anyone extending this component should read it and reconcile.

---

## 8. Where things live

| Path | Role |
|---|---|
| `rbgyanx/ai/capability.py` | matrix, install detection, kill switch, frozen set — **frozen** |
| `rbgyanx/ai/scrubber.py` | fail-closed PHI scrubber — **frozen** |
| `rbgyanx/ai/audit.py` | append-only transmission log — **frozen** |
| `rbgyanx/ai/config.py` | provider presets and the `remote` flag — **frozen** |
| `rbgyanx/ai/session.py` | what is allowed right now, for the panel header |
| `rbgyanx/ai/tools/registry.py` | the gate every tool passes through — **frozen** |
| `rbgyanx/ai/tools/paths.py` | path containment — **frozen** |
| `rbgyanx/ai/tools/readonly.py` | read_code, read_error, run_tests, run_synthetic, explain_run |
| `rbgyanx/ai/tools/edit.py` | edit_code and the verification loop |
| `rbgyanx/ai/tools/literature.py` | provenance tiers and the export gate |
| `rbgyanx/ai/reference_packs/` | versioned reference packs, site-extensible |
| `rbgyanx/ai/phi_guard.py` | warn-not-block guard for user-typed text |
