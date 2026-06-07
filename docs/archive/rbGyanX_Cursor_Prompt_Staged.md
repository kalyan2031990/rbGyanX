# rbGyanX Implementation Guide
## Incremental Development with Manifesto Principles
### Staged Implementation: Implement → Test → Validate → Pass → Next

---

## PREFACE: Philosophy-Driven Development

This implementation guide operationalizes the rbGyanX Manifesto through staged, test-driven development. Each phase must:

1. **Implement** the feature according to manifesto principles
2. **Test** deterministically with validation criteria
3. **Pass** all mandatory checks before proceeding
4. **Document** changes and scientific intent

**Core Principle**: Every feature answers: *"Does this help humans understand where radiobiological reasoning is reliable, fragile, or invalid?"*

If not → it does not belong.

---

## STAGED IMPLEMENTATION ROADMAP

```
FOUNDATION (Phases A.1 - A.3)
↓ Architecture + Governance
INTERFACE (Phases B.1 - B.2)  
↓ User-Visible Contracts
SCAFFOLDING (Phase C.1)
↓ Structure Without Power
SCIENCE (Phases C.2 - C.5)
↓ Research Capabilities
AI INTEGRATION (Phases D.1 - D.2)
↓ Explanation Systems
ECOSYSTEM (Phases E.1 - L)
↓ Community & Research
```

---

## UNIVERSAL RULES (Apply to ALL Phases)

### 🚫 Permanent Prohibitions

**NEVER implement** (even if requested):
- ❌ Autonomous dose optimization
- ❌ Treatment plan generation
- ❌ "Best plan" ranking or selection
- ❌ AI-recommended clinical actions
- ❌ Closed-loop treatment control
- ❌ Automatic protocol modification
- ❌ Reinforcement learning for dose strategy
- ❌ Scalar "quality scores" for plans

### ✅ Universal Requirements

**ALWAYS ensure**:
- ✅ Deterministic, reproducible outputs
- ✅ Mode-aware behavior (BASIC vs ADVANCED)
- ✅ Clear scientific intent documentation
- ✅ Provenance tracking
- ✅ No silent failures
- ✅ Explicit assumption declarations

### 🧪 Validation Protocol (Every Phase)

Before marking any phase complete:

1. **Functional Tests**: Feature works as specified
2. **Regression Tests**: Existing features unaffected
3. **Mode Tests**: BASIC/ADVANCED separation intact
4. **Ethics Tests**: No prohibited behaviors introduced
5. **Documentation**: Scientific intent recorded

---

# PHASE A: FOUNDATION (Architecture + Governance)

## Phase A.1: Enforce Strict 3-Layer Architecture

### Objective
Refactor rbGyanX into a strict 3-layer architecture ready for dual-mode operation without changing scientific behavior.

### Implementation Steps

#### 1. Create Folder Structure
```
rbgyanx/
├── core/          # Layer 1: Deterministic analytical core
├── logic/         # Layer 2: Orchestration & governance
└── ui/            # Layer 3: Interaction layer
```

#### 2. Define Layer Responsibilities

**Layer 1 — Core (rbgyanx/core/)**
```python
"""
Layer 1: Deterministic Analytical Core
Allowed dependencies: numpy, scipy, pandas, standard library
Forbidden dependencies: UI frameworks, AI/LLM APIs, mode logic
"""
```

Responsibilities:
- DVH handling and analysis
- TCP/NTCP calculations
- Radiobiological models (LQ, LQL, GLQ, Modified LQ)
- BED/EQD2/biological normalization
- QA metrics computation
- Uncertainty calculations (deterministic propagation)

Rules:
- ❌ No UI imports (Tkinter, PyQt, matplotlib.pyplot)
- ❌ No AI/Ask rbGyanX integration
- ❌ No mode logic or governance
- ✅ Pure functions with clear inputs/outputs
- ✅ Comprehensive docstrings with assumptions
- ✅ Type hints everywhere

**Layer 2 — Logic (rbgyanx/logic/)**
```python
"""
Layer 2: Orchestration & Governance
Allowed dependencies: core layer, standard library
Forbidden dependencies: UI frameworks, direct plotting
"""
```

Responsibilities:
- Pipeline orchestration
- Model applicability checks (CCS enforcement)
- Conditional physical vs biological branching
- QA-driven flow control
- Central execution sequencing
- Mode-aware capability gating

Rules:
- ❌ No UI widgets or dialogs
- ❌ No direct file dialogs
- ❌ No plotting (returns data for plotting)
- ✅ Calls Layer 1 only
- ✅ Returns structured results + logs
- ✅ Stateless where possible

**Layer 3 — UI (rbgyanx/ui/)**
```python
"""
Layer 3: Interaction Layer
Allowed dependencies: logic layer, UI frameworks
Forbidden dependencies: direct core layer calls
"""
```

Responsibilities:
- GUI (existing Tkinter, future PyQt)
- User input handling and validation
- Visualization (plots, tables, dashboards)
- Status and log display
- File I/O dialogs

Rules:
- ❌ No scientific calculations
- ❌ No direct DVH or TCP/NTCP math
- ❌ No QA logic or applicability checks
- ✅ Presentation only
- ✅ Calls orchestration layer exclusively

#### 3. Module Migration Strategy

**Move systematically**:
1. Identify pure computational functions → `core/`
2. Identify orchestration logic → `logic/`
3. Keep UI components in → `ui/`

**Create clean interfaces**:
```python
# Example: Core layer function
def calculate_tcp_poisson(
    dvh: DVHData,
    alpha: float,
    beta: float,
    rho: float
) -> TCPResult:
    """
    Calculate TCP using Poisson model.
    
    Assumptions:
    - Homogeneous clonogen density
    - Independent cell kill
    - No repopulation during treatment
    
    Validity:
    - Conventional fractionation (1.8-2.2 Gy)
    - Photon therapy
    
    Args:
        dvh: Dose-volume histogram object
        alpha: α parameter (Gy^-1)
        beta: β parameter (Gy^-2)
        rho: Clonogen density (cm^-3)
        
    Returns:
        TCPResult with value, uncertainty, and provenance
    """
    # Implementation
    pass
```

#### 4. Add Module Docstrings

Every module must declare:
```python
"""
Module: rbgyanx/core/tcp_models.py
Layer: 1 (Core - Deterministic Analytical)
Purpose: Tumor Control Probability model implementations

Allowed Dependencies:
- numpy, scipy
- rbgyanx.core.dvh

Forbidden Dependencies:
- UI frameworks
- AI/ML inference engines
- Mode controllers

Assumptions:
- All models assume photon therapy unless stated
- Parameters must be pre-validated by caller
- No applicability checking at this layer
"""
```

### Validation Checklist

Run these tests before proceeding:

```python
# Test 1: Import isolation
def test_layer_isolation():
    """Ensure core has no UI imports"""
    import ast
    import sys
    
    core_modules = get_modules('rbgyanx/core/')
    for module in core_modules:
        imports = extract_imports(module)
        forbidden = ['tkinter', 'PyQt5', 'matplotlib.pyplot']
        assert not any(f in imports for f in forbidden)
    
# Test 2: Behavioral equivalence
def test_regression_equivalence():
    """Ensure refactor produces identical outputs"""
    old_result = legacy_pipeline(test_case)
    new_result = refactored_pipeline(test_case)
    
    assert np.allclose(old_result.tcp, new_result.tcp)
    assert np.allclose(old_result.ntcp, new_result.ntcp)
    assert old_result.qa_flags == new_result.qa_flags

# Test 3: No circular imports
def test_no_circular_imports():
    """Ensure clean dependency graph"""
    import_graph = build_import_graph('rbgyanx/')
    assert not has_cycles(import_graph)
    
# Test 4: Core is UI-free
def test_core_ui_free():
    """Verify core layer has zero UI dependencies"""
    core_deps = get_all_dependencies('rbgyanx/core/')
    ui_patterns = ['tkinter', 'qt', 'gui', 'widget']
    assert not any(p in str(core_deps).lower() for p in ui_patterns)
    
# Test 5: Application still runs
def test_application_runs():
    """End-to-end smoke test"""
    app = launch_rbgyanx()
    assert app.load_test_case()
    assert app.run_analysis()
    assert app.outputs_match_baseline()
```

**Mandatory Checks**:
- ✅ Application runs exactly as before
- ✅ All outputs byte-identical (or within floating-point tolerance)
- ✅ No circular imports detected
- ✅ No UI imports in `core/`
- ✅ No scientific calculations in `ui/`
- ✅ Pipeline can be run headless via `logic/`

### Deliverable

A cleanly refactored codebase with:
- Clear 3-layer separation
- Zero behavior change
- Foundation ready for:
  - ModeController
  - PyQt UI migration
  - ADVANCED mode implementation

### Completion Signal

✅ **"Phase A.1 COMPLETE — 3-layer architecture validated. Ready for Phase A.2."**

---

## Phase A.2: Extract Orchestration Logic

### Objective
Complete the 3-layer architecture by extracting pipeline orchestration from legacy scripts into `rbgyanx/logic/`, ensuring zero behavioral change.

### Implementation Steps

#### 1. Identify Orchestration Code

Locate code responsible for:
- Sequential execution logic
- "Glue code" connecting: DVH → biology → TCP/NTCP → QA → plots
- Decision logic for "what runs next"
- Conditional branching based on:
  - Treatment technique
  - Fractionation
  - Applicability checks

**These belong in Layer 2.**

#### 2. Create Primary Pipeline Entry Point

```python
# rbgyanx/logic/pipeline.py

"""
Layer 2: Orchestration & Governance
Central execution pipeline for rbGyanX analysis
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

@dataclass
class PipelineInput:
    """Structured input for analysis pipeline"""
    dvh_data: DVHData
    treatment_info: TreatmentInfo
    structure_set: StructureSet
    config: AnalysisConfig
    
@dataclass
class PipelineOutput:
    """Structured output from analysis pipeline"""
    physical_results: PhysicalResults
    biological_results: Optional[BiologicalResults]
    qa_results: QAResults
    plots: Dict[str, PlotData]
    logs: List[str]
    execution_time: float
    provenance: ProvenanceRecord
    
class PipelineStage(Enum):
    """Execution stages"""
    VALIDATE = "validate"
    PHYSICAL = "physical"
    APPLICABILITY = "applicability"
    BIOLOGICAL = "biological"
    QA = "qa"
    VISUALIZATION = "visualization"

def run_analysis_pipeline(
    inputs: PipelineInput,
    mode_controller: Optional['ModeController'] = None
) -> PipelineOutput:
    """
    Execute the rbGyanX analysis pipeline.
    
    This is the primary orchestration function that:
    1. Validates inputs
    2. Computes physical metrics
    3. Checks model applicability
    4. Conditionally computes biological metrics
    5. Runs QA checks
    6. Prepares visualization data
    
    Args:
        inputs: Structured pipeline inputs
        mode_controller: Optional mode controller (defaults to BASIC)
        
    Returns:
        Structured results and execution logs
        
    Raises:
        ValidationError: If inputs are invalid
        ApplicabilityError: If biological computation blocked
    """
    # Implementation
    logs = []
    start_time = time.time()
    
    # Default to BASIC mode if not provided
    if mode_controller is None:
        from rbgyanx.logic.mode_controller import ModeController, RunMode
        mode_controller = ModeController(RunMode.BASIC)
    
    logs.append(f"rbGyanX pipeline started in {mode_controller.get_mode().value.upper()} mode")
    
    # Stage 1: Validation
    validate_inputs(inputs)
    logs.append("Input validation: PASSED")
    
    # Stage 2: Physical analysis (always runs)
    physical_results = compute_physical_metrics(inputs.dvh_data)
    logs.append("Physical metrics: COMPUTED")
    
    # Stage 3: Applicability check (conditional biological branching)
    applicability = check_applicability(
        inputs.treatment_info,
        inputs.config,
        mode_controller
    )
    
    if applicability.biological_allowed:
        # Stage 4: Biological analysis (conditional)
        biological_results = compute_biological_metrics(
            physical_results,
            inputs.config.biological_params,
            applicability
        )
        logs.append(f"Biological metrics: COMPUTED using {applicability.selected_model}")
    else:
        biological_results = None
        logs.append(f"Biological metrics: BLOCKED - {applicability.reason}")
    
    # Stage 5: QA checks
    qa_results = run_qa_checks(physical_results, biological_results, inputs.config)
    logs.extend(qa_results.messages)
    
    # Stage 6: Prepare visualization data (data only, no plotting)
    plots = prepare_plot_data(physical_results, biological_results, qa_results)
    
    # Create provenance record
    provenance = create_provenance(
        inputs=inputs,
        mode=mode_controller.get_mode(),
        applicability=applicability,
        execution_time=time.time() - start_time
    )
    
    return PipelineOutput(
        physical_results=physical_results,
        biological_results=biological_results,
        qa_results=qa_results,
        plots=plots,
        logs=logs,
        execution_time=time.time() - start_time,
        provenance=provenance
    )
```

#### 3. Move Legacy Code Carefully

**For each legacy execution script (`code1_*.py` ... `code7_*.py`)**:

```python
# Decision tree for code migration:

def classify_code_block(code: str) -> str:
    """Determine where code belongs"""
    
    if contains_calculation(code):
        if is_pure_math(code):
            return "MOVE to core/"
        elif orchestrates_calculations(code):
            return "MOVE to logic/"
        else:
            return "NEEDS REFACTORING"
            
    elif contains_ui_elements(code):
        return "KEEP in ui/"
        
    elif is_glue_code(code):
        return "MOVE to logic/"
    
    else:
        return "MARK for REVIEW"
```

**Migration priority**:
1. Pure calculations → `core/` (if not already moved)
2. Orchestration/sequencing → `logic/`
3. UI display → `ui/`
4. Ambiguous → Mark TODO, leave in place

#### 4. Update Imports Incrementally

**Critical**: Update imports one module at a time.

```python
# BEFORE (scattered imports)
from code1_dvh import calculate_dvh
from code3_tcp import tcp_poisson
from code5_qa import check_qa
from gui_main import display_result

# AFTER (clean layer separation)
from rbgyanx.core.dvh import calculate_dvh
from rbgyanx.core.tcp_models import calculate_tcp_poisson
from rbgyanx.logic.qa import run_qa_checks
# UI imports only in UI layer
```

**Test after each major import change**:
```bash
python -m pytest tests/test_imports.py
python -m rbgyanx --test-mode
```

#### 5. Minimal UI Adjustment

Update GUI code to call the new pipeline:

```python
# BEFORE: UI directly sequencing pipeline
def on_analyze_button():
    dvh = load_dvh()
    tcp = calculate_tcp(dvh)  # Direct core call
    ntcp = calculate_ntcp(dvh)  # Direct core call
    qa = check_qa(tcp, ntcp)  # Direct logic call
    display(tcp, ntcp, qa)

# AFTER: UI calls orchestration layer only
def on_analyze_button():
    inputs = prepare_pipeline_input()
    
    try:
        results = run_analysis_pipeline(inputs)
        display_results(results)
        display_logs(results.logs)
    except ValidationError as e:
        show_error_dialog(str(e))
    except ApplicabilityError as e:
        show_warning_dialog(str(e))
```

**UI behavior must remain identical.**

### Validation Checklist

```python
# Test 1: Identical numerical outputs
def test_numerical_equivalence():
    """Verify refactor produces same numbers"""
    test_cases = load_validation_suite()
    
    for case in test_cases:
        old_result = legacy_execution(case)
        new_result = run_analysis_pipeline(case)
        
        assert results_match(old_result, new_result, tolerance=1e-10)

# Test 2: Identical execution order
def test_execution_order():
    """Verify pipeline stages execute in correct order"""
    mock_tracer = ExecutionTracer()
    run_analysis_pipeline(test_input, tracer=mock_tracer)
    
    expected_order = [
        'validate', 'physical', 'applicability', 
        'biological', 'qa', 'visualization'
    ]
    assert mock_tracer.order == expected_order

# Test 3: Headless execution
def test_headless_pipeline():
    """Verify pipeline can run without UI"""
    # Should succeed without any GUI imports
    result = run_analysis_pipeline(test_input)
    assert result.physical_results is not None
    
# Test 4: Clean imports
def test_layer_imports():
    """Verify import hygiene"""
    assert 'tkinter' not in get_imports('rbgyanx/logic/')
    assert 'matplotlib.pyplot' not in get_imports('rbgyanx/logic/')
    
# Test 5: No circular dependencies
def test_no_cycles():
    """Ensure acyclic dependency graph"""
    graph = build_dependency_graph()
    assert is_dag(graph)
```

**Mandatory Checks**:
- ✅ Application runs exactly as before
- ✅ Identical numerical outputs (within tolerance)
- ✅ Identical plots generated
- ✅ Identical logs/messages produced
- ✅ No circular imports detected
- ✅ `core/` has zero GUI imports
- ✅ `ui/` has zero scientific calculation logic
- ✅ Pipeline can be run headless via `logic/`

### Deliverable

A codebase where:
- Layer 1 = pure science (deterministic core)
- Layer 2 = full pipeline ownership (orchestration)
- Layer 3 = presentation only (UI)
- All imports clean and layered
- No behavioral changes introduced

### Completion Signal

✅ **"Phase A.2 COMPLETE — Orchestration extracted and validated. Ready for Phase A.3 (ModeController)."**

---

## Phase A.3: Implement ModeController (Governance Layer)

### Objective
Introduce a ModeController that explicitly governs BASIC and ADVANCED operation without changing existing behavior. This establishes intent, permissions, and contracts.

### Conceptual Foundation

**Mode is an operating contract, not a feature switch.**

- **BASIC** = Governed clinical + academic decision support
- **ADVANCED** = Explicit research / experimental intent

The same engine runs in both modes. Only permissions and disclosures change.

### Implementation Steps

#### 1. Create Mode Enum

```python
# rbgyanx/logic/mode_controller.py

"""
Layer 2: Mode Controller - Governance Layer
Enforces BASIC vs ADVANCED operating contracts
"""

from enum import Enum
from typing import Dict, Set
from dataclasses import dataclass

class RunMode(Enum):
    """Operating modes for rbGyanX"""
    BASIC = "basic"
    ADVANCED = "advanced"
    
    def __str__(self):
        return self.value.upper()
```

#### 2. Define Capability Exposure

```python
@dataclass
class Capability:
    """A capability that can be enabled/disabled by mode"""
    name: str
    description: str
    risk_level: str  # "low", "medium", "high"
    requires_mode: RunMode
    
# Define all capabilities upfront
CAPABILITIES = {
    # Currently all locked - scaffolding only
    "applicability_override": Capability(
        name="Applicability Override",
        description="Allow biological calculation outside validated domains",
        risk_level="high",
        requires_mode=RunMode.ADVANCED
    ),
    "parameter_sweep": Capability(
        name="Parameter Sweep",
        description="Vary biological parameters systematically",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "model_comparison": Capability(
        name="Model Comparison",
        description="Run multiple models side-by-side",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "developer_mode": Capability(
        name="Developer Mode",
        description="Experimental modification environment",
        risk_level="high",
        requires_mode=RunMode.ADVANCED
    ),
}

# Capability exposure map (currently all False)
CAPABILITY_EXPOSURE = {
    RunMode.BASIC: {
        "applicability_override": False,
        "parameter_sweep": False,
        "model_comparison": False,
        "developer_mode": False,
    },
    RunMode.ADVANCED: {
        # All still locked - will be enabled in future phases
        "applicability_override": False,
        "parameter_sweep": False,
        "model_comparison": False,
        "developer_mode": False,
    }
}
```

#### 3. Implement ModeController Class

```python
class ModeController:
    """
    Governs rbGyanX operating mode and capability exposure.
    
    The ModeController enforces ethical and scientific separation
    between clinical (BASIC) and research (ADVANCED) intent.
    
    Design Principles:
    - Mode is immutable per session
    - Capabilities are declarative, not procedural
    - All mode checks must go through this controller
    - No silent mode changes
    """
    
    def __init__(self, mode: RunMode):
        """
        Initialize mode controller.
        
        Args:
            mode: Operating mode for this session
        """
        self._mode = mode
        self._capabilities = CAPABILITY_EXPOSURE[mode].copy()
        self._session_id = self._generate_session_id()
        self._initialization_time = datetime.now()
        
        # Log mode selection
        logger.info(f"ModeController initialized: {mode}")
        logger.info(f"Session ID: {self._session_id}")
        
    @property
    def mode(self) -> RunMode:
        """Get current operating mode (immutable)"""
        return self._mode
    
    def is_basic(self) -> bool:
        """Check if running in BASIC mode"""
        return self._mode == RunMode.BASIC
    
    def is_advanced(self) -> bool:
        """Check if running in ADVANCED mode"""
        return self._mode == RunMode.ADVANCED
    
    def assert_basic(self):
        """
        Assert that current mode is BASIC.
        Raises ModeError if in ADVANCED mode.
        """
        if not self.is_basic():
            raise ModeError(
                "This operation requires BASIC mode. "
                "Current mode: ADVANCED"
            )
    
    def assert_advanced(self):
        """
        Assert that current mode is ADVANCED.
        Raises ModeError if in BASIC mode.
        """
        if not self.is_advanced():
            raise ModeError(
                "This operation requires ADVANCED mode. "
                "Current mode: BASIC"
            )
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get current capability exposure map.
        
        Returns:
            Dictionary mapping capability names to enabled status
        """
        return self._capabilities.copy()
    
    def is_capability_enabled(self, capability: str) -> bool:
        """
        Check if a specific capability is enabled.
        
        Args:
            capability: Capability name
            
        Returns:
            True if enabled, False otherwise
            
        Raises:
            KeyError: If capability name is unknown
        """
        if capability not in self._capabilities:
            raise KeyError(f"Unknown capability: {capability}")
        return self._capabilities[capability]
    
    def get_contract_message(self) -> str:
        """
        Get the operating contract message for current mode.
        
        Returns:
            Human-readable contract description
        """
        if self.is_basic():
            return (
                "BASIC Mode: Governed clinical and academic decision support. "
                "All analyses are constrained by validated applicability rules."
            )
        else:
            return (
                "ADVANCED Mode: Research and experimental environment. "
                "Results are exploratory and non-clinical."
            )
    
    def get_session_metadata(self) -> Dict:
        """Get session metadata for provenance"""
        return {
            "session_id": self._session_id,
            "mode": self._mode.value,
            "initialization_time": self._initialization_time.isoformat(),
            "capabilities": self.get_capabilities()
        }
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate unique session identifier"""
        import uuid
        return f"rbgyanx-{uuid.uuid4().hex[:12]}"

class ModeError(Exception):
    """Raised when mode requirements are violated"""
    pass
```

#### 4. Integrate with Pipeline

Update `pipeline.py`:

```python
def run_analysis_pipeline(
    inputs: PipelineInput,
    mode_controller: Optional[ModeController] = None
) -> PipelineOutput:
    """
    Execute rbGyanX analysis pipeline with mode governance.
    """
    
    # Default to BASIC if not provided
    if mode_controller is None:
        mode_controller = ModeController(RunMode.BASIC)
    
    logs = []
    logs.append(f"rbGyanX running in {mode_controller.mode} mode")
    logs.append(mode_controller.get_contract_message())
    
    # Rest of pipeline implementation unchanged
    # Mode controller passed through but not yet used for branching
    
    # Store mode in provenance
    provenance = create_provenance(
        inputs=inputs,
        mode=mode_controller.mode,
        capabilities=mode_controller.get_capabilities(),
        session_metadata=mode_controller.get_session_metadata()
    )
    
    return PipelineOutput(...)
```

#### 5. Minimal UI Integration

```python
# rbgyanx/ui/main_window.py

class MainWindow:
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize mode controller (BASIC by default for now)
        # In Phase B.1, this will come from startup screen
        self.mode_controller = ModeController(RunMode.BASIC)
        
        # Display mode in status bar
        self.status_bar.showMessage(
            f"Mode: {self.mode_controller.mode} | "
            f"{self.mode_controller.get_contract_message()}"
        )
        
    def run_analysis(self):
        """Execute analysis with mode governance"""
        inputs = self.prepare_inputs()
        
        # Pass mode controller to pipeline
        results = run_analysis_pipeline(
            inputs,
            mode_controller=self.mode_controller
        )
        
        # Display results
        self.display_results(results)
```

### Validation Checklist

```python
# Test 1: Mode immutability
def test_mode_immutability():
    """Mode cannot be changed after initialization"""
    mc = ModeController(RunMode.BASIC)
    
    with pytest.raises(AttributeError):
        mc.mode = RunMode.ADVANCED  # Should fail
    
    assert mc.mode == RunMode.BASIC

# Test 2: Capability exposure correct
def test_capability_exposure():
    """Capabilities correctly exposed by mode"""
    basic_mc = ModeController(RunMode.BASIC)
    advanced_mc = ModeController(RunMode.ADVANCED)
    
    # Currently all should be False
    assert not basic_mc.is_capability_enabled("model_comparison")
    assert not advanced_mc.is_capability_enabled("model_comparison")
    
# Test 3: Mode assertions work
def test_mode_assertions():
    """Mode assertion helpers work correctly"""
    basic_mc = ModeController(RunMode.BASIC)
    advanced_mc = ModeController(RunMode.ADVANCED)
    
    basic_mc.assert_basic()  # Should pass
    with pytest.raises(ModeError):
        basic_mc.assert_advanced()  # Should fail
        
    advanced_mc.assert_advanced()  # Should pass
    with pytest.raises(ModeError):
        advanced_mc.assert_basic()  # Should fail

# Test 4: Pipeline integration
def test_pipeline_mode_logging():
    """Pipeline logs mode correctly"""
    mc = ModeController(RunMode.BASIC)
    result = run_analysis_pipeline(test_input, mc)
    
    assert any("BASIC mode" in log for log in result.logs)
    assert result.provenance.mode == RunMode.BASIC

# Test 5: Behavioral equivalence
def test_no_behavior_change():
    """Pipeline still produces identical results"""
    # With mode controller
    mc = ModeController(RunMode.BASIC)
    new_result = run_analysis_pipeline(test_input, mc)
    
    # Without mode controller (defaults to BASIC)
    default_result = run_analysis_pipeline(test_input)
    
    # Should be identical
    assert results_match(new_result, default_result)
```

**Mandatory Checks**:
- ✅ BASIC mode runs identically to before
- ✅ Mode logged once per run
- ✅ Mode cannot be changed mid-session
- ✅ No capability accidentally enabled
- ✅ No UI changes beyond displaying mode
- ✅ No imports from UI inside ModeController
- ✅ No imports from Core inside ModeController
- ✅ Provenance includes mode and capabilities

### Deliverable

rbGyanX now has:
- Explicit governance layer
- BASIC vs ADVANCED encoded in logic, not just philosophy
- ADVANCED exists only as a declared contract
- Foundation ready for:
  - Startup screen with mode selection
  - Disclaimers and warnings
  - Capability unlocking in future phases
  - PyQt UI migration

### Completion Signal

✅ **"Phase A.3 COMPLETE — ModeController implemented and validated. Ready for Phase B.1 (Startup Screen)."**

---

# PHASE B: INTERFACE (User-Visible Contracts)

## Phase B.1: Startup Screen with Mode Selection

[Content continues with Phase B.1 implementation details, following same structured format]

---

## APPENDIX: Testing Infrastructure

### Automated Test Suite Structure

```
tests/
├── unit/
│   ├── test_core/              # Pure calculation tests
│   ├── test_logic/             # Orchestration tests
│   └── test_mode_controller/   # Governance tests
├── integration/
│   ├── test_pipeline/          # End-to-end pipeline tests
│   └── test_ui_integration/    # UI-logic integration
├── regression/
│   ├── test_numerical/         # Numerical equivalence
│   └── test_behavioral/        # Behavioral equivalence
└── validation/
    ├── test_ethics/            # Ethics compliance
    └── test_provenance/        # Reproducibility
```

### Continuous Integration Checks

```yaml
# .github/workflows/rbgyanx-ci.yml

name: rbGyanX CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
          
      - name: Run unit tests
        run: pytest tests/unit/ -v
        
      - name: Run integration tests
        run: pytest tests/integration/ -v
        
      - name: Run regression tests
        run: pytest tests/regression/ -v
        
      - name: Check import hygiene
        run: python tests/check_imports.py
        
      - name: Validate ethics compliance
        run: python tests/validate_ethics.py
```

---

## NOTES FOR DEVELOPERS

### When to Proceed to Next Phase

Only move to the next phase when:
1. ✅ All mandatory checks pass
2. ✅ No regressions introduced
3. ✅ Documentation updated
4. ✅ Scientific intent recorded
5. ✅ Code reviewed (if multi-person team)

### When to Stop and Refactor

Stop and refactor if:
- ❌ Tests fail repeatedly
- ❌ Import cycles detected
- ❌ Behavior changes unexpectedly
- ❌ Code violates layer boundaries
- ❌ Scientific correctness in question

**It is always better to pause and fix than to accumulate technical debt.**

### Communication with Cursor/AI

When requesting each phase:

```
"I have completed Phase A.1 and all validation checks pass.
Please provide Phase A.2 implementation guidance.

Phase A.1 Status:
✅ 3-layer architecture implemented
✅ All imports cleaned
✅ No behavioral changes
✅ Tests passing: 47/47
✅ Code reviewed and documented

Ready to proceed with orchestration extraction."
```

---

## END OF IMPLEMENTATION GUIDE

This guide will be expanded with detailed implementation instructions for Phases B-L as development progresses. Each phase follows the same structure:

1. **Objective** (What and Why)
2. **Implementation Steps** (How)
3. **Code Examples** (Concrete)
4. **Validation Checklist** (Mandatory Tests)
5. **Deliverable** (What You Built)
6. **Completion Signal** (What to Say Next)

**Remember**: The manifesto is not just philosophy—it's the implementation roadmap.
