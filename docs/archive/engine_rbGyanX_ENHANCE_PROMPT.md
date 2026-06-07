# rbGyanX CDSS — ENHANCE PROMPT (P3 + P4): New Clinical Capabilities
## Expert Cursor Implementation Prompt — Literature-Grounded

**Prerequisite:** rbGyanX_FIX_PROMPT.md must be fully implemented and all tests
passing before starting. The EPV gate fix, corrected LKB probit (gEUD-based),
bDVH module, uNTCP, and NTCP Excel reporter must all be in place.

---

## MANDATORY TERMINOLOGY (enforce throughout all code and comments)

| Symbol | Full name | Definition | Do NOT confuse with |
|--------|-----------|------------|---------------------|
| **uTCP** | Uncertainty-aware TCP | MC CI bands on TCP (existing: `uncertainty/parameter_mc.py`) | UTCP |
| **uNTCP** | Uncertainty-aware NTCP | MC CI bands on NTCP (FIX prompt: `uncertainty/ntcp_mc.py`) | UTCP |
| **UTCP** | Uncomplicated TCP | Plan-quality composite = TCP × Π(1−NTCP_k) over all scored OARs. Brahme/Källman. **THIS module.** | uTCP, uNTCP |
| **P+** | Complication-free control | Identical to UTCP; original Källman (1992) notation | — |
| **EPV** | Events per variable | n_recurrences / n_features | — |
| **bDVH** | Biological DVH | EQD2-corrected DVH for OARs (FIX prompt) | — |

---

## ENHANCEMENT 1 — UTCP (Uncomplicated TCP / Complication-Free Control)
### `radiobiology/utcp.py`

### Literature basis — mandatory reading before implementing

**Foundational papers (these define the formula and philosophy):**

1. **Brahme A.** Dosimetric precision requirements in radiation therapy. *Acta Radiol Oncol* 1984;23(5):379–391.
   — Introduced the concept: probability of achieving tumour control without causing serious complications.

2. **Källman P, Lind BK, Brahme A.** An algorithm for maximizing the probability of complication-free tumour control in radiation therapy. *Phys Med Biol* 1992;37(4):871–890.
   — Defined P+ = TCP × Π_k(1−NTCP_k) over ALL scored OARs. Demonstrated dose-optimisation by finding the dose that maximises P+. Used H&N as the clinical example.

3. **Ågren A-K, Brahme A, Turesson I.** Optimization of uncomplicated control for head and neck tumors. *Int J Radiat Oncol Biol Phys* 1990;19(4):1077–1085.
   — First clinical application of P+ to ~200 H&N patients at two dose levels. Parotid gland AND spinal cord NTCPs were both included in the product — parotid xerostomia was NOT excluded.

4. **Sánchez-Nieto B, Nahum AE.** BIOPLAN: software for the biological evaluation of radiotherapy treatment plans. *Med Dosim* 2000;25(2):71–76.
   — BIOPLAN computes UTCP = TCP × Π(1−NTCP_k) over **all user-selected structures**, not just serial OARs. The user chooses which structures to include based on their clinical relevance to the endpoint.

5. **Wang X et al.** Calculating the individualized fraction regime in stereotactic body radiotherapy for non-small cell lung cancer based on uncomplicated tumor control probability function. *Radiat Oncol* 2019;14(1):117. PMC6587287.
   — Lung SBRT specific: P+ = TCP × (1−NTCP_pneumonitis) × (1−NTCP_chest_wall_pain) × (1−NTCP_rib_fracture). Shows that ALL clinically relevant OAR endpoints (including quality-of-life endpoints like chest wall pain) belong in the product.

6. **Tommasino F, Nahum A, Cella L.** Increasing the power of TCP/NTCP modelling in radiotherapy. *Transl Cancer Res* 2017;6(Suppl 5):S807–S821.
   — Review confirming H&N UTCP includes parotid + mandible + cord + brainstem (Chang et al. H&N data cited).

### The correct formula and philosophy

**The Källman / Brahme P+ formula:**
```
UTCP = P+ = TCP_target × Π_{k=1}^{K} (1 − NTCP_k)
```

Where k runs over **ALL scored OARs** for the treatment site — not only serial/lethal OARs.
The product includes quality-of-life endpoints (parotid xerostomia, chest wall pain) because
the radiobiological philosophy is that **any complication degrades the treatment outcome**.

**Critical design point (corrected from earlier literature-naive implementations):**

The restriction to "serial OARs only" has NO basis in the Brahme/Källman framework. This
restriction was a clinical shortcut sometimes applied in treatment planning optimisation
software, but for a radiobiological reporting tool like rbGyanX, the full product over all
scored structures is the correct approach.

The practical consequence:
- **UTCP for H&N** is lower than TCP alone even when cord/brainstem are well-spared,
  because parotid NTCPs (which are high) also reduce the product. This is clinically correct:
  a plan that gives 90% TCP but 80% bilateral xerostomia probability is not truly "uncomplicated".
- **UTCP for Lung SBRT** is limited by pneumonitis AND chest wall toxicity (Wang 2019).
- **UTCP for Brain GBM** is limited by brainstem, optic chiasm/nerves, AND normal brain
  (radionecrosis and cognitive decline).

**Severity-weighted extension (optional):**

A clinically useful extension is the severity-weighted UTCP:
```
UTCP_w = TCP × Π_k (1 − NTCP_k)^{w_k}
```
where w_k ∈ (0,1] is a clinical severity weight reflecting the gravity of complication k.
- w = 1.0: life-threatening or irreversible (myelopathy, blindness, brainstem injury)
- w = 0.7: serious/Grade 3–4 quality-impacting (dysphagia, severe xerostomia, pneumonitis G3)
- w = 0.4: Grade 2, reversible (mild xerostomia, rib fracture G2, chest wall pain G2)

This is implemented as an optional parameter. The default (w=1 for all) reproduces the
Källman 1992 formula.

### Site-specific OAR lists — corrected and literature-grounded

**Important corrections vs. earlier version:**

**Brain GBM:** Hippocampus was missing. A randomised controlled trial (NCOG-41, Neuro-Oncol
2024) demonstrated that mean left hippocampal dose > 30 Gy causes verbal/visual memory deficits
in GBM patients. The EORTC/ESTRO-EANO GBM guideline (RadiotherOncol 2023) lists hippocampi,
cochleae, and pituitary as OARs to constrain during GBM planning. All three were absent from
the earlier OAR map. They are now included.
References: PMC9161646 (hippocampus NTCP GBM); PMC12059297 (hippocampal sparing GBM planning);
ESTRO-EANO guideline ScienceDirect 2023; EORTC 22033 LGG NTCP trial PMC6797857.

**Brain METS:** Cochleae were missing. WBRT and multi-fraction SRS irradiate the cochleae;
hearing loss is a documented WBRT endpoint. Now included.

**Breast:** Multiple OARs were missing or incorrectly weighted:
- SpinalCord was w=1.0 — wrong. Spinal cord injury in standard breast RT is exceedingly rare;
  doses are well below tolerance in tangential fields. Downgraded to w=0.7 and only relevant
  when posterior nodal fields are used.
- Missing Esophagus (when supraclavicular + IMN fields used, D1cc ≤20 Gy per RTOG constraints).
- Missing Thyroid: hypothyroidism is a validated, well-modelled NTCP endpoint in breast RT
  with supraclavicular irradiation. TD50 ≈ 37.7 Gy (Smyczek-Gargya 2024 PubMed 38317677).
- Missing BrachialPlexus: standard OAR in supraclavicular field planning.
- Missing Lung_Contra: low but non-zero, tracked in bilateral disease and modern techniques.
Reference: Darby NEJM 2013; PMC4465142 (DIBH breast NTCP); PMC6195271 (IMN+supraclav OARs);
PubMed 38317677 (thyroid NTCP breast); Johansson 2014 (brachial plexus).

**What about other brain cancers (Low-Grade Glioma, Meningioma, WBRT)?**

rbGyanX currently supports two brain sites: BRAIN_GBM (high-grade glioma) and BRAIN_METS
(metastases / SRS). Three clinically important subtypes are not yet covered:
- BRAIN_LGG — Low-grade glioma (50.4 Gy/28 fr; EORTC 22033): longer survival → hippocampus,
  pituitary, and cognitive decline OARs are even more important than in GBM.
- BRAIN_SRS_BENIGN — Meningioma/Schwannoma/Pituitary adenoma (single-fraction SRS):
  OARs are cochlea (hearing loss), cranial nerves, optic apparatus.
- BRAIN_WBRT — Whole-brain RT for primary CNS lymphoma or multiple mets.

Adding these requires new TCP site parameters (α, β, N₀, TCD50) in `site_params.py` and
`site_params_default.yaml`. This is recommended as a future Phase 9 extension after
the current ENHANCE prompt is fully implemented and tested.

```python
# ──────────────────────────────────────────────────────────────────────────────
# UTCP_OAR_MAP: site → list of {oar, severity_weight}
#
# Severity weights: 1.0 = lethal/irreversible; 0.7 = serious G3-4 quality-impairing;
#                   0.4 = G2 reversible/quality-of-life.
# The product runs over ALL scored OARs (Källman 1992 philosophy).
# ──────────────────────────────────────────────────────────────────────────────
UTCP_OAR_MAP: dict[str, list[dict]] = {

    # ── BRAIN_GBM: Glioblastoma 60Gy/30fr or 40Gy/15fr ──────────────────────
    # Full EORTC/ESTRO-EANO OAR set (ESTRO-EANO guideline, RadiotherOncol 2023).
    # Critical: brainstem, optic chiasm, optic nerves.
    # Non-critical but dose-constrained (EORTC guideline): cochleas, pituitary,
    #   hippocampi, hypothalamus.
    # Hippocampus: RCT evidence of dose-memory association in GBM (NCOG-41 2024;
    #   PMC9161646). Mean bilateral dose >30 Gy → verbal/visual memory impairment.
    # Pituitary: radiation-induced hypopituitarism documented in high-dose brain RT
    #   (Appelman 2011; AAPM TG-166).
    # Cochlea: QUANTEC Dmean <45 Gy (Bhandare IJROBP 2010); EORTC GBM guideline.
    "BRAIN_GBM": [
        {"oar": "Brainstem",      "severity_weight": 1.0},  # neuropathy/necrosis: lethal
        {"oar": "OpticChiasm",    "severity_weight": 1.0},  # optic neuropathy: irreversible
        {"oar": "OpticNerve_L",   "severity_weight": 1.0},
        {"oar": "OpticNerve_R",   "severity_weight": 1.0},
        {"oar": "NormalBrain",    "severity_weight": 0.7},  # radionecrosis / V60
        {"oar": "Hippocampus_L",  "severity_weight": 0.7},  # neurocognitive decline (NCOG-41)
        {"oar": "Hippocampus_R",  "severity_weight": 0.7},  # neurocognitive decline
        {"oar": "Cochlea_L",      "severity_weight": 0.4},  # sensorineural hearing loss
        {"oar": "Cochlea_R",      "severity_weight": 0.4},
        {"oar": "Pituitary",      "severity_weight": 0.4},  # hypopituitarism
    ],

    # ── BRAIN_METS: Brain metastases — SRS 1–3 fr; HA-WBRT 30Gy/10fr ─────────
    # For SRS: brainstem + optic apparatus dominate (proximity-driven toxicity).
    # For HA-WBRT: hippocampus is the primary sparing target (RTOG 0933; NRG CC001).
    # Cochlea: WBRT irradiates the entire cochlea — hearing loss NTCP is relevant.
    # Basis: RTOG 0933 (Gondi IJROBP 2014); NRG CC001; PMC5859351 (cumulative SRS doses).
    "BRAIN_METS": [
        {"oar": "Brainstem",      "severity_weight": 1.0},
        {"oar": "OpticChiasm",    "severity_weight": 1.0},
        {"oar": "OpticNerve_L",   "severity_weight": 1.0},
        {"oar": "OpticNerve_R",   "severity_weight": 1.0},
        {"oar": "NormalBrain",    "severity_weight": 0.7},  # radionecrosis (multi-SRS)
        {"oar": "Hippocampus_L",  "severity_weight": 0.7},  # HA-WBRT RTOG 0933
        {"oar": "Hippocampus_R",  "severity_weight": 0.7},
        {"oar": "Cochlea_L",      "severity_weight": 0.4},  # WBRT hearing loss
        {"oar": "Cochlea_R",      "severity_weight": 0.4},
    ],

    # ── HN: Head & Neck IMRT/VMAT 66–70Gy/33–35fr ────────────────────────────
    # Ågren/Brahme/Turesson (1990) used parotid + cord in the original P+.
    # Chang et al. (Acta Oncol 2013) included parotid, mandible, cord, brainstem.
    # Full QUANTEC 2010 H&N OAR set (Deasy, Sanguineti, Werner-Wasik, Eisbruch).
    "HN": [
        {"oar": "SpinalCord",          "severity_weight": 1.0},  # myelopathy: lethal
        {"oar": "Brainstem",           "severity_weight": 1.0},  # neuropathy: severe
        {"oar": "Parotid_L",           "severity_weight": 0.7},  # xerostomia G2+
        {"oar": "Parotid_R",           "severity_weight": 0.7},
        {"oar": "Mandible",            "severity_weight": 0.7},  # osteoradionecrosis
        {"oar": "PharynxConstrictor",  "severity_weight": 0.7},  # dysphagia G2+
        {"oar": "OralCavity",          "severity_weight": 0.4},  # mucositis G2
        {"oar": "Larynx",              "severity_weight": 0.7},  # laryngeal oedema
    ],

    # ── LUNG_SBRT: 3–8 fractions, dose/fraction > 10 Gy ─────────────────────
    # Wang et al. (2019) PMC6587287: P+ = TCP × (1-NTCP_lung) × (1-NTCP_cw) × (1-NTCP_rib).
    # ChestWall and Rib are Grade 2 quality-of-life endpoints (w=0.4) but critical to
    # SBRT UTCP when tumour is peripheral/adjacent to chest wall.
    "LUNG_SBRT": [
        {"oar": "SpinalCord",    "severity_weight": 1.0},  # myelopathy: lethal
        {"oar": "LungTotal",     "severity_weight": 0.7},  # pneumonitis G2+
        {"oar": "Esophagus",     "severity_weight": 0.7},  # esophagitis/stricture
        {"oar": "Heart",         "severity_weight": 0.7},  # pericarditis/ischemia
        {"oar": "ChestWall",     "severity_weight": 0.4},  # chest wall pain G2+ (Wang 2019)
        {"oar": "Rib",           "severity_weight": 0.4},  # rib fracture G2 (Wang 2019)
    ],

    # ── BREAST: IMRT 50Gy/25fr, hypofrax 40Gy/15fr, or 26–28.5Gy/5fr ────────
    # CORRECTED from previous version — substantial additions:
    #
    # SpinalCord: downgraded from w=1.0 to w=0.7. Cord injury in standard tangential
    #   breast RT is exceedingly rare (doses typically <20 Gy). Retained at w=0.7 because
    #   posterior supraclavicular fields (used in node-positive disease) can approach
    #   spinal cord tolerance, especially with extended field RT.
    #
    # Esophagus (NEW): when supraclavicular + IMN irradiation is used (standard for
    #   node-positive breast cancer, EBCTCG 2024), esophageal D1cc can reach 15–20 Gy.
    #   RTOG constraint: D1cc ≤20 Gy. NTCP for esophagitis G2+ is clinically validated.
    #   Ref: PMC6195271 (IMN+supraclav OAR dosimetry); Werner-Wasik QUANTEC 2010.
    #
    # Thyroid (NEW): hypothyroidism after supraclavicular irradiation is a validated,
    #   modelled NTCP endpoint. TD50 = 37.7 Gy for hypothyroidism grade≥1.
    #   Risk is significant when thyroid volume ≥8.5cc receives >20 Gy.
    #   Ref: PubMed 38317677 (Smyczek-Gargya 2024 Clin Trans RadSci);
    #        NTCP model hypothyroidism breast: PubMed 32926911.
    #
    # BrachialPlexus (NEW): standard OAR for supraclavicular field; brachial plexopathy
    #   G2+ is a known complication. Dmax <66 Gy (Johansson IJROBP 2014).
    #
    # Lung_Contra (NEW): low-dose exposure tracked in bilateral breast cancer and modern
    #   wide-field RT techniques. Relevant for secondary pneumonitis risk (w=0.4).
    #
    # Basis: Darby NEJM 2013 (heart); Gagliardi QUANTEC 2010 (heart);
    #   PMC4465142 (DIBH breast NTCP — heart+lung); PMC6195271 (supraclav OARs);
    #   PubMed 38317677 (thyroid); Johansson 2014 (brachial plexus).
    "BREAST": [
        {"oar": "Heart",           "severity_weight": 1.0},  # pericarditis/cardiac ischaemia
        {"oar": "LAD",             "severity_weight": 0.7},  # coronary stenosis (left-sided)
        {"oar": "Lung_Ipsi",       "severity_weight": 0.7},  # pneumonitis G2+
        {"oar": "Esophagus",       "severity_weight": 0.7},  # esophagitis (nodal RT)
        {"oar": "Thyroid",         "severity_weight": 0.4},  # hypothyroidism (supraclav RT)
        {"oar": "BrachialPlexus",  "severity_weight": 0.7},  # plexopathy (supraclav RT)
        {"oar": "SpinalCord",      "severity_weight": 0.7},  # myelopathy (posterior fields)
        {"oar": "Lung_Contra",     "severity_weight": 0.4},  # secondary pneumonitis risk
    ],
}
```

### Code specification

```python
# radiobiology/utcp.py

"""
UTCP — Uncomplicated TCP (Complication-Free Tumour Control Probability).

P+ = TCP × Π_{k=1}^{K} (1 − NTCP_k)

where k runs over ALL scored OARs for the treatment site.

Reference:
  Brahme A. Acta Radiol Oncol 1984;23:379–391.
  Källman P, Lind BK, Brahme A. Phys Med Biol 1992;37:871–890.
  Ågren A-K, Brahme A, Turesson I. IJROBP 1990;19:1077–1085.

Terminology note:
  UTCP ≠ uTCP.
  uTCP  = uncertainty-aware TCP   (MC CI bands, uncertainty/parameter_mc.py).
  UTCP  = Uncomplicated TCP       (plan quality composite metric, THIS module).
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any


# Default OAR maps per site with severity weights.
# Severity weight w_k: 1.0 = lethal/irreversible, 0.7 = serious G3-4 QoL,
# 0.4 = moderate G2 reversible.
# Reference: Wang 2019 PMC6587287; Ågren 1990 IJROBP; Chang 2013 Acta Oncol.
UTCP_OAR_MAP: dict[str, list[dict]] = {
    "BRAIN_GBM": [
        {"oar": "Brainstem",    "severity_weight": 1.0},
        {"oar": "OpticChiasm",  "severity_weight": 1.0},
        {"oar": "OpticNerve_L", "severity_weight": 1.0},
        {"oar": "OpticNerve_R", "severity_weight": 1.0},
        {"oar": "NormalBrain",  "severity_weight": 0.7},
    ],
    "BRAIN_METS": [
        {"oar": "Brainstem",      "severity_weight": 1.0},
        {"oar": "OpticChiasm",    "severity_weight": 1.0},
        {"oar": "OpticNerve_L",   "severity_weight": 1.0},
        {"oar": "OpticNerve_R",   "severity_weight": 1.0},
        {"oar": "Hippocampus_L",  "severity_weight": 0.7},
        {"oar": "Hippocampus_R",  "severity_weight": 0.7},
        {"oar": "NormalBrain",    "severity_weight": 0.7},
    ],
    "HN": [
        {"oar": "SpinalCord",         "severity_weight": 1.0},
        {"oar": "Brainstem",          "severity_weight": 1.0},
        {"oar": "Parotid_L",          "severity_weight": 0.7},
        {"oar": "Parotid_R",          "severity_weight": 0.7},
        {"oar": "Mandible",           "severity_weight": 0.7},
        {"oar": "OralCavity",         "severity_weight": 0.4},
        {"oar": "PharynxConstrictor", "severity_weight": 0.7},
        {"oar": "Larynx",             "severity_weight": 0.7},
    ],
    "LUNG_SBRT": [
        {"oar": "SpinalCord",    "severity_weight": 1.0},
        {"oar": "LungTotal",     "severity_weight": 0.7},
        {"oar": "Esophagus",     "severity_weight": 0.7},
        {"oar": "Heart",         "severity_weight": 0.7},
        {"oar": "ChestWall",     "severity_weight": 0.4},
        {"oar": "Rib",           "severity_weight": 0.4},
    ],
    "BREAST": [
        {"oar": "Heart",         "severity_weight": 1.0},
        {"oar": "LAD",           "severity_weight": 0.7},
        {"oar": "Lung_Ipsi",     "severity_weight": 0.7},
        {"oar": "SpinalCord",    "severity_weight": 1.0},
    ],
}


@dataclass
class UTCPResult:
    """Per-patient UTCP result with full provenance."""
    UTCP: float                              # standard UTCP (all w_k = 1)
    UTCP_weighted: float                     # severity-weighted variant
    TCP_used: float                          # TCP value used in product
    TCP_model: str                           # which TCP model (Poisson, gEUD, mean)
    NTCP_product: float                      # Π(1-NTCP_k), w=1 version
    NTCP_product_weighted: float             # Π(1-NTCP_k)^w_k version
    scored_OARs: list[dict]                  # list of {oar, ntcp, weight, contributed}
    n_oars_scored: int                       # number of OARs with valid NTCP
    n_oars_missing: int                      # OARs in map but not found in results
    missing_OAR_names: list[str]             # which OARs were absent
    site: str
    AnonPatientID: str = ""
    warnings: list[str] = field(default_factory=list)


def compute_utcp(
    tcp_result: dict,
    ntcp_results: list[dict],
    site_key: str,
    tcp_model: str = "auto",
    ntcp_model: str = "LKB_loglogit",
    custom_oar_map: list[dict] | None = None,
) -> UTCPResult:
    """
    Compute UTCP for one patient.

    Formula (Källman 1992):
        UTCP     = TCP × Π_{k ∈ scored} (1 − NTCP_k)
        UTCP_w   = TCP × Π_{k ∈ scored} (1 − NTCP_k)^{w_k}

    The product runs over ALL OARs in UTCP_OAR_MAP[site_key] for which
    NTCP values are available. Missing OARs generate a warning but do NOT
    abort — the product is computed over the scored subset.

    Arguments
    ---------
    tcp_result : dict from TCPCalculator.compute_all(). Keys include:
                 TCP_Poisson, TCP_ZM, TCP_gEUD, TCP_Logistic, TCP_mean.
    ntcp_results : list of dicts from NTCPCalculator.compute_all(), one per OAR.
                   Each has keys 'structure', 'NTCP_LKB_loglogit', etc.
    site_key   : one of BRAIN_GBM, BRAIN_METS, HN, LUNG_SBRT, BREAST.
    tcp_model  : 'auto' selects first valid TCP in order: Poisson → gEUD → mean.
    ntcp_model : NTCP column to use: 'LKB_loglogit', 'LKB_probit', or 'RS'.
    custom_oar_map : override UTCP_OAR_MAP[site_key] with a user-supplied list of
                     {'oar': str, 'severity_weight': float} dicts.

    Returns UTCPResult with full provenance.
    """
    warns: list[str] = []
    anon_id = str(tcp_result.get("AnonPatientID", ""))

    # --- Select TCP value ---
    if tcp_model == "auto":
        for col in ("TCP_Poisson", "TCP_gEUD", "TCP_ZM", "TCP_Logistic", "TCP_mean"):
            v = tcp_result.get(col, math.nan)
            if isinstance(v, (int, float)) and not math.isnan(float(v)):
                tcp_val = float(v)
                tcp_model_used = col.replace("TCP_", "")
                break
        else:
            tcp_val = math.nan
            tcp_model_used = "none"
            warns.append("No valid TCP value found.")
    else:
        col = f"TCP_{tcp_model}" if not tcp_model.startswith("TCP_") else tcp_model
        tcp_val = float(tcp_result.get(col, math.nan))
        tcp_model_used = tcp_model

    # --- Map NTCP results by OAR canonical name ---
    ntcp_col_map = {
        "LKB_loglogit": "NTCP_LKB_loglogit",
        "LKB_probit":   "NTCP_LKB_probit",
        "RS":           "NTCP_RS",
    }
    ntcp_col = ntcp_col_map.get(ntcp_model, "NTCP_LKB_loglogit")

    oar_ntcp: dict[str, float] = {}
    for r in ntcp_results:
        oar = str(r.get("structure", ""))
        val = r.get(ntcp_col, math.nan)
        if oar and isinstance(val, (int, float)) and not math.isnan(float(val)):
            oar_ntcp[oar] = float(val)

    # --- Compute UTCP product over all OARs in map ---
    oar_list = custom_oar_map or UTCP_OAR_MAP.get(site_key.upper(), [])
    scored_oars:     list[dict] = []
    missing_oars:    list[str]  = []
    ntcp_product          = 1.0   # w=1 standard
    ntcp_product_weighted = 1.0   # severity-weighted

    for entry in oar_list:
        oar_name = entry["oar"]
        w_k      = float(entry.get("severity_weight", 1.0))

        if oar_name in oar_ntcp:
            ntcp_k = oar_ntcp[oar_name]
            ntcp_product          *= (1.0 - ntcp_k)
            ntcp_product_weighted *= (1.0 - ntcp_k) ** w_k
            scored_oars.append({
                "oar":             oar_name,
                "NTCP":            ntcp_k,
                "severity_weight": w_k,
                "contribution":    1.0 - ntcp_k,
            })
        else:
            missing_oars.append(oar_name)
            warns.append(
                f"OAR '{oar_name}' absent from NTCP results for site {site_key}. "
                f"UTCP product computed over {len(oar_list)-len(missing_oars)} OARs only. "
                f"UTCP may be overestimated if this OAR has high NTCP."
            )

    # --- Compute final UTCP values ---
    if math.isnan(tcp_val):
        utcp = utcp_w = math.nan
    else:
        utcp   = float(tcp_val * ntcp_product)
        utcp_w = float(tcp_val * ntcp_product_weighted)

    return UTCPResult(
        UTCP=utcp,
        UTCP_weighted=utcp_w,
        TCP_used=tcp_val,
        TCP_model=tcp_model_used,
        NTCP_product=ntcp_product,
        NTCP_product_weighted=ntcp_product_weighted,
        scored_OARs=scored_oars,
        n_oars_scored=len(scored_oars),
        n_oars_missing=len(missing_oars),
        missing_OAR_names=missing_oars,
        site=site_key,
        AnonPatientID=anon_id,
        warnings=warns,
    )


def compute_utcp_cohort(
    tcp_results: list[dict],
    ntcp_results_by_patient: dict[str, list[dict]],
    site_key: str,
    ntcp_model: str = "LKB_loglogit",
) -> list[UTCPResult]:
    """
    Compute UTCP for each patient in a cohort.

    ntcp_results_by_patient : {AnonPatientID → list of per-OAR NTCP result dicts}.
    Returns one UTCPResult per patient (best-target TCP used).
    """
    results: list[UTCPResult] = []
    for tcp_r in tcp_results:
        anon_id  = str(tcp_r.get("AnonPatientID", ""))
        ntcp_rs  = ntcp_results_by_patient.get(anon_id, [])
        utcp_r   = compute_utcp(tcp_r, ntcp_rs, site_key, ntcp_model=ntcp_model)
        results.append(utcp_r)
    return results
```

### Wire UTCP into `rbgyanx_engine/engine.py`

```python
# engine.py — after TCP and NTCP are collected, before Excel output:
if tcp_results and ntcp_results and cfg.endpoint == "both":
    from collections import defaultdict
    from radiobiology.utcp import compute_utcp_cohort

    ntcp_by_patient: dict[str, list[dict]] = defaultdict(list)
    for r in ntcp_results:
        ntcp_by_patient[str(r.get("AnonPatientID", ""))].append(r)

    site_for_utcp = site_override or _dominant_params_site(tcp_results)
    utcp_list     = compute_utcp_cohort(
        tcp_results, dict(ntcp_by_patient), site_for_utcp
    )
    utcp_map = {u.AnonPatientID: u for u in utcp_list}
    for r in tcp_results:
        pid = str(r.get("AnonPatientID", ""))
        if pid in utcp_map:
            u = utcp_map[pid]
            r["UTCP"]                = u.UTCP
            r["UTCP_weighted"]       = u.UTCP_weighted
            r["UTCP_NTCP_product"]   = u.NTCP_product
            r["UTCP_OARs_scored"]    = u.n_oars_scored
            r["UTCP_OARs_missing"]   = u.n_oars_missing
            r["UTCP_missing_OARs"]   = ", ".join(u.missing_OAR_names)
            r["UTCP_TCP_model"]      = u.TCP_model
```

Add UTCP columns to `build_benchmarking_table()` in `outputs/reporter.py`.

---

## ENHANCEMENT 2 — QUANTEC CONSTRAINT CHECKER
### `validation/quantec_checker.py`

### Clinical context

QUANTEC (Quantitative Analyses of Normal Tissue Effects in the Clinic, Bentzen et al.
IJROBP 2010;76:S3–9) established organ-specific dose-volume tolerance constraints
that are the current clinical standard. These constraints differ conceptually from
probabilistic NTCP models — they are **hard thresholds** used in treatment planning
to define dose limits. Automatic flagging gives the radiation oncologist immediate
plan safety information.

```python
# validation/quantec_checker.py

"""
QUANTEC 2010 dose constraint checker.

Evaluates DVH metrics against Quantitative Analyses of Normal Tissue Effects
in the Clinic (QUANTEC) published thresholds (Marks et al. IJROBP 2010 and
site-specific QUANTEC papers in the same supplement).

This is a dose-volume constraint check, NOT a probabilistic NTCP computation.
Both are useful and complementary; neither replaces the other.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class QUANTECResult:
    organ: str
    metric: str
    actual_value: float        # Gy for Dmax/Dmean/Vxx; % for volume metrics
    limit: float               # QUANTEC threshold
    endpoint: str              # clinical endpoint described by this constraint
    reference: str             # QUANTEC paper citation
    severity: str              # "VIOLATION" | "WARNING" (within 10% of limit) | "PASS"
    anon_patient_id: str = ""


# QUANTEC 2010 constraints. Each entry: {metric, limit, endpoint, ref}.
# Vxx metrics: volume (%) receiving ≥ xx Gy. Dmax/Dmean in Gy.
# Reference: Marks LB et al. IJROBP 2010;76:S10-19; site-specific papers in same issue.
QUANTEC_CONSTRAINTS: dict[str, list[dict]] = {
    "SpinalCord": [
        {"metric": "Dmax", "limit": 45.0,
         "endpoint": "Myelopathy <1%",
         "ref": "Kirkpatrick IJROBP 2010;76:S42"},
        {"metric": "Dmax", "limit": 50.0,
         "endpoint": "Myelopathy <0.2%",
         "ref": "Kirkpatrick IJROBP 2010;76:S42"},
    ],
    "Brainstem": [
        {"metric": "Dmax", "limit": 54.0,
         "endpoint": "Neuropathy/necrosis",
         "ref": "Mayo IJROBP 2010;76:S20"},
        {"metric": "Dmax", "limit": 60.0,
         "endpoint": "Neuropathy absolute limit (<1cc)",
         "ref": "Mayo IJROBP 2010;76:S20"},
    ],
    "OpticChiasm": [
        {"metric": "Dmax", "limit": 54.0,
         "endpoint": "Optic neuropathy <3%",
         "ref": "Mayo IJROBP 2010;76:S28"},
    ],
    "OpticNerve_L": [
        {"metric": "Dmax", "limit": 54.0,
         "endpoint": "Optic neuropathy <3%",
         "ref": "Mayo IJROBP 2010;76:S28"},
    ],
    "OpticNerve_R": [
        {"metric": "Dmax", "limit": 54.0,
         "endpoint": "Optic neuropathy <3%",
         "ref": "Mayo IJROBP 2010;76:S28"},
    ],
    "NormalBrain": [
        {"metric": "V60", "limit": 3.0,
         "endpoint": "Symptomatic radionecrosis <5%",
         "ref": "Lawrence IJROBP 2010;76:S20 (V60<3cc)"},
    ],
    "Hippocampus_L": [
        {"metric": "Dmean", "limit": 7.3,
         "endpoint": "Neurocognitive decline (RTOG 0933)",
         "ref": "Gondi IJROBP 2014;88:571"},
    ],
    "Hippocampus_R": [
        {"metric": "Dmean", "limit": 7.3,
         "endpoint": "Neurocognitive decline (RTOG 0933)",
         "ref": "Gondi IJROBP 2014;88:571"},
    ],
    "Parotid_L": [
        {"metric": "Dmean", "limit": 25.0,
         "endpoint": "Xerostomia grade≥2 <20%",
         "ref": "Deasy IJROBP 2010;76:S86"},
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Xerostomia grade≥2 <15%",
         "ref": "Deasy IJROBP 2010;76:S86"},
    ],
    "Parotid_R": [
        {"metric": "Dmean", "limit": 25.0,
         "endpoint": "Xerostomia grade≥2 <20%",
         "ref": "Deasy IJROBP 2010;76:S86"},
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Xerostomia grade≥2 <15%",
         "ref": "Deasy IJROBP 2010;76:S86"},
    ],
    "Mandible": [
        {"metric": "Dmax", "limit": 70.0,
         "endpoint": "Osteoradionecrosis",
         "ref": "Tsai IJROBP 2013;85:1124"},
    ],
    "Larynx": [
        {"metric": "Dmean", "limit": 44.0,
         "endpoint": "Laryngeal edema grade≥2",
         "ref": "Sanguineti IJROBP 2007;69:1300"},
        {"metric": "Dmax", "limit": 66.0,
         "endpoint": "Laryngeal dysfunction",
         "ref": "QUANTEC HN supplement 2010"},
    ],
    "PharynxConstrictor": [
        {"metric": "Dmean", "limit": 50.0,
         "endpoint": "Dysphagia grade≥2",
         "ref": "Eisbruch IJROBP 2011;81:1327"},
    ],
    "OralCavity": [
        {"metric": "Dmean", "limit": 40.0,
         "endpoint": "Mucositis grade≥2",
         "ref": "QUANTEC HN supplement 2010"},
    ],
    "LungTotal": [
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Pneumonitis grade≥2 <20%",
         "ref": "Marks IJROBP 2010;76:S70"},
        {"metric": "V20",   "limit": 30.0,
         "endpoint": "Pneumonitis grade≥2 <20%",
         "ref": "Marks IJROBP 2010;76:S70"},
        {"metric": "V5",    "limit": 65.0,
         "endpoint": "Pneumonitis (V5 limit)",
         "ref": "Marks IJROBP 2010;76:S70"},
    ],
    "Lung_L": [
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Pneumonitis grade≥2",
         "ref": "Marks IJROBP 2010;76:S70"},
        {"metric": "V20",   "limit": 30.0,
         "endpoint": "Pneumonitis grade≥2",
         "ref": "Marks IJROBP 2010;76:S70"},
    ],
    "Lung_R": [
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Pneumonitis grade≥2",
         "ref": "Marks IJROBP 2010;76:S70"},
        {"metric": "V20",   "limit": 30.0,
         "endpoint": "Pneumonitis grade≥2",
         "ref": "Marks IJROBP 2010;76:S70"},
    ],
    "Heart": [
        {"metric": "Dmean", "limit": 26.0,
         "endpoint": "Pericarditis grade≥3",
         "ref": "Gagliardi IJROBP 2010;76:S77"},
        {"metric": "V25",   "limit": 10.0,
         "endpoint": "Cardiac toxicity <1%",
         "ref": "Gagliardi IJROBP 2010;76:S77"},
    ],
    "Esophagus": [
        {"metric": "Dmean", "limit": 34.0,
         "endpoint": "Esophagitis grade≥2 <30%",
         "ref": "Werner-Wasik IJROBP 2010;76:S86"},
        {"metric": "Dmax",  "limit": 58.0,
         "endpoint": "Esophageal stricture",
         "ref": "Werner-Wasik IJROBP 2010;76:S86"},
    ],
    "Cochlea_L": [
        {"metric": "Dmean", "limit": 45.0,
         "endpoint": "Sensorineural hearing loss",
         "ref": "Bhandare IJROBP 2010;76:S110"},
    ],
    "Cochlea_R": [
        {"metric": "Dmean", "limit": 45.0,
         "endpoint": "Sensorineural hearing loss",
         "ref": "Bhandare IJROBP 2010;76:S110"},
    ],
    "LAD": [
        {"metric": "Dmean", "limit": 10.0,
         "endpoint": "Major coronary event risk (LAD)",
         "ref": "van Nimwegen Heart 2016;102:1703"},
    ],
    "Lung_Ipsi": [
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Pneumonitis grade≥2",
         "ref": "Marks IJROBP 2010;76:S70"},
    ],
    "ChestWall": [
        {"metric": "V30", "limit": 70.0,
         "endpoint": "Chest wall pain grade≥2 <30%",
         "ref": "Timmerman IJROBP 2008;72:S53 (RTOG 0236)"},
    ],
    "BrachialPlexus": [
        {"metric": "Dmax", "limit": 66.0,
         "endpoint": "Brachial plexopathy grade≥2",
         "ref": "Johansson IJROBP 2014;88:92"},
    ],
    # ── New entries for brain and breast OAR corrections ──────────────────────
    "NormalBrain": [
        {"metric": "V60", "limit": 3.0,
         "endpoint": "Symptomatic radionecrosis <5% (V60<3cc)",
         "ref": "Lawrence IJROBP 2010;76:S20"},
    ],
    "Pituitary": [
        {"metric": "Dmean", "limit": 45.0,
         "endpoint": "Hypopituitarism grade≥2",
         "ref": "Appelman IJROBP 2011;79:1421"},
    ],
    "Thyroid": [
        {"metric": "Dmean", "limit": 30.0,
         "endpoint": "Hypothyroidism grade≥1 (supraclav RT)",
         "ref": "Smyczek-Gargya Clin Trans RadSci 2024 (PubMed 38317677)"},
        {"metric": "Dmean", "limit": 20.0,
         "endpoint": "Hypothyroidism grade≥1 <15% risk",
         "ref": "NTCP hypothyroid breast: PubMed 32926911"},
    ],
    "Lung_Contra": [
        {"metric": "Dmean", "limit": 10.0,
         "endpoint": "Low-dose pneumonitis risk (bilateral fields)",
         "ref": "Marks IJROBP 2010;76:S70 (extrapolated)"},
    ],
    "Rib": [
        {"metric": "Dmax", "limit": 50.0,
         "endpoint": "Rib fracture grade≥2 <5% (EQD2 Dmax)",
         "ref": "Timmerman IJROBP 2008;72:S53; PMC3573931"},
    ],
}


def _compute_dvh_metric(dvh_df: pd.DataFrame, metric: str) -> float:
    """
    Compute one DVH metric from a differential DVH DataFrame.
    Vxx returns volume percentage (0-100) receiving ≥ xx Gy.
    Dmax, Dmean return doses in Gy.
    """
    if dvh_df is None or dvh_df.empty:
        return math.nan
    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols  = np.asarray(dvh_df["volume_frac"], dtype=float)
    total = vols.sum()
    if total <= 0:
        return math.nan
    if metric == "Dmax":
        return float(doses.max())
    if metric == "Dmean":
        return float((doses * vols).sum() / total)
    if metric.startswith("V"):
        try:
            thr = float(metric[1:])
            return float(vols[doses >= thr].sum() / total * 100.0)
        except ValueError:
            return math.nan
    return math.nan


def check_quantec_constraints(
    dvh_df: pd.DataFrame,
    canonical_oar: str,
    anon_id: str = "",
) -> list[QUANTECResult]:
    """
    Check QUANTEC 2010 constraints for one OAR DVH.
    VIOLATION if actual > limit.
    WARNING if actual is within 10% below limit.
    Returns empty list if no constraints defined or no issues found.
    """
    results: list[QUANTECResult] = []
    for c in QUANTEC_CONSTRAINTS.get(canonical_oar, []):
        actual = _compute_dvh_metric(dvh_df, c["metric"])
        if math.isnan(actual):
            continue
        limit = float(c["limit"])
        if actual > limit:
            severity = "VIOLATION"
        elif actual > limit * 0.90:
            severity = "WARNING"
        else:
            continue
        results.append(QUANTECResult(
            organ=canonical_oar, metric=c["metric"],
            actual_value=actual, limit=limit,
            endpoint=c["endpoint"], reference=c["ref"],
            severity=severity, anon_patient_id=anon_id,
        ))
    return results


def check_cohort_quantec(ntcp_results: list[dict]) -> pd.DataFrame:
    """Evaluate QUANTEC constraints for all OARs in an NTCP result list."""
    rows: list[dict] = []
    for r in ntcp_results:
        dvh_df  = r.get("_dvh_df")
        if dvh_df is None:
            continue
        organ   = str(r.get("structure", ""))
        anon_id = str(r.get("AnonPatientID", ""))
        for v in check_quantec_constraints(dvh_df, organ, anon_id):
            rows.append({
                "AnonPatientID":      v.anon_patient_id,
                "OAR":                v.organ,
                "Metric":             v.metric,
                "Actual_Gy_or_Pct":   round(v.actual_value, 2),
                "QUANTEC_Limit":      round(v.limit, 2),
                "Clinical_Endpoint":  v.endpoint,
                "Reference":          v.reference,
                "Severity":           v.severity,
            })
    cols = ["AnonPatientID","OAR","Metric","Actual_Gy_or_Pct",
            "QUANTEC_Limit","Clinical_Endpoint","Reference","Severity"]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
```

Wire into `engine.py`: after NTCP collection, call `check_cohort_quantec()` and
add a `QUANTEC_Flags` sheet to the NTCP Excel workbook. Save `quantec_flags.csv`.

---

## ENHANCEMENT 3 — CLINICAL SAFETY GUARD
### `validation/clinical_safety_guard.py`

Before ML-derived predictions enter any report, a pre-reporting checklist must run.
This guard annotates results without blocking output.

```python
# validation/clinical_safety_guard.py

"""
Clinical Safety Guard — pre-reporting gate for ML-derived TCP/NTCP predictions.

Uses TRIPOD reporting guidelines (Collins et al. BMJ 2015;350:g7594) and
Harrell's guidelines on predictive modelling (Regression Modelling Strategies 2015).
Assigns PASS / WARN / FAIL status. Does NOT block output — annotates it.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class SafetyCheck:
    criterion: str
    passed: bool
    actual: float | None
    threshold: float | None
    message: str
    severity: str   # "FAIL" | "WARN" | "INFO"


@dataclass
class SafetyReport:
    model_name: str
    overall_status: str          # "PASS" | "WARN" | "FAIL"
    checks: list[SafetyCheck] = field(default_factory=list)

    def annotation(self) -> str:
        if self.overall_status == "PASS":
            return f"[VALIDATED — {self.model_name}]"
        if self.overall_status == "WARN":
            return f"[USE WITH CAUTION — {self.model_name}]"
        return f"[UNRELIABLE — DO NOT REPORT — {self.model_name}]"


def run_safety_checks(
    model_name: str,
    auc: float,
    cv_auc: float | None = None,
    overfitting_index: float | None = None,
    calibration_slope: float | None = None,
    epv: float | None = None,
    n_patients: int = 0,
    synthetic_data_used: bool = False,
) -> SafetyReport:
    """
    Safety checklist using TRIPOD + Harrell criteria.

    1. AUC > 0.60: better than chance (FAIL ≤0.55; WARN 0.55–0.65).
    2. Overfitting index < 0.10: apparent vs CV AUC gap (FAIL >0.20; WARN 0.10–0.20).
    3. Calibration slope 0.70–1.30 (FAIL <0.50 or >2.0; WARN outside 0.70–1.30).
    4. EPV ≥ 10 (FAIL <5; WARN 5–10).
    5. n ≥ 30 (FAIL <20; WARN 20–30).
    6. No synthetic/augmented data in reported metrics (FAIL if synthetic=True).
    """
    checks: list[SafetyCheck] = []
    n_fail = n_warn = 0

    def _add(criterion, passed, actual, threshold, msg, sev):
        nonlocal n_fail, n_warn
        checks.append(SafetyCheck(criterion, passed, actual, threshold, msg, sev))
        if sev == "FAIL": n_fail += 1
        elif sev == "WARN": n_warn += 1

    if math.isfinite(auc):
        if auc <= 0.55:
            _add("AUC", False, auc, 0.60, f"AUC={auc:.3f} ≤ 0.55: not better than chance.", "FAIL")
        elif auc <= 0.65:
            _add("AUC", True,  auc, 0.65, f"AUC={auc:.3f}: marginally above chance.", "WARN")
        else:
            _add("AUC", True,  auc, 0.60, f"AUC={auc:.3f}: acceptable.", "INFO")

    if overfitting_index is not None and math.isfinite(overfitting_index):
        if overfitting_index > 0.20:
            _add("Overfitting", False, overfitting_index, 0.20,
                 f"Index={overfitting_index:.3f} > 0.20: likely overfit.", "FAIL")
        elif overfitting_index > 0.10:
            _add("Overfitting", True,  overfitting_index, 0.10,
                 f"Index={overfitting_index:.3f}: borderline.", "WARN")
        else:
            _add("Overfitting", True,  overfitting_index, 0.10,
                 f"Index={overfitting_index:.3f}: acceptable.", "INFO")

    if calibration_slope is not None and math.isfinite(calibration_slope):
        if calibration_slope < 0.50 or calibration_slope > 2.0:
            _add("CalibSlope", False, calibration_slope, None,
                 f"Slope={calibration_slope:.3f}: severe miscalibration.", "FAIL")
        elif not (0.70 <= calibration_slope <= 1.30):
            _add("CalibSlope", True,  calibration_slope, None,
                 f"Slope={calibration_slope:.3f}: moderate miscalibration.", "WARN")
        else:
            _add("CalibSlope", True,  calibration_slope, None,
                 f"Slope={calibration_slope:.3f}: acceptable.", "INFO")

    if epv is not None and math.isfinite(epv):
        if epv < 5.0:
            _add("EPV", False, epv, 10.0, f"EPV={epv:.1f} < 5: critically underpowered.", "FAIL")
        elif epv < 10.0:
            _add("EPV", True,  epv, 10.0, f"EPV={epv:.1f}: borderline (5–10).", "WARN")
        else:
            _add("EPV", True,  epv, 10.0, f"EPV={epv:.1f}: sufficient.", "INFO")

    if n_patients < 20:
        _add("SampleSize", False, float(n_patients), 30.0,
             f"n={n_patients} < 20: too small for ML.", "FAIL")
    elif n_patients < 30:
        _add("SampleSize", True,  float(n_patients), 30.0,
             f"n={n_patients}: borderline (20–30).", "WARN")

    if synthetic_data_used:
        _add("SyntheticData", False, None, None,
             "Synthetic/augmented data: NEVER report ML metrics from synthetic cohorts.", "FAIL")

    status = "FAIL" if n_fail > 0 else ("WARN" if n_warn > 0 else "PASS")
    return SafetyReport(model_name=model_name, overall_status=status, checks=checks)
```

Wire into `run_ml_xai_validation()`: call `run_safety_checks()` after each model fit,
store `.annotation()` in `perf[model_name]["safety_annotation"]`. In
`save_benchmarking_excel()`, colour `Model_Performance` rows: red=FAIL, yellow=WARN,
green=PASS using `openpyxl.styles.PatternFill`.

---

## ENHANCEMENT 4 — LightGBM ML MODEL
### `ml_models/lgbm_tcp.py`

LightGBM is faster than XGBoost, often better calibrated on small imbalanced cohorts
(is_unbalance=True), and completes the standard clinical ML trio (XGB + RF + LGBM).
SHAP via TreeExplainer works identically.

```python
# ml_models/lgbm_tcp.py — implement identically to xgboost_tcp.py but with:
# ('lgbm', LGBMClassifier(is_unbalance=True, random_state=42, n_jobs=-1, verbose=-1))
# LGBM_PARAM_GRID = {'lgbm__n_estimators': [100,200], 'lgbm__max_depth': [3,5],
#                    'lgbm__learning_rate': [0.05,0.10], 'lgbm__num_leaves': [15,31]}
# LGBMTCPResult dataclass identical to XGBoostTCPResult.
# Export: fit_lgbm_tcp()
```

Add `lightgbm>=3.3` to `requirements.txt`. Wire into `run_ml_xai_validation()`.

---

## ENHANCEMENT 5 — PATIENT-LEVEL CV SPLIT
### Fix in `ml_models/xgboost_tcp.py`, `random_forest_tcp.py`, `lgbm_tcp.py`

Multi-target patients (e.g. GTVp + GTVn in H&N) can have both DVHs split across
folds — this is patient-level data leakage inflating AUC.

```python
# Replace in all three ML modules:
from sklearn.model_selection import StratifiedGroupKFold  # sklearn ≥ 1.3

outer_cv = StratifiedGroupKFold(n_splits=outer_folds)
inner_cv = StratifiedGroupKFold(n_splits=inner_folds)

# Add patient_ids parameter:
def fit_xgboost_tcp(X, y, feature_names=None, patient_ids=None, ...):
    groups = np.asarray(patient_ids) if patient_ids is not None else np.arange(len(y_arr))
    # .split(X_arr, y_arr, groups=groups) instead of .split(X_arr, y_arr)
```

Pass `patient_ids=ml_df["AnonPatientID"].values` from `pipeline.py`.

---

## ENHANCEMENT 6 — ADAPTIVE COHORT CONSISTENCY SCORE (CCS)
### `validation/cohort_consistency.py`

The CCS threshold adapts to sample size — a ρ of 0.35 is acceptable for n=12
but poor for n=60. Adds a `verdict` key (CONSISTENT / MARGINAL / INCONSISTENT).

```python
# validation/cohort_consistency.py

def _adaptive_ccs_threshold(n: int) -> float:
    """Threshold = max(0.20, 0.50 × min(n/50, 1.0)). Floored at 0.20 for small cohorts."""
    return max(0.20, 0.50 * min(n / 50.0, 1.0))


def compute_ccs(y_true, y_prob_classical, y_prob_ml) -> dict:
    """
    Adaptive CCS: three Spearman correlations, adaptive threshold, verdict.
    Returns dict with keys: ccs, verdict, threshold_used,
    rho_classical_vs_ml, rho_classical_vs_outcome, rho_ml_vs_outcome, n_patients.
    """
    from scipy import stats
    import numpy as np
    y    = np.asarray(y_true, dtype=float)
    p_cl = np.asarray(y_prob_classical, dtype=float)
    p_ml = np.asarray(y_prob_ml, dtype=float)
    n    = len(y)
    rho1, _ = stats.spearmanr(p_cl, p_ml)
    rho2, _ = stats.spearmanr(p_cl, y)
    rho3, _ = stats.spearmanr(p_ml, y)
    ccs      = float(np.mean([rho1, rho2, rho3]))
    threshold = _adaptive_ccs_threshold(n)
    if ccs >= threshold:          verdict = "CONSISTENT"
    elif ccs >= 0.5 * threshold:  verdict = "MARGINAL"
    else:                         verdict = "INCONSISTENT"
    return {
        'ccs': ccs, 'verdict': verdict, 'threshold_used': threshold,
        'rho_classical_vs_ml': float(rho1),
        'rho_classical_vs_outcome': float(rho2),
        'rho_ml_vs_outcome': float(rho3),
        'n_patients': n,
    }
```

---

## EXPAND NTCP OAR YAML

Add the following missing OARs to `config/site_params_ntcp_default.yaml`.
Parameters from QUANTEC 2010 and cited literature. Add matching canonical name
aliases to `config/structure_aliases.py`.

```yaml
HN:
  organs:
    Submandibular_L:
      geud_a: 3.0
      alpha_beta_gy: 3.0           # Welsh 2013
      LKB_loglogit: {TD50_gy: 39.0, gamma50: 0.6}
    Submandibular_R:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 39.0, gamma50: 0.6}
    Mandible:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 70.0, gamma50: 0.5}   # osteoradionecrosis, Tsai 2013
    PharynxConstrictor:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 41.0, gamma50: 0.4}   # dysphagia, Eisbruch 2011
    Esophagus:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 34.0, gamma50: 0.7}   # Werner-Wasik 2010

LUNG_SBRT:
  organs:
    # Note: ChestWall and Rib require Dmax-based NTCP — LKB loglogit with
    # high geud_a (serial endpoint) or simple threshold models. Parameters
    # from Wang 2019 PMC6587287 calibrated to SBRT cohorts.
    Lung_L:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 24.5, gamma50: 0.7}   # Marks 2010
    Lung_R:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 24.5, gamma50: 0.7}
    BrachialPlexus:
      geud_a: 20.0
      alpha_beta_gy: 3.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}  # Johansson 2014

BREAST:
  organs:
    # ── Corrected: added Esophagus, Thyroid, BrachialPlexus, Lung_Contra ──────
    # All four are clinically relevant when supraclavicular + IMN fields are used
    # (standard for node-positive breast cancer, EBCTCG 2024).
    Esophagus:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 34.0, gamma50: 0.7}   # esophagitis, Werner-Wasik 2010
    Thyroid:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      # Hypothyroidism NTCP validated in breast RT supraclav field.
      # TD50 = 37.7 Gy (LKB fit), gamma50 = 0.7.
      # Ref: Smyczek-Gargya Clin Trans RadSci 2024 (PubMed 38317677);
      #      NTCP hypothyroid breast PubMed 32926911.
      LKB_loglogit: {TD50_gy: 37.7, gamma50: 0.7}
    BrachialPlexus:
      geud_a: 20.0
      alpha_beta_gy: 3.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}  # Johansson IJROBP 2014
    Lung_Contra:
      geud_a: 3.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 24.5, gamma50: 0.7}     # Marks QUANTEC 2010

BRAIN_GBM:
  organs:
    # ── Corrected: added Hippocampus L+R, Cochlea L+R (EORTC GBM guideline) ──
    # All four are listed in ESTRO-EANO GBM guideline as non-critical but dose-
    # constrained OARs. Hippocampus: NCOG-41 RCT evidence in GBM (2024).
    OpticNerve_L:
      geud_a: 20.0
      alpha_beta_gy: 2.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}  # Mayo QUANTEC 2010
    OpticNerve_R:
      geud_a: 20.0
      alpha_beta_gy: 2.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}
    Pituitary:
      geud_a: 3.0
      alpha_beta_gy: 2.0
      LKB_loglogit: {TD50_gy: 45.0, gamma50: 0.5}     # Appelman IJROBP 2011
    Hippocampus_L:
      geud_a: 3.0
      alpha_beta_gy: 2.0
      # TD50 from hippocampus NTCP model (prospective cohort, PMC9161646):
      # For bilateral mean dose: TD20 ≈ 10.9 Gy, TD50 ≈ 59.3 Gy.
      # Using clinical sparing threshold (RTOG 0933 < 7.3 Gy mean) as a conservative
      # reference; LKB fitted gamma50 from LGG NTCP trial (PMC6797857).
      LKB_loglogit: {TD50_gy: 22.0, gamma50: 0.8}
    Hippocampus_R:
      geud_a: 3.0
      alpha_beta_gy: 2.0
      LKB_loglogit: {TD50_gy: 22.0, gamma50: 0.8}
    Cochlea_L:
      geud_a: 1.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 45.0, gamma50: 0.6}     # Bhandare QUANTEC 2010
    Cochlea_R:
      geud_a: 1.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 45.0, gamma50: 0.6}

BRAIN_METS:
  organs:
    # ── Corrected: added Cochlea L+R (WBRT hearing loss endpoint) ─────────────
    OpticNerve_L:
      geud_a: 20.0
      alpha_beta_gy: 2.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}
    OpticNerve_R:
      geud_a: 20.0
      alpha_beta_gy: 2.0
      LKB_probit: {TD50_gy: 54.0, m: 0.18, n: 0.05}
    Cochlea_L:
      geud_a: 1.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 45.0, gamma50: 0.6}     # Bhandare QUANTEC 2010
    Cochlea_R:
      geud_a: 1.0
      alpha_beta_gy: 3.0
      LKB_loglogit: {TD50_gy: 45.0, gamma50: 0.6}
```

### Future Phase 9 — Additional brain cancer sites (not in this prompt)

Three brain cancer subtypes are not yet supported in rbGyanX:

| Proposed site key | Cancer | Fractionation | New TCP params needed |
|---|---|---|---|
| `BRAIN_LGG` | Low-grade glioma (IDH-mut) | 50.4 Gy/28 fr (EORTC 22033) | α=0.10, β=0.020, α/β=5, N₀=10⁶, Tpot=30d |
| `BRAIN_SRS_BENIGN` | Meningioma, schwannoma, pituitary adenoma | 12–16 Gy/1 fr (SRS) | Tumour-specific; use USC model |
| `BRAIN_WBRT` | Primary CNS lymphoma, multi-met WBRT | 30–36 Gy/10–12 fr | α=0.10, β=0.020 |

For BRAIN_LGG and BRAIN_SRS_BENIGN, the OAR sets are:
- **BRAIN_LGG UTCP OARs**: Brainstem (w=1.0), OpticChiasm (w=1.0), OpticNerves (w=1.0),
  NormalBrain (w=0.7), Hippocampus_L/R (w=0.7, especially critical — longer survival),
  Cochlea_L/R (w=0.4), Pituitary (w=0.4)
- **BRAIN_SRS_BENIGN UTCP OARs**: OpticChiasm (w=1.0), OpticNerves (w=1.0), Brainstem (w=1.0),
  Cochlea_L/R (w=0.7, hearing loss is primary endpoint for acoustic neuroma SRS),
  CranialNerves V/VII (w=0.7, trigeminal/facial nerve — cavernous sinus meningioma)

Implementing these requires editing `config/site_params.py`, `site_params_default.yaml`,
and adding TCP model calibration — defer to a dedicated Phase 9 session.

---

## ML AUGMENTATION SAFETY TAGGING

In `outputs/reporter.py`, tag rows from augmented patients (AnonPatientID starts
with "AUG") with `Data_Source = "SYNTHETIC"`. Use openpyxl orange `PatternFill`
for those rows in `TCP_Summary` sheet. This is a visible clinical-safety marker.

---

## UNIT TESTS

### `tests/test_utcp.py`

```python
import math, pytest
import numpy as np


def _make_tcp(pid="PT001", tcp_poisson=0.85):
    return {"AnonPatientID": pid, "TCP_Poisson": tcp_poisson}

def _make_ntcp(oar, ntcp_val, pid="PT001"):
    return {"structure": oar, "AnonPatientID": pid,
            "NTCP_LKB_loglogit": ntcp_val}


def test_utcp_uses_all_scored_oars_not_just_serial():
    """Parotid NTCP (w=0.7) must reduce UTCP — not excluded like in naive implementations."""
    from radiobiology.utcp import compute_utcp
    tcp_r  = _make_tcp(tcp_poisson=0.85)
    # Only parotid present — if UTCP naively excluded non-serial OARs, UTCP would equal TCP
    ntcp_r = [_make_ntcp("Parotid_L", 0.60)]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert result.UTCP < 0.85, (
        "Parotid NTCP must reduce UTCP — all OARs in the Källman formula, not just serial."
    )

def test_utcp_standard_product_formula():
    """UTCP = TCP × (1-NTCP_cord) × (1-NTCP_parotid_L) × (1-NTCP_parotid_R) for HN."""
    from radiobiology.utcp import compute_utcp
    tcp_val = 0.80
    ntcp_cord = 0.05; ntcp_parl = 0.35; ntcp_parr = 0.30
    tcp_r  = _make_tcp(tcp_poisson=tcp_val)
    ntcp_r = [
        _make_ntcp("SpinalCord", ntcp_cord),
        _make_ntcp("Parotid_L",  ntcp_parl),
        _make_ntcp("Parotid_R",  ntcp_parr),
    ]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    # Standard UTCP product (w=1 for all)
    expected = tcp_val * (1-ntcp_cord) * (1-ntcp_parl) * (1-ntcp_parr)
    assert abs(result.UTCP - expected) < 1e-9, (
        f"Expected UTCP={expected:.6f}, got {result.UTCP:.6f}"
    )

def test_utcp_equals_tcp_when_all_ntcp_zero():
    """UTCP = TCP when all OAR NTCPs are 0 (ideal plan)."""
    from radiobiology.utcp import compute_utcp
    tcp_r  = _make_tcp(tcp_poisson=0.85)
    ntcp_r = [_make_ntcp("SpinalCord", 0.0), _make_ntcp("Brainstem", 0.0)]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert abs(result.UTCP - 0.85) < 1e-9

def test_utcp_weighted_less_than_standard_when_w_less_1():
    """UTCP_weighted > UTCP_standard when severity weights < 1 (softer penalisation)."""
    from radiobiology.utcp import compute_utcp
    tcp_r  = _make_tcp(tcp_poisson=0.80)
    ntcp_r = [_make_ntcp("Parotid_L", 0.50)]   # w=0.7 for parotid in HN
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    # With w<1 for parotid, weighted UTCP is less penalised than standard
    assert result.UTCP_weighted > result.UTCP, (
        "Severity-weighted UTCP should be > standard when w<1 for quality-of-life OARs"
    )

def test_utcp_warns_on_missing_critical_oar():
    """Missing critical OAR (cord for HN) must generate a warning."""
    from radiobiology.utcp import compute_utcp
    tcp_r  = _make_tcp(tcp_poisson=0.85)
    ntcp_r = []
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert len(result.warnings) > 0
    assert result.n_oars_missing > 0

def test_utcp_lung_sbrt_includes_chest_wall():
    """
    For Lung SBRT, ChestWall and LungTotal must both be in the OAR product.
    Wang 2019: P+ = TCP × (1-NTCP_lung) × (1-NTCP_cw) × (1-NTCP_rib).
    """
    from radiobiology.utcp import UTCP_OAR_MAP
    lung_oars = [e["oar"] for e in UTCP_OAR_MAP.get("LUNG_SBRT", [])]
    assert "LungTotal" in lung_oars, "LungTotal must be in Lung SBRT OAR map"
    assert "ChestWall" in lung_oars, "ChestWall must be in Lung SBRT OAR map (Wang 2019)"

def test_utcp_hn_includes_parotid():
    """H&N OAR map must include Parotid_L/R (Ågren/Brahme 1990)."""
    from radiobiology.utcp import UTCP_OAR_MAP
    hn_oars = [e["oar"] for e in UTCP_OAR_MAP.get("HN", [])]
    assert "Parotid_L" in hn_oars, "Parotid_L missing from HN OAR map — see Ågren 1990"
    assert "Parotid_R" in hn_oars, "Parotid_R missing from HN OAR map — see Ågren 1990"

def test_utcp_brain_mets_includes_hippocampus_and_cochlea():
    """Brain METS OAR map must include hippocampus (RTOG 0933) AND cochlea (WBRT hearing)."""
    from radiobiology.utcp import UTCP_OAR_MAP
    mets_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_METS", [])]
    assert "Hippocampus_L" in mets_oars, "Hippocampus_L missing from BRAIN_METS — see RTOG 0933"
    assert "Cochlea_L"     in mets_oars, "Cochlea_L missing from BRAIN_METS — WBRT hearing loss"

def test_utcp_brain_gbm_includes_hippocampus():
    """
    Brain GBM OAR map must include hippocampus (NCOG-41 RCT 2024: mean left
    hippocampal dose >30 Gy associated with memory impairment in GBM patients).
    Not just BRAIN_METS — GBM patients also suffer hippocampal dose-related
    cognitive decline.
    """
    from radiobiology.utcp import UTCP_OAR_MAP
    gbm_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_GBM", [])]
    assert "Hippocampus_L" in gbm_oars, (
        "Hippocampus_L missing from BRAIN_GBM — NCOG-41 2024 RCT evidence"
    )
    assert "Hippocampus_R" in gbm_oars, "Hippocampus_R missing from BRAIN_GBM"

def test_utcp_brain_gbm_includes_cochlea_and_pituitary():
    """
    EORTC/ESTRO-EANO GBM guideline lists cochleae and pituitary as
    dose-constrained OARs for GBM planning. Both must be in the OAR map.
    """
    from radiobiology.utcp import UTCP_OAR_MAP
    gbm_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_GBM", [])]
    assert "Cochlea_L" in gbm_oars, "Cochlea_L missing from BRAIN_GBM — EORTC guideline"
    assert "Pituitary" in gbm_oars, "Pituitary missing from BRAIN_GBM — hypopituitarism risk"

def test_utcp_breast_includes_esophagus_thyroid_brachial():
    """
    Breast OAR map must include Esophagus, Thyroid, BrachialPlexus —
    all relevant when supraclavicular + IMN fields are used (node-positive
    breast cancer, EBCTCG 2024 standard of care).
    Thyroid: hypothyroidism NTCP validated (PubMed 38317677).
    BrachialPlexus: plexopathy from supraclav fields (Johansson 2014).
    """
    from radiobiology.utcp import UTCP_OAR_MAP
    breast_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BREAST", [])]
    assert "Esophagus"      in breast_oars, "Esophagus missing from BREAST — supraclav RT"
    assert "Thyroid"        in breast_oars, "Thyroid missing from BREAST — hypothyroidism NTCP"
    assert "BrachialPlexus" in breast_oars, "BrachialPlexus missing from BREAST — plexopathy"

def test_utcp_breast_spinal_cord_weight_not_1():
    """
    SpinalCord severity_weight must be < 1.0 for BREAST. Cord injury in
    standard tangential breast RT is exceedingly rare (cord doses typically
    <20 Gy). w=1.0 would over-penalise UTCP for a near-impossible complication.
    """
    from radiobiology.utcp import UTCP_OAR_MAP
    breast_entries = {e["oar"]: e["severity_weight"]
                      for e in UTCP_OAR_MAP.get("BREAST", [])}
    if "SpinalCord" in breast_entries:
        assert breast_entries["SpinalCord"] < 1.0, (
            f"SpinalCord w={breast_entries['SpinalCord']} should be <1.0 for BREAST "
            f"— cord injury in tangential breast RT is very rare"
        )
```

### `tests/test_quantec.py`

```python
import pandas as pd, pytest

def test_quantec_spinal_cord_violation():
    from validation.quantec_checker import check_quantec_constraints
    dvh = pd.DataFrame({"dose_gy": [47.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "SpinalCord")
    assert any(x.severity == "VIOLATION" for x in v)

def test_quantec_spinal_cord_pass():
    from validation.quantec_checker import check_quantec_constraints
    dvh = pd.DataFrame({"dose_gy": [38.0], "volume_frac": [1.0]})
    assert len(check_quantec_constraints(dvh, "SpinalCord")) == 0

def test_quantec_warning_zone():
    """43 Gy > 90% of 45 Gy limit → WARNING not VIOLATION."""
    from validation.quantec_checker import check_quantec_constraints
    dvh = pd.DataFrame({"dose_gy": [43.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "SpinalCord")
    assert any(x.severity == "WARNING" for x in v)

def test_quantec_parotid_warning():
    """Parotid Dmean=23 Gy → between 20 and 25 Gy → at least WARNING."""
    from validation.quantec_checker import check_quantec_constraints
    dvh = pd.DataFrame({"dose_gy": [23.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "Parotid_L")
    assert len(v) > 0   # warning for 20 Gy limit
```

### `tests/test_safety_guard.py`

```python
def test_safety_guard_fails_on_synthetic():
    from validation.clinical_safety_guard import run_safety_checks
    r = run_safety_checks("XGBoost", auc=0.75, cv_auc=0.70, overfitting_index=0.05,
                          calibration_slope=1.0, epv=12.0, n_patients=40,
                          synthetic_data_used=True)
    assert r.overall_status == "FAIL"
    assert "UNRELIABLE" in r.annotation()

def test_safety_guard_passes_good_model():
    from validation.clinical_safety_guard import run_safety_checks
    r = run_safety_checks("XGBoost", auc=0.75, cv_auc=0.70, overfitting_index=0.05,
                          calibration_slope=1.0, epv=15.0, n_patients=50)
    assert r.overall_status == "PASS"
    assert "VALIDATED" in r.annotation()

def test_adaptive_ccs_threshold_scales_with_n():
    from validation.cohort_consistency import _adaptive_ccs_threshold
    assert _adaptive_ccs_threshold(10)  < _adaptive_ccs_threshold(50)
    assert _adaptive_ccs_threshold(100) == pytest.approx(_adaptive_ccs_threshold(50))
    assert _adaptive_ccs_threshold(5)   >= 0.20

def test_ccs_verdict_key_present():
    from validation.cohort_consistency import compute_ccs
    import numpy as np
    y    = np.array([0,1]*6)
    p_cl = np.linspace(0.3, 0.9, 12)
    p_ml = p_cl + np.random.default_rng(0).normal(0, 0.05, 12)
    r = compute_ccs(y, p_cl, p_ml)
    assert r['verdict'] in ('CONSISTENT', 'MARGINAL', 'INCONSISTENT')
    assert 'threshold_used' in r
```

---

## COMPLETION CHECKLIST

- [ ] `radiobiology/utcp.py` — `UTCP_OAR_MAP` with literature-grounded site-specific OAR lists; `compute_utcp()` with both standard (Källman) and severity-weighted variants; `compute_utcp_cohort()`
- [ ] `rbgyanx_engine/engine.py` — UTCP computed for endpoint="both"; all UTCP fields attached to tcp_results
- [ ] `outputs/reporter.py` — UTCP, UTCP_weighted, UTCP_OARs_scored columns in benchmarking table
- [ ] `validation/quantec_checker.py` — full QUANTEC 2010 constraint table; `check_quantec_constraints()`; `check_cohort_quantec()`
- [ ] `outputs/ntcp_reporter.py` — `QUANTEC_Flags` sheet in NTCP Excel; `save_ntcp_excel()` updated
- [ ] `validation/clinical_safety_guard.py` — `run_safety_checks()`, `SafetyReport` with `.annotation()` method
- [ ] `rbgyanx_engine/pipeline.py` — safety guard called after model fit; annotation in Excel cells (colour-coded)
- [ ] `ml_models/lgbm_tcp.py` — `fit_lgbm_tcp()`, `LGBMTCPResult`; wired into `run_ml_xai_validation()`
- [ ] `ml_models/__init__.py` — exports `fit_lgbm_tcp`
- [ ] `requirements.txt` — `lightgbm>=3.3` added
- [ ] All three ML modules — `StratifiedGroupKFold`; `patient_ids` argument
- [ ] `rbgyanx_engine/pipeline.py` — `patient_ids=ml_df["AnonPatientID"].values` passed
- [ ] `validation/cohort_consistency.py` — `_adaptive_ccs_threshold()`; `verdict` and `threshold_used` in result dict
- [ ] `config/site_params_ntcp_default.yaml` — all missing OARs added:
      - HN: Submandibular L/R, Mandible, PharynxConstrictor, Esophagus
      - LUNG_SBRT: Lung_L, Lung_R, BrachialPlexus
      - BREAST: Esophagus, Thyroid (TD50=37.7 Gy), BrachialPlexus, Lung_Contra
      - BRAIN_GBM: OpticNerve L/R, Pituitary, Hippocampus L/R, Cochlea L/R
      - BRAIN_METS: OpticNerve L/R, Cochlea L/R
- [ ] `config/structure_aliases.py` — aliases for all new OAR canonical names
      (Thyroid: "thyroid","THYROID"; BrachialPlexus: "brachial_plexus","BP_L","BP_R";
       PharynxConstrictor: "pharynx","constrictor","MPC"; ChestWall: "chest_wall","CW";
       NormalBrain: "normal_brain","brain_minus_gtv")
- [ ] `outputs/reporter.py` — `Data_Source` column; SYNTHETIC rows in orange
- [ ] `tests/test_utcp.py` — 12 tests pass, specifically:
      - test_utcp_brain_gbm_includes_hippocampus (NEW — NCOG-41 evidence)
      - test_utcp_brain_gbm_includes_cochlea_and_pituitary (NEW — EORTC guideline)
      - test_utcp_brain_mets_includes_hippocampus_and_cochlea (updated — cochlea added)
      - test_utcp_breast_includes_esophagus_thyroid_brachial (NEW)
      - test_utcp_breast_spinal_cord_weight_not_1 (NEW — clinical correctness)
- [ ] `tests/test_quantec.py` — 4 tests pass
- [ ] `tests/test_safety_guard.py` — 4 tests pass
- [ ] `pytest tests/ -v` — full suite green, zero failures

**Full integration test:**
```bash
python -m rbgyanx_engine \
  --endpoint both \
  --input-kind dicom \
  --input-dir sumanplandvh/ \
  --site LUNG \
  --output-dir rbgyanx_output/ \
  --figures --verbose
```

Expected outputs:
- `tcp_benchmarking.xlsx`: UTCP, UTCP_weighted columns present
- `ntcp_benchmarking.xlsx`: QUANTEC_Flags sheet present
- `quantec_flags.csv`: created (may be empty if no violations in test case)
- `provenance.json`, `qa_report.json`: created, exit code 0
