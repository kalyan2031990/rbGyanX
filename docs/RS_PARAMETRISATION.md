# Relative-seriality (RS) NTCP parametrisation

## Decision (Phase 2b)

**Resolution (ii):** Keep the implemented voxel control term

```
P(D) = 2^(-exp(gamma_eff · (1 − D/D50)))
```

and document YAML `gamma` as **`gamma_eff`**, not literature γ50 directly.

## Relationship to canonical literature form

The Ågren / Källman form often written as:

```
P(D) = 2^(-exp(e · γ50 · (1 − D/D50)))     where e ≈ 2.71828
```

Therefore, when importing γ50 from publications:

```
gamma_eff = e · γ50
```

## Fixed-point anchors (regression contract)

1. **Voxel control:** `P(D50) = 2^(-exp(0)) = 0.5` (independent of `gamma_eff`).
2. **Organ NTCP:** For a uniform DVH at `D = D50`, organ-level NTCP = **0.5** when
   `s = 1` (fully serial). For `s < 1`, organ NTCP at D50 is **not** 0.5 — this is
   expected parallel-serial biology, not a bug.

Tests: `engine/tests/test_ntcp_scientific_anchors.py`.

## YAML schema

In `engine/config/*_ntcp.yaml`, RS blocks use:

| Field | Meaning |
|-------|---------|
| `D50` | Dose for 50% voxel control (Gy) |
| `gamma` | `gamma_eff` for this implementation |
| `s` | Relative seriality (0 parallel … 1 serial) |
