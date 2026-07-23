# rbGyanX Dual-Mode Implementation Strategy
## From Current State to Manifesto-Compliant Architecture

**Date**: January 12, 2026  
**Author**: KB + Claude  
**Status**: Strategic Implementation Plan

---

## EXECUTIVE SUMMARY

This document provides a **complete gap analysis** between your current rbGyanX software and the manifesto-compliant dual-mode (BASIC + ADVANCED) architecture. It includes:

1. **Current State Assessment** - What you have now
2. **Gap Analysis** - What needs to change
3. **Strategic Implementation Roadmap** - How to get there
4. **Risk Mitigation** - How to avoid breaking existing functionality
5. **Concrete Next Steps** - What to do first

---

## 1. CURRENT STATE ASSESSMENT

### 1.1 Architecture Overview

Your existing `rbgyanx_dual` software has the following structure:

```
rbgyanx_dual/
├── Core Computational Scripts (Legacy)
│   ├── code1_dvh_preprocess.py           # DVH parsing and preprocessing
│   ├── code2_dvh_plot_and_summary.py     # Physical metrics and plots
│   ├── code3_ntcp_analysis_ml.py         # NTCP models + ML (138KB!)
│   ├── code4_ntcp_output_QA_reporter.py  # QA checks and reporting
│   ├── code5_ntcp_factors_analysis.py    # Clinical factor analysis
│   ├── code6_tcp_analysis.py             # TCP models and analysis
│   └── code7_tcp_ntcp_integration.py     # TCP/NTCP integration
│
├── GUI Layer
│   └── rbgyanx_gui.py                    # Monolithic GUI (371KB, 8301 lines!)
│
├── Partial Modularization
│   ├── core/                             # Some state management
│   │   ├── project_state.py
│   │   └── feature_registry.json
│   ├── utils/                            # Utilities (DVH parser, errors)
│   ├── qa/                               # QA modules
│   ├── ask_rbgyanx/                      # AI assistant (partial)
│   ├── ai/                               # Local LLM engine
│   ├── clinical/                         # Clinical data adapter
│   └── models/                           # (Directory exists)
│
├── Configuration
│   └── config/                           # YAML configs for parameters
│
└── Testing
    └── tests/                            # Existing test suite
```

### 1.2 Key Findings

#### ✅ **Strengths (What's Already Good)**

1. **Comprehensive Functionality**: Full TCP/NTCP pipeline with ML integration
2. **Some Modularization**: Utilities, QA, and AI modules exist
3. **Testing Infrastructure**: Test suite already established
4. **Configuration Management**: YAML-based parameter configuration
5. **QA Framework**: Quality assurance modules present
6. **AI Integration**: Ask rbGyanX assistant partially implemented
7. **Documentation**: Multiple README files and user manual generator

#### ⚠️ **Critical Issues (Major Gaps)**

1. **No 3-Layer Architecture**: Code violates layer separation
   - GUI (`rbgyanx_gui.py`) is **371KB** and **8301 lines** - massive monolith
   - Direct mixing of UI, logic, and computation
   - `code3_ntcp_analysis_ml.py` is **138KB** - contains everything

2. **No ModeController**: BASIC/ADVANCED is only cosmetic branding
   - GUI shows "BASIC" in title but no governance layer exists
   - No capability exposure system
   - No mode-aware behavior enforcement
   - Comment mentions "switch to rbGyanX_advanced" but no actual implementation

3. **Legacy Script Architecture**: 7 separate `code*.py` scripts
   - Sequential pipeline through scripts, not orchestrated
   - Heavy interdependencies
   - Difficult to test in isolation

4. **UI Directly Calls Computation**: Severe layer violation
   - No orchestration layer
   - GUI likely calls `subprocess` to run scripts
   - Cannot run headless effectively

5. **No Applicability Gating**: Missing safety layer
   - No runtime model validity checks
   - No CCS (Conformal Consensus Score) enforcement
   - Biological calculations run without domain validation

6. **Incomplete AI Integration**: Ask rbGyanX exists but not mode-aware
   - No dual-personality (BASIC vs ADVANCED)
   - May not have proper explanation-only constraints
   - Unclear governance

### 1.3 Functional Capabilities (Current)

**What your software CAN do:**
- ✅ Parse DVH files from TPS exports
- ✅ Compute physical dose metrics
- ✅ Calculate NTCP (LKB, Relative Seriality models)
- ✅ Train ML models (ANN, XGBoost) for NTCP prediction
- ✅ Calculate TCP (Poisson and variants)
- ✅ Generate plots and reports
- ✅ Perform QA checks on outputs
- ✅ Clinical factor analysis
- ✅ AI-assisted explanations (partial)
- ✅ Configuration management

**What your software CANNOT do (yet):**
- ❌ Enforce BASIC vs ADVANCED governance
- ❌ Runtime applicability checks before biological calculations
- ❌ Mode-aware capability exposure
- ❌ Model agreement/disagreement analysis
- ❌ Parameter sensitivity analysis
- ❌ Uncertainty decomposition (aleatoric, epistemic, structural)
- ❌ Robustness indices
- ❌ Explicit model failure detection
- ❌ Provenance tracking and reproducibility bundles
- ❌ Developer mode with tracked modifications
- ❌ Research-only experimental features

---

## 2. GAP ANALYSIS

### 2.1 Architecture Gaps

| Requirement | Current State | Gap Severity | Effort to Fix |
|-------------|---------------|--------------|---------------|
| **3-Layer Architecture** | Monolithic mixing | 🔴 CRITICAL | HIGH |
| **ModeController** | Non-existent | 🔴 CRITICAL | MEDIUM |
| **Orchestration Layer** | Scripts + subprocess | 🔴 CRITICAL | HIGH |
| **UI Layer Separation** | 371KB monolith | 🔴 CRITICAL | HIGH |
| **Core Layer Purity** | Mixed with logic | 🟡 HIGH | MEDIUM |
| **Clean Imports** | Circular risks | 🟡 HIGH | MEDIUM |

### 2.2 Governance Gaps

| Requirement | Current State | Gap Severity | Effort to Fix |
|-------------|---------------|--------------|---------------|
| **Mode Selection** | Cosmetic only | 🔴 CRITICAL | LOW |
| **Capability Exposure** | Non-existent | 🔴 CRITICAL | MEDIUM |
| **Applicability Gate** | Missing | 🔴 CRITICAL | HIGH |
| **Runtime Validation** | Minimal | 🟡 HIGH | MEDIUM |
| **Mode Immutability** | Not enforced | 🟡 HIGH | LOW |
| **Provenance Tracking** | Partial | 🟢 MEDIUM | MEDIUM |

### 2.3 Scientific Features Gaps

| Feature | Current State | Gap Severity | Effort to Fix |
|---------|---------------|--------------|---------------|
| **Model Agreement Analysis** | Non-existent | 🟡 HIGH | MEDIUM |
| **Parameter Sensitivity** | Non-existent | 🟡 HIGH | MEDIUM |
| **Uncertainty Decomposition** | Non-existent | 🟡 HIGH | HIGH |
| **Robustness Indices** | Non-existent | 🟢 MEDIUM | MEDIUM |
| **Applicability Detection** | Non-existent | 🔴 CRITICAL | HIGH |
| **Model Failure Detection** | Minimal QA | 🟡 HIGH | MEDIUM |

### 2.4 AI Integration Gaps

| Feature | Current State | Gap Severity | Effort to Fix |
|---------|---------------|--------------|---------------|
| **Dual Personality** | Single mode | 🟡 HIGH | LOW |
| **Explanation-Only** | Unclear | 🟡 HIGH | MEDIUM |
| **Mode-Aware Prompts** | Non-existent | 🟡 HIGH | LOW |
| **Structured Queries** | Basic | 🟢 MEDIUM | LOW |
| **Safety Filters** | Unknown | 🟡 HIGH | MEDIUM |

---

## 3. STRATEGIC IMPLEMENTATION ROADMAP

### 3.1 Philosophy: Incremental Transformation, Not Rewrite

**Critical Principle**: We will **NOT rewrite from scratch**. Instead:

1. **Extract and refactor** existing functionality incrementally
2. **Preserve all existing features** during transformation
3. **Add governance layer** without breaking current workflows
4. **Test continuously** at each step
5. **Maintain backward compatibility** where possible

### 3.2 Implementation Phases (Prioritized)

#### 🚨 **PHASE 0: Pre-Implementation Setup** (Week 1)
*Foundation before touching code*

**Objectives**:
- Set up version control properly
- Create development branch
- Establish testing baseline
- Document current behavior

**Tasks**:
```bash
# 1. Git initialization (if not done)
cd rbgyanx_dual
git init
git add .
git commit -m "Baseline: Current rbGyanX dual before refactor"
git branch develop
git checkout develop

# 2. Baseline testing
python -m pytest tests/ --tb=short > baseline_tests.log

# 3. Create baseline outputs
python rbgyanx_gui.py --test-mode --save-baseline
```

**Deliverables**:
- ✅ Git repository with baseline commit
- ✅ Baseline test results documented
- ✅ Known good outputs captured
- ✅ Development environment isolated

---

#### 🏗️ **PHASE 1: Architecture Foundation** (Weeks 2-4)
*Implement 3-layer separation without feature changes*

**Sub-Phase 1.1: Create Directory Structure**
```bash
rbgyanx/
├── __init__.py
├── core/                    # Layer 1: Pure computation
│   ├── __init__.py
│   ├── dvh/                 # DVH processing
│   ├── tcp_models/          # TCP calculations
│   ├── ntcp_models/         # NTCP calculations
│   ├── biological/          # Biological normalization
│   ├── qa_metrics/          # QA computations
│   └── uncertainty/         # Uncertainty calculations
│
├── logic/                   # Layer 2: Orchestration
│   ├── __init__.py
│   ├── pipeline.py          # Main pipeline orchestration
│   ├── applicability.py     # Applicability checks
│   ├── qa_engine.py         # QA orchestration
│   └── mode_controller.py   # Mode governance (NEW)
│
└── ui/                      # Layer 3: Presentation
    ├── __init__.py
    ├── main_window.py       # Refactored GUI
    ├── startup/             # Mode selection (NEW)
    ├── basic/               # BASIC mode UI
    ├── advanced/            # ADVANCED mode UI (NEW)
    └── components/          # Reusable UI components
```

**Migration Strategy**:
1. **Extract core computations from `code3_ntcp_analysis_ml.py`**:
   - Pure TCP/NTCP math → `rbgyanx/core/tcp_models/`, `ntcp_models/`
   - ML training orchestration → `rbgyanx/logic/`
   - Plotting → `rbgyanx/ui/components/`

2. **Extract orchestration from scripts**:
   - Pipeline sequencing → `rbgyanx/logic/pipeline.py`
   - Keep scripts as thin CLI wrappers (for now)

3. **Refactor monolithic GUI**:
   - Break 8301-line file into logical components
   - Separate UI widgets from business logic
   - Move all computation calls to logic layer

**Validation After Phase 1**:
```python
# Must pass:
def test_phase1_equivalence():
    """Outputs identical to baseline"""
    old = run_baseline_analysis()
    new = run_refactored_analysis()
    assert np.allclose(old.ntcp, new.ntcp)
    assert np.allclose(old.tcp, new.tcp)
    assert old.plots_match(new)
```

---

#### 🎛️ **PHASE 2: Mode Controller Implementation** (Week 5)
*Add governance without changing behavior*

**Objectives**:
- Implement `ModeController` class
- Add mode selection at startup (placeholder)
- Wire mode through pipeline
- **NO new features, just infrastructure**

**Implementation**:
```python
# rbgyanx/logic/mode_controller.py
# (Use code from staged prompt Phase A.3)

from enum import Enum
from dataclasses import dataclass
from typing import Dict

class RunMode(Enum):
    BASIC = "basic"
    ADVANCED = "advanced"

class ModeController:
    """Governance layer for BASIC vs ADVANCED operation"""
    def __init__(self, mode: RunMode):
        self._mode = mode
        self._capabilities = self._init_capabilities()
    
    def get_capabilities(self) -> Dict[str, bool]:
        # Initially all False
        return {
            "model_comparison": False,
            "parameter_sweep": False,
            "applicability_override": False,
            "developer_mode": False
        }
    # ... rest from Phase A.3 template
```

**Integration**:
```python
# rbgyanx/logic/pipeline.py
def run_analysis_pipeline(
    inputs: PipelineInput,
    mode_controller: ModeController = None
) -> PipelineOutput:
    if mode_controller is None:
        mode_controller = ModeController(RunMode.BASIC)
    
    # Pipeline proceeds as before, but logs mode
    logs.append(f"Running in {mode_controller.mode} mode")
    # ... existing pipeline logic
```

**Validation After Phase 2**:
```python
def test_mode_controller_passive():
    """Mode exists but doesn't change behavior yet"""
    basic = run_with_mode(RunMode.BASIC)
    advanced = run_with_mode(RunMode.ADVANCED)
    
    # Should be identical for now
    assert results_match(basic, advanced)
```

---

#### 🚪 **PHASE 3: Startup Screen** (Week 6)
*Force explicit mode selection*

**Objectives**:
- Create startup dialog for mode selection
- Add ADVANCED mode disclaimer
- Make mode immutable per session

**Implementation**:
```python
# rbgyanx/ui/startup/mode_selection.py

import tkinter as tk
from tkinter import ttk, messagebox
from rbgyanx.logic.mode_controller import RunMode, ModeController

class ModeSelectionDialog:
    """Startup dialog for BASIC vs ADVANCED mode selection"""
    
    def show(self) -> ModeController:
        """Display dialog and return selected mode controller"""
        # Create modal dialog
        dialog = tk.Toplevel()
        dialog.title("rbGyanX Mode Selection")
        
        # Mode selection buttons
        btn_basic = ttk.Button(
            dialog,
            text="BASIC MODE\nGoverned Clinical & Academic Support",
            command=lambda: self._select_basic(dialog)
        )
        
        btn_advanced = ttk.Button(
            dialog,
            text="ADVANCED MODE\nResearch & Experimental",
            command=lambda: self._select_advanced(dialog)
        )
        
        # Wait for selection
        dialog.wait_window()
        return self.selected_mode_controller
    
    def _select_advanced(self, dialog):
        """Show disclaimer before enabling ADVANCED"""
        disclaimer = (
            "ADVANCED MODE — Research Use Only\n\n"
            "This mode enables experimental features that may operate "
            "outside validated domains. Results must not be used for "
            "clinical decision-making.\n\n"
            "Do you understand and accept these limitations?"
        )
        
        if messagebox.askyesno("Advanced Mode Warning", disclaimer):
            self.selected_mode_controller = ModeController(RunMode.ADVANCED)
            dialog.destroy()
```

**Validation After Phase 3**:
- ✅ Application cannot start without mode selection
- ✅ ADVANCED requires disclaimer acceptance
- ✅ Mode displayed in UI persistently

---

#### 🔬 **PHASE 4: Applicability Gate** (Weeks 7-8)
*Add safety layer before biological calculations*

**Objectives**:
- Implement CCS (Conformal Consensus Score) or similar
- Check treatment technique compatibility with models
- Block biological calculations when unsafe
- **This is the most critical safety feature**

**Implementation**:
```python
# rbgyanx/logic/applicability.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum

class TreatmentTechnique(Enum):
    CONVENTIONAL = "conventional"  # 1.8-2.2 Gy
    HYPOFRACTIONATION = "hypofractionation"  # 2.5-5 Gy
    SBRT = "sbrt"
    SRS = "srs"
    BRACHYTHERAPY = "brachytherapy"
    UNKNOWN = "unknown"

class BiologicalModel(Enum):
    LQ = "lq"
    LQL = "lql"
    MODIFIED_LQ = "modified_lq"
    GLQ = "glq"
    PHYSICAL_ONLY = "physical_only"

@dataclass
class ApplicabilityResult:
    """Result of applicability check"""
    biological_allowed: bool
    selected_model: Optional[BiologicalModel]
    reason: str
    confidence: str  # "high", "medium", "low"
    warnings: list[str]

class ApplicabilityChecker:
    """
    Determines if biological modeling is scientifically valid
    for the given treatment context.
    """
    
    # Model applicability matrix (from Manifesto Table 2)
    VALIDITY_MATRIX = {
        TreatmentTechnique.CONVENTIONAL: {
            BiologicalModel.LQ: "valid",
            BiologicalModel.LQL: "valid",
            BiologicalModel.MODIFIED_LQ: "context_dependent",
            BiologicalModel.GLQ: "valid",
        },
        TreatmentTechnique.SBRT: {
            BiologicalModel.LQ: "not_recommended",
            BiologicalModel.LQL: "limited",
            BiologicalModel.MODIFIED_LQ: "valid",
            BiologicalModel.GLQ: "preferred",
        },
        # ... full matrix from manifesto
    }
    
    def check_applicability(
        self,
        technique: TreatmentTechnique,
        fraction_size: float,
        requested_model: BiologicalModel,
        mode_controller: ModeController
    ) -> ApplicabilityResult:
        """
        Check if biological calculation is appropriate.
        
        In BASIC mode: Strict enforcement
        In ADVANCED mode: Warnings only (for now)
        """
        
        validity = self.VALIDITY_MATRIX.get(technique, {}).get(requested_model)
        
        if validity == "valid":
            return ApplicabilityResult(
                biological_allowed=True,
                selected_model=requested_model,
                reason="Model validated for this technique",
                confidence="high",
                warnings=[]
            )
        
        elif validity == "not_recommended":
            if mode_controller.is_basic():
                # BASIC mode: Block
                return ApplicabilityResult(
                    biological_allowed=False,
                    selected_model=BiologicalModel.PHYSICAL_ONLY,
                    reason=f"{requested_model.value.upper()} not recommended for {technique.value}",
                    confidence="high",
                    warnings=["Biological calculation blocked by applicability gate"]
                )
            else:
                # ADVANCED mode: Allow with strong warning
                return ApplicabilityResult(
                    biological_allowed=True,
                    selected_model=requested_model,
                    reason="EXPERIMENTAL: Extrapolating outside validated domain",
                    confidence="low",
                    warnings=["WARNING: Model validity questionable for this technique"]
                )
        
        # ... rest of logic
```

**Integration into Pipeline**:
```python
# rbgyanx/logic/pipeline.py

def run_analysis_pipeline(inputs, mode_controller):
    # ... physical analysis (always runs)
    
    # APPLICABILITY CHECK (NEW)
    applicability = ApplicabilityChecker().check_applicability(
        technique=inputs.treatment_info.technique,
        fraction_size=inputs.treatment_info.fraction_size,
        requested_model=inputs.config.biological_model,
        mode_controller=mode_controller
    )
    
    if applicability.biological_allowed:
        biological_results = compute_biological_metrics(
            physical_results,
            applicability.selected_model
        )
    else:
        biological_results = None
        logs.append(f"Biological blocked: {applicability.reason}")
    
    # ... rest of pipeline
```

**Validation After Phase 4**:
```python
def test_applicability_enforcement():
    """Verify applicability gate works"""
    
    # BASIC mode with SBRT + LQ → should block
    basic_mc = ModeController(RunMode.BASIC)
    sbrt_input = create_sbrt_test_case()
    sbrt_input.config.biological_model = BiologicalModel.LQ
    
    result = run_analysis_pipeline(sbrt_input, basic_mc)
    assert result.biological_results is None
    assert "blocked" in result.logs[-1].lower()
    
    # ADVANCED mode with same → should warn but allow
    advanced_mc = ModeController(RunMode.ADVANCED)
    result = run_analysis_pipeline(sbrt_input, advanced_mc)
    assert result.biological_results is not None
    assert any("WARNING" in log for log in result.logs)
```

---

#### 🔬 **PHASE 5-8: ADVANCED Features** (Weeks 9-16)
*Incrementally add research capabilities*

These phases add the scientific features from the manifesto:

- **Phase 5**: Model Agreement/Disagreement Analysis (C.2)
- **Phase 6**: Parameter Sensitivity Analysis (C.3)
- **Phase 7**: Uncertainty Decomposition (C.4)
- **Phase 8**: Robustness Indices (C.5)

**Each follows same pattern**:
1. Implement in `rbgyanx/logic/` (computational logic)
2. Add UI in `rbgyanx/ui/advanced/` (visualization)
3. Gate behind `mode_controller.is_capability_enabled("feature_name")`
4. Test in isolation
5. Only enable in ADVANCED mode after validation

---

#### 🤖 **PHASE 9: AI Refinement** (Weeks 17-18)
*Dual personality Ask rbGyanX*

**Objectives**:
- Split Ask rbGyanX into BASIC and ADVANCED personalities
- Implement explanation-only constraints
- Add structured "Why Not?" queries

**Implementation**:
```python
# rbgyanx/logic/ask_rbgyanx_profiles.py

class AskRbGyanXProfile:
    """AI behavior profile for mode-aware assistance"""
    
    BASIC_PROFILE = {
        "tone": "conservative, cautious",
        "allowed": [
            "explain_models",
            "explain_uncertainty",
            "explain_blocking"
        ],
        "forbidden": [
            "model_comparison",
            "hypotheticals",
            "sensitivity_speculation"
        ],
        "system_prompt": (
            "You are a conservative clinical AI assistant. "
            "Explain concepts clearly but avoid any comparative "
            "or speculative analysis. Never suggest actions."
        )
    }
    
    ADVANCED_PROFILE = {
        "tone": "analytical, exploratory",
        "allowed": [
            "explain_divergence",
            "discuss_assumptions",
            "suggest_experiments"  # NOT clinical actions
        ],
        "forbidden": [
            "clinical_recommendations",
            "optimization",
            "prospective_prediction"
        ],
        "system_prompt": (
            "You are a research-oriented AI assistant. "
            "Analyze model behavior, explain divergence, and "
            "suggest experiments. Never recommend clinical actions."
        )
    }
```

---

#### 🛠️ **PHASE 10: Developer Mode** (Weeks 19-20)
*Governed experimentation environment*

Enable researchers to prototype safely with full tracking.

---

### 3.3 Risk Mitigation Strategy

#### Risk 1: Breaking Existing Functionality

**Mitigation**:
- **Comprehensive regression testing** after each phase
- **Feature flags** for new capabilities (off by default)
- **Parallel execution** of old and new code during transition
- **Rollback plan** at each phase

#### Risk 2: User Confusion During Transition

**Mitigation**:
- **Clear migration guide** for existing users
- **Backward compatibility mode** (optional)
- **Visual indicators** of which mode is active
- **Documentation updates** concurrent with changes

#### Risk 3: Performance Degradation

**Mitigation**:
- **Benchmark critical paths** before and after
- **Profile hot spots** in refactored code
- **Lazy loading** of heavy modules
- **Caching strategies** for repeated computations

#### Risk 4: Scientific Correctness

**Mitigation**:
- **Validation suite** with known-good cases
- **Cross-check against published results**
- **Peer review** of mathematical implementations
- **Conservative defaults** (BASIC mode)

---

## 4. CONCRETE NEXT STEPS

### Step 1: Environment Setup (Do This First)

```bash
# 1. Create development branch
cd /path/to/rbgyanx_dual
git init  # if not already done
git add .
git commit -m "Baseline: rbGyanX dual pre-refactor"
git branch develop
git checkout develop

# 2. Install development dependencies
pip install pytest pytest-cov black mypy pylint

# 3. Run baseline tests
python -m pytest tests/ -v > baseline_test_results.txt

# 4. Create validation test cases
python -c "
import numpy as np
import pickle

# Generate test cases with known outputs
test_cases = {
    'conventional_lq': {...},  # Known TCP/NTCP values
    'sbrt_glq': {...},
    # Add more
}

with open('validation_baseline.pkl', 'wb') as f:
    pickle.dump(test_cases, f)
"
```

### Step 2: Architecture Refactor (Phase 1)

**Week 1 Tasks**:
```bash
# 1. Create new directory structure
mkdir -p rbgyanx/core/{dvh,tcp_models,ntcp_models,biological,qa_metrics,uncertainty}
mkdir -p rbgyanx/logic
mkdir -p rbgyanx/ui/{startup,basic,advanced,components}

# 2. Extract pure TCP calculations from code6_tcp_analysis.py
# Move to rbgyanx/core/tcp_models/poisson.py
# (Use Cursor with Phase A.1 prompt)

# 3. Extract pure NTCP calculations from code3_ntcp_analysis_ml.py
# Move to rbgyanx/core/ntcp_models/lkb.py
# (Use Cursor with Phase A.1 prompt)

# 4. Test after each extraction
python -m pytest tests/test_tcp_models.py -v
```

**Week 2 Tasks**:
```bash
# 1. Create pipeline orchestration
# rbgyanx/logic/pipeline.py
# (Use template from Phase A.2 prompt)

# 2. Extract orchestration logic from code scripts
# Move sequential execution to pipeline.py

# 3. Test pipeline equivalence
python tests/test_pipeline_equivalence.py
```

**Week 3-4 Tasks**:
```bash
# 1. Break apart monolithic GUI
# Start with extracting plot functions
# Move to rbgyanx/ui/components/plots.py

# 2. Create modular UI components
# rbgyanx/ui/components/dvh_viewer.py
# rbgyanx/ui/components/results_panel.py

# 3. Refactor main window to use components
# Keep behavior identical

# 4. Final validation
python tests/test_full_workflow.py
python tests/test_gui_integration.py
```

### Step 3: Mode Controller (Phase 2)

```bash
# Week 5
# 1. Implement ModeController class
# Use template from Phase A.3 prompt
# File: rbgyanx/logic/mode_controller.py

# 2. Integrate with pipeline
# Modify rbgyanx/logic/pipeline.py

# 3. Add mode display to UI
# Update rbgyanx/ui/main_window.py

# 4. Test mode immutability
python tests/test_mode_controller.py
```

### Step 4: Applicability Gate (Phase 4)

**This is CRITICAL for safety - don't skip**

```bash
# Weeks 7-8
# 1. Implement ApplicabilityChecker
# File: rbgyanx/logic/applicability.py
# (Use template from Phase 4 section above)

# 2. Create applicability matrix
# Data structure from Manifesto Table 2

# 3. Integrate into pipeline
# Add gating before biological calculations

# 4. Test thoroughly
python tests/test_applicability.py
python tests/test_applicability_integration.py
```

### Step 5: Iterative Feature Addition (Phases 5+)

After Phase 4, add features incrementally:
- One feature per week
- Full testing before next
- Always gated behind ADVANCED mode
- No breaking changes to BASIC mode

---

## 5. CURSOR PROMPTING STRATEGY

### How to Use the Staged Prompt with Your Code

For each phase, use this pattern with Cursor:

```
I am implementing Phase [X] of the rbGyanX refactor.

Context:
- Current codebase: [describe relevant files]
- Phase objective: [from staged prompt]
- Previous phases: [completed/validated]

Please help me:
1. [Specific implementation task]
2. Ensure no behavior changes
3. Follow 3-layer architecture
4. Add appropriate tests

Relevant files:
- [list files to modify]

Constraints:
- Maintain backward compatibility
- No new dependencies unless critical
- All changes must be reversible
```

### Example Cursor Prompt for Phase 1

```
I am implementing Phase A.1 (3-layer architecture) for rbGyanX.

Current state:
- code3_ntcp_analysis_ml.py: 138KB monolith with NTCP + ML
- Need to extract pure NTCP calculations to rbgyanx/core/ntcp_models/

Objective:
Extract the LKB (log-logit and probit) NTCP calculation functions from 
code3_ntcp_analysis_ml.py and move them to rbgyanx/core/ntcp_models/lkb.py

Requirements:
1. Pure functions: no UI, no file I/O
2. Clear docstrings with assumptions
3. Type hints everywhere
4. Must produce identical numerical results
5. Add unit tests

Please help me:
1. Identify the LKB calculation code in code3_ntcp_analysis_ml.py
2. Extract it to a clean module
3. Write unit tests
4. Verify numerical equivalence

Files to examine:
- code3_ntcp_analysis_ml.py (source)
- tests/test_ntcp_models.py (existing tests to extend)
```

---

## 6. SUCCESS CRITERIA

### Phase Completion Checklist

For **EACH** phase, verify:

- ✅ **Functional**: Feature works as specified
- ✅ **Regression**: All existing tests pass
- ✅ **Equivalence**: Outputs match baseline (where applicable)
- ✅ **Architecture**: Layer boundaries respected
- ✅ **Documentation**: Code documented, intent clear
- ✅ **Reversible**: Can roll back if needed
- ✅ **Performance**: No significant slowdown
- ✅ **User-facing**: No unexpected UI changes (unless intended)

### Overall Success Criteria

rbGyanX refactor is **COMPLETE** when:

1. ✅ All code follows 3-layer architecture
2. ✅ ModeController fully operational
3. ✅ BASIC mode: Conservative, safe, validated
4. ✅ ADVANCED mode: Research features unlocked
5. ✅ Applicability gate enforces scientific validity
6. ✅ All original features preserved
7. ✅ Test coverage >80%
8. ✅ Performance ≥ baseline
9. ✅ Documentation complete
10. ✅ Manifesto principles embodied in code

---

## 7. TIMELINE ESTIMATE

**Conservative Estimate** (assuming full-time development):

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 0: Setup | 1 week | 1 week |
| Phase 1: Architecture | 3 weeks | 4 weeks |
| Phase 2: ModeController | 1 week | 5 weeks |
| Phase 3: Startup Screen | 1 week | 6 weeks |
| Phase 4: Applicability Gate | 2 weeks | 8 weeks |
| Phase 5-8: Advanced Features | 8 weeks | 16 weeks |
| Phase 9: AI Refinement | 2 weeks | 18 weeks |
| Phase 10: Developer Mode | 2 weeks | 20 weeks |
| Testing & Polish | 4 weeks | 24 weeks |

**Total: ~6 months** for complete manifesto compliance.

**Realistic Estimate** (part-time, with PhD commitments):
**12-18 months** for full implementation.

### Minimum Viable Product (MVP)

Can achieve a **functional dual-mode rbGyanX** in:
- **2-3 months** if focusing on Phases 0-4 only
- This gives you: Architecture + Mode governance + Applicability
- Sufficient for publication and demonstration
- Advanced features can be added later

---

## 8. RECOMMENDED DEVELOPMENT WORKFLOW

### Daily Workflow

```bash
# Morning: Check status
git status
python -m pytest tests/ -k "not slow"

# Development cycle
1. Read relevant section of staged prompt
2. Implement small change
3. Test immediately
4. Commit if tests pass
5. Repeat

# End of day: Full test suite
python -m pytest tests/ -v --cov=rbgyanx
git commit -am "Phase X.Y: [description]"
```

### Weekly Review

Every Friday:
1. Review progress against roadmap
2. Run full validation suite
3. Update documentation
4. Identify blockers
5. Adjust timeline if needed

---

## 9. GETTING HELP

### When You're Stuck

1. **Consult the manifesto** for philosophical guidance
2. **Re-read the staged prompt** for the current phase
3. **Check existing tests** for examples
4. **Ask Cursor/Claude** with specific context
5. **Take a break** - complex refactors require mental clarity

### Red Flags to Watch For

🚩 Tests suddenly failing without clear reason  
🚩 Import cycles appearing  
🚩 Performance degrading significantly  
🚩 Scientific outputs changing unexpectedly  
🚩 Feeling overwhelmed by scope  

**When you see red flags: STOP, REVERT, RE-PLAN**

---

## 10. FINAL WORDS

### You Are Building Something Important

This is not just a software refactor. This is:
- A **scientific contribution** (methodology matters)
- An **ethical statement** (AI should empower, not replace)
- A **reference implementation** (others will learn from this)
- A **PhD thesis component** (publishable architecture)

### The Manifesto Exists for a Reason

Every constraint in the manifesto protects:
- **Patients**: From overconfident AI
- **Clinicians**: From black-box decisions
- **Researchers**: From irreproducible science
- **You**: From building something you can't defend

### Slow is Smooth, Smooth is Fast

It's tempting to rush. **Resist that temptation.**

- Take time to understand each phase
- Test thoroughly before proceeding
- Don't skip validation steps
- Celebrate small wins

**You're not just coding. You're architecting trust.**

---

## APPENDIX A: File Mapping (Current → Target)

| Current File | Target Location(s) | Notes |
|--------------|-------------------|-------|
| `code1_dvh_preprocess.py` | `rbgyanx/core/dvh/parser.py` | Extract pure parsing |
| `code2_dvh_plot_and_summary.py` | `rbgyanx/core/dvh/metrics.py` + `ui/components/plots.py` | Split calculation and plotting |
| `code3_ntcp_analysis_ml.py` | `rbgyanx/core/ntcp_models/*.py` + `logic/ml_training.py` | Massive decomposition needed |
| `code4_ntcp_output_QA_reporter.py` | `rbgyanx/logic/qa_engine.py` + `ui/components/reports.py` | Split logic and presentation |
| `code5_ntcp_factors_analysis.py` | `rbgyanx/logic/clinical_analysis.py` | Orchestration layer |
| `code6_tcp_analysis.py` | `rbgyanx/core/tcp_models/*.py` + `logic/tcp_pipeline.py` | Split models and orchestration |
| `code7_tcp_ntcp_integration.py` | `rbgyanx/logic/integration.py` | High-level orchestration |
| `rbgyanx_gui.py` (8301 lines!) | `rbgyanx/ui/*.py` (many files) | Major decomposition |

---

## APPENDIX B: Quick Reference Commands

```bash
# Setup
git init && git checkout -b develop

# Run baseline tests
python -m pytest tests/ -v > baseline.log

# Run specific phase tests
python -m pytest tests/test_phase_a1.py -v

# Check import hygiene
python -c "import ast; # check imports script"

# Profile performance
python -m cProfile -o profile.stats rbgyanx_gui.py

# Check coverage
python -m pytest --cov=rbgyanx --cov-report=html

# Validate against baseline
python validate_equivalence.py --baseline baseline_outputs/

# Commit after phase
git commit -am "Phase A.X complete - [description]"
```

---

## APPENDIX C: Communication Template for Updates

When reporting progress (e.g., to supervisors):

```
rbGyanX Refactor Progress Report

Week: [X]
Phase: [Y]
Status: [On Track / Blocked / Complete]

Completed:
✅ [Task 1]
✅ [Task 2]

In Progress:
⏳ [Task 3] - 60% complete

Blocked:
🚫 [Issue] - [Brief description]

Tests:
- Passing: X/Y
- New tests added: Z
- Coverage: N%

Next Week:
- [Plan for next week]

Questions/Concerns:
- [Any issues]
```

---

**END OF STRATEGIC IMPLEMENTATION PLAN**

You now have everything you need to transform your existing rbGyanX software into a manifesto-compliant, state-of-the-art clinical + research + learning platform.

**Remember: This is a marathon, not a sprint. Every step forward is progress.**

Good luck, KB. You're building something that matters.
