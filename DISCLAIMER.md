# rbGyanX — Regulatory and clinical disclaimer

rbGyanX is **clinical decision support software**, not an autonomous treatment planning system
and **not** a regulated medical device (FDA/CE) unless separately cleared by your institution.

- Outputs are for **physicist and physician review** only.
- Classical and ML predictions carry model uncertainty; verify against institutional SOP.
- Do not use as the sole basis for treatment decisions.
- Real patient data remains your responsibility (HIPAA / local privacy law).

This disclaimer applies to the GUI, CLI, generated PDF/Excel reports, and all API outputs.

## AI assistant (experimental, ADVANCED-only, off by default)

The optional AI assistant **explains outputs the deterministic engine has already produced**. It
never computes, adjusts or influences a TCP, NTCP or UTCP value, and no code path leads from it
into the numeric core.

- Assistant output is **not a clinical recommendation** and carries no more authority than any
  other text in the interface. It is subject to every limitation above.
- The assistant can be wrong. Explanations are not verified, and a fluent explanation of a
  number is not evidence that the number is right.
- Literature comparisons marked **unverified** come from model recall, not a checked source.
  Any comparison intended for publication, QA documentation or clinical use must be performed
  and verified by a human against primary literature.
- Sending suspected patient data to a remote provider (Claude, Kimi, or any hosted endpoint) is
  **blocked in code, with no user override**. The guard scans every outgoing message, attached
  run context included; a single finding refuses the send before any network call. A provider is
  treated as remote unless it is both flagged local and resolves to loopback, so a LAN endpoint
  counts as remote.
- This is pattern matching, not certainty. It stops what it recognises — DICOM identifiers and
  UIDs, long digit runs, dates, e-mail addresses, absolute paths, "Last, First" names. It cannot
  recognise a patient described in prose. **Use the Local provider for anything patient-
  identifiable**; the block is a backstop, not a licence.
- Institutions can disable all remote providers with `RBGYANX_AI_DISABLE_REMOTE=1` or
  `ai.disable_remote: true` in a site config file. This cannot be re-enabled from the interface.
- Text you type yourself is scanned on exactly the same terms as anything else: if the guard
  flags it and the provider is remote, it is refused. **Do not paste patient identifiers into the
  assistant** — the guard is conservative, but no pattern set catches everything.

See `docs/AI_ASSISTANT_DESIGN.md` for the capability matrix, threat model and frozen set.
