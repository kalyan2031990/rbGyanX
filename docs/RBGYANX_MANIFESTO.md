# rbGyanX MANIFESTO
## A Governed Scientific Framework for Radiotherapy Reasoning

**Version**: 1.0  
**Date**: January 2026  
**Author**: KB (GLA University/BHU Varanasi)  
**License**: [To be determined]

---

## EXECUTIVE SUMMARY

rbGyanX is not a treatment planning system.  
rbGyanX is not an AI automation platform.  
rbGyanX is not a simple radiobiology calculator.

**rbGyanX is a governed scientific framework that uses AI and radiobiological modeling to expose the structure, limits, and failure modes of clinical reasoning in radiotherapy—without automating decisions.**

This manifesto defines the principles, architecture, and roadmap for rbGyanX as a clinical + research + learning platform that respects uncertainty, resists automation hype, and creates trust through transparency.

---

## TABLE OF CONTENTS

1. [Core Identity & Philosophy](#1-core-identity--philosophy)
2. [The Problem rbGyanX Solves](#2-the-problem-rbgyanx-solves)
3. [Foundational Principles](#3-foundational-principles)
4. [Architecture: One Platform, Two Modes, Two Contracts](#4-architecture-one-platform-two-modes-two-contracts)
5. [The Role of AI in rbGyanX](#5-the-role-of-ai-in-rbgyanx)
6. [Advanced Mode: Research Infrastructure Roadmap](#6-advanced-mode-research-infrastructure-roadmap)
7. [Technical Implementation Framework](#7-technical-implementation-framework)
8. [What rbGyanX Will NEVER Do](#8-what-rbgyanx-will-never-do)
9. [Positioning in the Landscape](#9-positioning-in-the-landscape)
10. [Success Metrics](#10-success-metrics)
11. [Long-Term Vision](#11-long-term-vision)
12. [Final Truth](#12-final-truth)

---

## 1. CORE IDENTITY & PHILOSOPHY

### 1.1 Identity Statement

rbGyanX is a **scientific operating system for radiotherapy reasoning**.

Every feature, every AI interaction, every model integration must answer:

> **"Does this help humans understand where radiobiological reasoning is reliable, fragile, or invalid?"**

If not → it does not belong.

### 1.2 The Three Pillars

rbGyanX serves three distinct, equally important audiences:

#### For **Clinicians**
- A safe reasoning support system
- A guardrail against overconfidence
- Protection from hidden failure modes

#### For **Researchers**
- A radiobiology laboratory
- A platform to study robustness, failure, and assumptions
- A framework for hypothesis generation

#### For **Learners**
- A thinking tutor
- A bridge between equations and intuition
- A training platform for residents and physicists

Very few systems can honestly claim all three.

### 1.3 Core Philosophy

**AI is not intuitive. AI is anti-intuitive—and that is exactly why it is useful.**

AI reveals:
- Where human intuition breaks
- Where assumptions stop holding
- Where confidence is unjustified

**Example**: The TCP Plateau Paradox

Human intuition says:
- "Higher dose → higher TCP → always better"

AI computation reveals:
- TCP plateaus (saturation due to clonogen limits, hypoxia)
- NTCP rises sharply (nonlinear dose-volume effects)
- Small volume effects dominate outcome

AI does not replace intuition.  
**AI challenges intuition by exposing where it stops being valid.**

This is the correct epistemic role of AI in medicine.

---

## 2. THE PROBLEM rbGyanX SOLVES

### 2.1 Current Landscape Issues

**Conventional Radiobiology Tools:**
- Post-hoc evaluation only
- No applicability enforcement
- Minimal uncertainty handling
- User-dependent validation

**Automation-Centric AI Systems:**
- Implicit decision pipelines
- Opaque reasoning
- Rare applicability checks
- Reduced human oversight
- Undeclared ethical governance

**Both approaches fail** to separate:
- Clinical intent vs research intent
- Safe support vs experimental exploration
- Validated domains vs extrapolation zones

### 2.2 The Fundamental Tension

Modern radiotherapy AI faces an irreconcilable conflict:

1. **Clinical software** must be conservative, validated, and governed
2. **Research tools** must be exploratory, comparative, and hypothesis-driven

Most platforms try to be both and fail at both.

**rbGyanX's Solution**: Same platform, two explicitly separated modes, two contracts.

---

## 3. FOUNDATIONAL PRINCIPLES

### 3.1 The Non-Negotiables

1. **No Decision Automation**  
   rbGyanX NEVER tells clinicians what to do. It exposes structure; humans decide.

2. **Transparency Before Performance**  
   Interpretable reasoning > black-box accuracy

3. **Failure Is a Feature**  
   Explicitly showing where models break is more valuable than hiding failures

4. **Uncertainty as First-Class Citizen**  
   Uncertainty is not a bug to hide—it's information to expose

5. **Applicability Is Mandatory**  
   No biological calculation without runtime validity checks

6. **Reproducibility Is Sacred**  
   Every analysis must be deterministically reproducible

7. **Ethics Through Design**  
   Safety is embedded in system architecture, not bolted on

### 3.2 The Separation Principle

**The problem is not "basic vs advanced software".**  
**The problem is mixing clinical intent and research intent in the same mode.**

Therefore:
- Clinical support requires **conservation**
- Research requires **exploration**
- These must be **separated explicitly**, not casually

---

## 4. ARCHITECTURE: ONE PLATFORM, TWO MODES, TWO CONTRACTS

### 4.1 Conceptual Framework

Think of rbGyanX not as "basic vs advanced features", but as **two operating contracts on the same engine**.

| Dimension | BASIC MODE | ADVANCED MODE |
|-----------|------------|---------------|
| **Primary audience** | Clinicians, routine users, educators | Researchers, developers, methodologists |
| **Intent** | Clinical decision support | Hypothesis generation & experimentation |
| **Risk tolerance** | Very low | Explicitly higher (but declared) |
| **AI authority** | Explanatory only | Exploratory / analytical |
| **Output stance** | Conservative, guarded | Investigative, comparative |
| **Ethics contract** | Clinical AI ethics | Research AI ethics |
| **Default** | ON | OFF (opt-in) |

**The platform is the same. The rules change.**

### 4.2 BASIC MODE (Clinical + Academic Safe Mode)

#### Purpose
- Routine clinical evaluation
- Teaching and training
- Academic analysis
- Reproducible, publishable results

#### Governing Principle
> "Nothing in BASIC mode should embarrass you in front of a regulator, an IRB, or a court."

#### Characteristics
- ✅ Decision support only
- ✅ No automation
- ✅ No rankings
- ✅ No "best plan" outputs
- ✅ Conditional radiobiology only
- ✅ Model applicability gates enforced
- ✅ CCS (Conformal Consensus Score) enforced
- ✅ Conservative defaults
- ✅ Deterministic behavior
- ✅ Strong logging and provenance
- ✅ Ask rbGyanX = scientific interpreter

#### AI Role in BASIC Mode

**AI CAN:**
- Explain assumptions
- Explain why something is blocked
- Explain uncertainty sources
- Explain literature context
- Bridge equations to intuition

**AI CANNOT:**
- Compare plans numerically
- Suggest clinical actions
- Explore "what if" dose changes
- Run alternative models outside validity gates
- Override safety constraints

**This is deployable, medicine-adjacent software.**

### 4.3 ADVANCED MODE (Research & Experimental Mode)

#### Purpose
- Model development
- Method comparison
- Sensitivity studies
- AI experimentation
- Algorithm research
- Grant-level and PhD-level work

#### Governing Principle
> "ADVANCED mode is honest about uncertainty, incompleteness, and experimental status. This is not clinical software—and it must say so clearly."

#### What ADVANCED Mode Unlocks

**🔬 Radiobiology & Physics Exploration**
- Side-by-side comparison of LQ, LQL, GLQ, Modified LQ models
- Parameter sweeps (α/β, repair half-time, etc.)
- Fractionation stress testing
- Dose-response surface exploration
- Sensitivity gradient analysis (BRI fully enabled)

**🤖 AI & Machine Learning Research**
- Multiple ML models side-by-side
- OOD (Out-of-Distribution) detection experiments
- Calibration curve analysis
- Uncertainty propagation experiments
- Model disagreement analysis
- Feature importance exploration

**📊 Unrestricted Analysis**
- Model agreement/disagreement matrices
- Hypothetical scenarios ("what if α/β = X?")
- Exploration without applicability gate
- Explicit assumption overrides
- Multi-criteria trade-off surfaces

**⚠️ But with mandatory labeling and disclaimers.**

### 4.4 The Mode Boundary (Critical)

The success of this design depends on how **hard and explicit** the boundary is.

#### Mode Switch Requirements (Non-Negotiable)

To enter ADVANCED mode, the user must:

1. **Explicitly switch mode** (not automatic)
2. **See a Research Use Disclaimer**
3. **Acknowledge that:**
   - Results are exploratory
   - Not for clinical decision making
   - Assumptions may violate guidelines
4. **Accept that:**
   - Outputs may be unstable
   - AI may explore beyond validated domains
   - No regulatory protections apply

**This is not bureaucracy—this is ethical separation.**

### 4.5 Feature Exposure Matrix

Same engine. Different permissions.

| Feature | BASIC | ADVANCED |
|---------|-------|----------|
| Applicability gate | Enforced | Optional override |
| Biological models | Conditional | All models |
| CCS requirements | Mandatory | Informational |
| uTCP/uNTCP | Conservative | Full distribution |
| Model comparison | Blocked | Enabled |
| AI hypothesis generation | No | Yes |
| Parameter sweeps | No | Yes |
| Dose perturbation | No | Yes |
| Experimental metrics | No | Yes |
| Reproducibility | Mandatory | Mandatory |

---

## 5. THE ROLE OF AI IN rbGyanX

### 5.1 AI's Correct Purpose

AI in rbGyanX is a **high-dimensional microscope**, not a decision engine.

**AI's job is to:**
- Expose non-intuitive structure in radiobiological response surfaces
- Enable clinicians to recognize plateaus, cliffs, and dominant effects
- Reveal where models agree, diverge, or collapse
- Show where human intuition silently fails

**AI's job is NOT to:**
- Make clinical recommendations
- Rank treatment plans
- Optimize dose distributions
- Replace human judgment

### 5.2 Ask rbGyanX: Two Personalities, One Brain

#### In BASIC Mode
- **Tone**: Conservative, cautious
- **Language**: Clinical, restrained
- **Behavior**: Explains, warns, blocks
- **Forbidden**: Comparative reasoning, suggestions

#### In ADVANCED Mode
- **Tone**: Analytical, exploratory
- **Language**: Research-oriented
- **Behavior**: 
  - Compares models
  - Explains divergence
  - Discusses hypothetical implications
  - Suggests experiments (not treatments)

**This is exactly how a good PhD supervisor behaves.**

### 5.3 Novel AI Capability: "Why Not?" Queries

Beyond explaining what happened, Ask rbGyanX should support structured queries:

- "Why is this not applicable?"
- "Why does this model disagree?"
- "Why does NTCP dominate here?"
- "Why does TCP plateau?"
- "Where does my intuition break down?"

This turns Ask rbGyanX into a **Socratic scientific assistant**, not a chatbot.

### 5.4 AI Feature Exposure Levels

| Level | Description | Allowed AI Functions | Restricted AI Functions |
|-------|-------------|---------------------|------------------------|
| **Green** | Safe, non-interpretive context | Explain concepts, models, assumptions | Numerical interpretation |
| **Yellow** | Context-limited analysis | Discuss uncertainty sources, model limits | Comparative or prescriptive reasoning |
| **Red** | Restricted or unsafe context | AI access blocked | All AI interaction |

---

## 6. ADVANCED MODE: RESEARCH INFRASTRUCTURE ROADMAP

### Guiding Rule for ALL Advanced Features

Every experimental feature must answer at least one of these questions:

1. What assumption is being tested?
2. How sensitive are conclusions to that assumption?
3. Where does the model stop being reliable?

**If a feature does not improve scientific understanding, it does not belong.**

---

### PHASE A: FOUNDATIONAL RESEARCH INFRASTRUCTURE
*Low risk, very high value—should be implemented first*

#### A1. Model Agreement / Disagreement Analysis
**Purpose**: Reveal robustness without ranking

**Implementation**:
- Run multiple compatible models in parallel
- Show agreement bands, not "best model"
- Highlight divergence zones (dose, volume, fractionation)

**Output (non-clinical)**:
- Agreement heatmap
- Divergence explanation by Ask rbGyanX
- Stability metrics across models

**Why this matters**:
- Prevents false confidence
- Encourages scientific skepticism
- Extremely publishable

**Risk**: Low  
**Priority**: 🔥 Very High

---

#### A2. Explicit Assumption Graph (Model Dependency Map)
**Purpose**: Make hidden assumptions visible

**What it shows**:
- α/β dependence
- Fraction size dependence
- Dose range validity
- Training cohort dependence (for ML)

**Visualization**:
- Node graph of assumptions → outputs
- Highlight "fragile paths"
- Show cascading dependencies

**Why this matters**:
- Ethics through transparency
- Trains users to think like scientists
- Reveals model vulnerabilities

**Risk**: Low  
**Priority**: 🔥 Very High

---

#### A3. Deterministic Replay + Provenance Tracking
**Purpose**: Scientific reproducibility

**Implementation**:
- Re-run analysis exactly from logs
- Hash inputs + configuration
- Enable "reproduce this figure" workflow
- Track all parameter choices

**Why this matters**:
- Journal publication requirements
- Legal defensibility
- Debugging research claims
- Trust building

**Risk**: Low  
**Priority**: High

---

### PHASE B: RADIOBIOLOGY & PHYSICS EXPLORATION
*Moderate risk, core academic contribution*

#### B1. Parameter Sweep Engine (α/β, repair half-time, etc.)
**Purpose**: Sensitivity analysis, not optimization

**Implementation**:
- Sweep parameters within literature bounds
- Show response surfaces
- Highlight stable vs unstable regimes

**Restrictions**:
- ❌ No dose modification
- ❌ No plan alteration
- ✅ Analysis only

**Why this matters**:
- Moves beyond point estimates
- Addresses long-standing criticism of LQ usage
- Reveals parameter sensitivity landscapes

**Risk**: Medium  
**Priority**: 🔥 Very High

---

#### B2. Fractionation Stress Testing
**Purpose**: Explore where models break

**Implementation**:
- Vary fraction size hypothetically
- Observe biological metric stability
- Flag extrapolation zones

**Output**:
- Stability curves
- "Model breakdown" indicators
- Threshold identification

**Why this matters**:
- SBRT / hypofractionation research
- Protocol development studies
- Understanding model limits

**Risk**: Medium  
**Priority**: High

---

#### B3. Multi-OAR Trade-off Landscapes (Non-Optimizing)
**Purpose**: Explore biological trade-offs without choosing

**Implementation**:
- TCP vs multiple NTCP surfaces
- Severity-weighted visualizations
- No scalar score, no ranking

**Why this matters**:
- Replaces simplistic UTCP thinking
- Supports multi-criteria research
- Honest complexity representation

**Risk**: Medium  
**Priority**: Medium–High

---

### PHASE C: UNCERTAINTY & ROBUSTNESS SCIENCE
*High scientific value, must be clearly labeled experimental*

#### C1. Uncertainty Decomposition Engine
**Purpose**: Answer "where does uncertainty come from?"

**Separate**:
1. **Aleatoric uncertainty** (patient variability)
2. **Epistemic uncertainty** (parameter ignorance)
3. **Structural uncertainty** (model form itself)

**Output**:
- Contribution bars
- Dominant uncertainty source identification
- Reducibility analysis

**Why this matters**:
- Stops misuse of uncertainty bands
- Directs future data collection
- Reveals fundamental vs resolvable uncertainty

**Risk**: Medium  
**Priority**: 🔥 Very High

---

#### C2. Robustness Indices Family (BRI, TWS, etc.)
**Purpose**: Compare stability, not outcomes

**Implementation**:
- Sensitivity gradients
- Stability metrics under perturbation
- Highlight brittle plans/models

**Restriction**:
- ❌ Must not be used for plan ranking
- ✅ Stability characterization only

**Why this matters**:
- Shifts focus from "best" to "reliable"
- Quantifies fragility
- Research tool for protocol robustness

**Risk**: Medium  
**Priority**: High

---

### PHASE D: ML & AI RESEARCH (STRICTLY NON-CLINICAL)

#### D1. Model Applicability Research Toolkit
**Purpose**: Study generalization explicitly

**Implementation**:
- CCS variants and extensions
- OOD detectors (multiple methods)
- Dataset similarity metrics
- Applicability domain mapping

**Output**:
- Applicability maps
- "Model trust envelope"
- Failure mode prediction

**Why this matters**:
- Addresses ML's biggest failure mode
- Very strong academic contribution
- Essential for safe ML deployment

**Risk**: Medium  
**Priority**: 🔥 Very High

---

#### D2. Model Disagreement & Ensemble Behavior
**Purpose**: Understand ML uncertainty honestly

**Implementation**:
- Ensemble prediction spread
- Failure mode clustering
- Feature sensitivity under distribution shift
- Model ecology analysis

**Restrictions**:
- ❌ No outputs labeled as "prediction"
- ✅ Characterization of behavior only

**Why this matters**:
- Prevents false ML confidence
- Aligns with responsible AI research
- Publishable ML methodology

**Risk**: Medium–High  
**Priority**: High

---

#### D3. Ask rbGyanX as a Research Copilot
**Purpose**: Accelerate scientific thinking, not decisions

**Ask rbGyanX in ADVANCED mode can**:
- Suggest experiments
- Explain why models diverge
- Point to relevant literature
- Generate hypotheses
- Identify research gaps

**Cannot**:
- Suggest clinical actions
- Modify treatment plans
- Override safety safeguards
- Make recommendations

**Why this matters**:
- Turns rbGyanX into a PhD-level research tool
- Accelerates discovery
- Maintains ethical boundaries

**Risk**: Medium  
**Priority**: High

---

### PHASE E: RADICAL BUT CONTROLLED IDEAS
*High risk, high reward—late stage only*

#### E1. Counterfactual Analysis Engine
**Purpose**: "What assumption change caused this outcome?"

**Implementation**:
- Change one assumption at a time
- Observe causal impact
- No clinical suggestions
- Pure hypothesis testing

**Why this matters**:
- Deepens causal reasoning
- Extremely publishable
- Novel methodology

**Risk**: High  
**Priority**: Medium

---

#### E2. Protocol Stress-Testing Sandbox
**Purpose**: Research protocol robustness

**Implementation**:
- Test guideline sensitivity
- Explore edge cases
- Highlight fragile protocol regions

**Mandatory disclaimer**: Research only

**Why this matters**:
- Protocol development
- Guidelines research
- Safety margin studies

**Risk**: High  
**Priority**: Medium

---

### WHAT WILL NEVER MOVE TO ADVANCED MODE

Even in research mode, rbGyanX will NEVER add:

❌ Autonomous plan generation  
❌ Dose optimization engines  
❌ "Best plan" selectors  
❌ AI-recommended clinical actions  
❌ Closed-loop AI control  
❌ Treatment decision automation  

**These cross an ethical line even for research software.**

---

## 7. TECHNICAL IMPLEMENTATION FRAMEWORK

### 7.1 Novel Capabilities (Beyond Standard Features)

#### 7.1.1 Model Failure as First-Class Output

**Most software shows results. Almost none show failure explicitly.**

**Implementation**:

**Model Failure & Breakdown Detection Layer**

Detects when outputs are dominated by:
- Extrapolation beyond training domain
- Parameter extremes (boundary violations)
- Unstable gradients
- Conflicting assumptions

**Labels results as**:
- ✅ Stable
- ⚠️ Conditionally stable
- ⚠️ Fragile
- ❌ Invalid

**Critical distinction**:
- Uncertainty ≠ Invalidity
- rbGyanX shows both explicitly

**Why this matters**: Aligns perfectly with transparency philosophy and is highly publishable.

---

#### 7.1.2 Model Ecology Framework

**Shift from "more models" to "model ecology"**

Models are treated as:
- **Populations** with overlapping validity domains
- **Competitors** in different regimes
- **Complementary systems** rather than alternatives

**rbGyanX studies**:
- Coexistence (where models agree)
- Competition (where models diverge)
- Dominance (which assumptions drive outcomes)
- Collapse (where all models fail)

**Output**:
- Which models agree and why
- Which models disagree and why
- Which assumptions drive divergence
- Ecological stability maps

**This reframes "model comparison" into scientific ecology, not benchmarking.**

---

#### 7.1.3 Three-Type Uncertainty Separation

Most tools blur uncertainty. rbGyanX explicitly separates:

1. **Aleatoric Uncertainty** (irreducible)
   - Patient-to-patient variability
   - Biological heterogeneity
   - Measurement noise

2. **Epistemic Uncertainty** (reducible)
   - Parameter estimation uncertainty
   - Insufficient data
   - Model calibration uncertainty

3. **Structural Uncertainty** (model form)
   - Choice of mathematical model
   - Functional form assumptions
   - Physics approximations

**Then shows**:
- Which type dominates
- Whether more data would help
- Whether the model is fundamentally limited

**This is rare and very impactful academically.**

---

### 7.2 Learning Infrastructure (The Missing Pillar)

rbGyanX aims to be clinical + research + **learning**.  
Right now, learning is implicit.

**Recommendation**: A third "learning lens", not a third mode.

#### Learning Lens (Toggle in Both Modes)

**When Learning Lens is ON**:
- Adds inline explanations
- Shows mathematical derivations (optional depth)
- Explains why gates block certain actions
- Provides historical context (QUANTEC, RTOG protocols)
- Links to literature references
- Highlights common misconceptions
- Shows worked examples

**Benefits**:
- Makes rbGyanX a training tool
- Supports residency education
- Enables PhD coursework integration
- Bridges theory and practice

**No other radiobiology system does this well.**

---

### 7.3 Plateau, Cliff, and Dominance Detection

Operationalize the "TCP plateau paradox" as system capabilities:

#### 🔬 A. Plateau Detection (TCP Saturation Awareness)

**What rbGyanX shows**:
- TCP vs dose curve
- Regions where ∂TCP/∂Dose → 0
- Saturation visualization

**Human insight enabled**:
"Further escalation gives negligible tumor benefit."

No recommendation made. Just exposure of structure.

---

#### 🧯 B. NTCP Cliff Detection

**What rbGyanX shows**:
- NTCP sensitivity vs dose or volume
- Identify steep regions ("cliffs")
- Threshold proximity warnings

**Human insight enabled**:
"We are near a risk cliff; small changes matter."

Again: No "don't do this", no optimization. Just visibility.

---

#### 🧩 C. Small-Volume Dominance Analysis

**What rbGyanX computes**:
- Contribution of dose bins / sub-volumes to NTCP
- Rank contributors, not plans
- Hotspot impact quantification

**Human insight enabled**:
"A tiny hotspot dominates risk more than global dose."

This often violates human intuition, which focuses on averages.

---

### 7.4 Developer Mode: Code as Scientific Artifact

GitHub-governed developer mode with a critical refinement:

**Scientific Intent Metadata** (Mandatory for Every Change)

Every developer change must declare:
- **Hypothesis being tested**
- **Expected failure modes**
- **Risk level** (Low / Medium / High)
- **Intended scope** (Research only / Future BASIC migration)
- **Validation approach**

**This turns rbGyanX development into traceable science, not hacking.**

---

### 7.5 Quality Assurance Paradigm: Flag-Not-Fail

Traditional QA: Binary pass/fail  
rbGyanX QA: **Continuous visibility into quality degradation**

**Implementation**:
- Continuous runtime checks
- Graduated warnings (info → caution → error)
- Quality metrics tracked and logged
- Graceful degradation, not catastrophic failure

**Philosophy**: Show the user what's questionable, let them decide.

---

## 8. WHAT rbGyanX WILL NEVER DO

### 8.1 The Permanent Exclusion List

Even with overwhelming user demand, rbGyanX will NEVER:

❌ **Autonomous Dose Optimization**  
❌ **Treatment Plan Generation**  
❌ **"Best Plan" Ranking or Selection**  
❌ **AI-Recommended Clinical Actions**  
❌ **Closed-Loop Treatment Control**  
❌ **Automatic Protocol Modification**  
❌ **Reinforcement Learning for Dose Strategy**  
❌ **End-to-End "AI Treatment Designers"**  
❌ **Scalar "Quality Scores" for Plans**  
❌ **Any System That Outputs: "Do X" to Clinicians**

### 8.2 Why These Are Forbidden

These features would:
- ✗ Undermine human authority
- ✗ Create liability without benefit
- ✗ Destroy trust through opacity
- ✗ Violate the core philosophy
- ✗ Attract attention for wrong reasons
- ✗ Compromise ethical foundation

**rbGyanX's strength is NOT being flashy.**

---

## 9. POSITIONING IN THE LANDSCAPE

### 9.1 Comparative Analysis

**Table: rbGyanX vs Alternatives**

| Feature / Dimension | Conventional Tools | Automation AI | rbGyanX |
|---------------------|-------------------|---------------|---------|
| **Primary objective** | Post-hoc evaluation | Automated pipeline | Support clinical reasoning |
| **Decision automation** | None | Often implicit | Explicitly prohibited |
| **Applicability enforcement** | User-dependent | Rare | Centralized, mandatory |
| **Runtime validation** | Limited | Minimal | Mandatory |
| **Uncertainty handling** | Static/absent | Implicit | Explicit, continuous |
| **Quality assurance** | Calculator checks | Retrospective | Continuous "flag-not-fail" |
| **Interpretability** | Equations only | Opaque | Structured explanation |
| **Role of AI** | N/A | Decision engine | Explanation only |
| **Human oversight** | Assumed | Reduced | Explicitly enforced |
| **Ethical governance** | Implicit | Often undeclared | Embedded by design |
| **Intended use** | Research/isolated | Clinical automation | Governed support + research |

### 9.2 Unique Value Propositions

rbGyanX is the only platform that:

1. **Separates clinical and research intent architecturally**
2. **Makes model failure a first-class output**
3. **Enforces applicability before biological computation**
4. **Explicitly prohibits decision automation**
5. **Treats uncertainty as information, not noise**
6. **Uses AI for explanation, never recommendation**
7. **Provides a learning infrastructure alongside clinical use**
8. **Implements model ecology rather than model competition**

---

## 10. SUCCESS METRICS

### 10.1 For Clinical Adoption

**Not measured by**:
- Number of automated decisions
- Speed of workflow
- Reduction in human involvement

**Measured by**:
- ✅ Trust metrics (user surveys)
- ✅ Understanding improvement (educational assessment)
- ✅ Error prevention (flagged invalid calculations)
- ✅ Reproducibility (audit pass rate)
- ✅ Regulatory acceptance

### 10.2 For Research Impact

**Success means**:
- 📄 Publications citing rbGyanX methodology
- 📄 Novel discoveries about model behavior
- 📄 Improved understanding of radiobiological limits
- 📄 New validation datasets generated
- 📄 Community-contributed extensions

### 10.3 For Learning Effectiveness

**Success means**:
- 🎓 Integration into residency curricula
- 🎓 Use in medical physics courses
- 🎓 Cited in educational materials
- 🎓 Student comprehension improvements
- 🎓 Reduced conceptual errors

---

## 11. LONG-TERM VISION

### 11.1 The 3-Year Horizon

**Year 1: Foundation**
- ✅ BASIC mode deployed and validated
- ✅ Core applicability framework operational
- ✅ Initial clinical adoption
- ✅ First peer-reviewed publication

**Year 2: Research Infrastructure**
- ✅ ADVANCED mode feature-complete (Phase A-C)
- ✅ Learning lens operational
- ✅ Multi-institutional validation
- ✅ Research community adoption

**Year 3: Ecosystem**
- ✅ Developer community active
- ✅ Extension framework operational
- ✅ International collaboration
- ✅ Reference architecture status

### 11.2 The North Star (10-Year Vision)

rbGyanX becomes:

**The reference standard** for how AI should be integrated into medical decision support—not by automating decisions, but by illuminating reasoning.

**The training platform** for the next generation of radiation oncologists and medical physicists who understand both the power and limits of computational radiobiology.

**The research laboratory** where the next breakthroughs in understanding radiobiological model behavior are discovered.

**The proof** that you can build powerful AI systems that enhance rather than replace human expertise.

### 11.3 Cultural Impact

rbGyanX aims to shift the conversation from:

"How can AI replace clinical decisions?"

**TO:**

"How can AI help humans understand where their reasoning is reliable?"

This philosophical shift is as important as the technical implementation.

---

## 12. FINAL TRUTH

### 12.1 What Makes rbGyanX Different

You are doing something rare:

- **Slowing down** (when everyone rushes)
- **Separating intent** (when others blur boundaries)
- **Respecting uncertainty** (when others hide it)
- **Resisting automation hype** (when it's most profitable)

This will:
- ❌ Delay flashy demos
- ❌ Reduce marketing appeal
- ❌ Complicate investor pitches

But it will:
- ✅ Create a platform people trust
- ✅ Enable honest science
- ✅ Protect patients
- ✅ Last decades, not years

**That trust is what lasts.**

### 12.2 The Core Tension Resolved

Medical AI faces a fundamental paradox:

**Powerful enough to be useful** ⟷ **Safe enough to be trusted**

Most systems sacrifice one for the other.

rbGyanX resolves this by recognizing:

**Power comes from transparency, not autonomy.**  
**Safety comes from design, not restrictions.**

### 12.3 Closing Statement

AI is not dangerous because it is powerful.

**AI is dangerous when power and responsibility are not separated.**

rbGyanX does that separation cleanly, intelligently, and unapologetically.

This is not just software engineering.  
This is not just radiobiology.  
This is not just AI development.

**This is principled scientific architecture.**

And that is what makes rbGyanX state-of-the-art.

---

## APPENDICES

### Appendix A: Model Applicability Matrix

| Treatment Technique | LQ Model | LQL Model | Modified LQ | GLQ | Physical Dose Only |
|---------------------|----------|-----------|-------------|-----|--------------------|
| Conventional (1.8-2.2 Gy) | ✔ Valid | ✔ Valid | ⚠ Context-dependent | ✔ Valid | ✔ Valid |
| Hypofractionation (2.5-5 Gy) | ⚠ Use with caution | ✔ Valid | ✔ Valid | ✔ Valid | ✔ Valid |
| SBRT | ✖ Not recommended | ⚠ Limited validity | ✔ Valid | ✔ Preferred | ✔ Valid |
| SRS | ✖ Not recommended | ⚠ Limited validity | ✔ Valid | ✔ Preferred | ✔ Valid |
| Brachytherapy (LDR/HDR) | ⚠ Context-dependent | ⚠ Context-dependent | ✔ Valid | ✔ Valid | ✔ Valid |
| Particle therapy | ✖ Unsupported | ✖ Unsupported | ✖ Unsupported | ✖ Unsupported | ✔ Valid |
| Other / Unknown | ⚠ Use with caution | ⚠ Use with caution | ⚠ Use with caution | ⚠ Use with caution | ✔ Default |

**Legend**:  
✔ Validated use | ⚠ Use with caution / context-dependent | ✖ Not recommended or unsupported

This matrix governs biological normalization and downstream analysis in rbGyanX.

---

### Appendix B: BASIC vs ADVANCED Mode Capabilities (Complete)

| Capability | BASIC Mode | ADVANCED Mode |
|-----------|------------|---------------|
| **Intended use** | Routine clinical and academic decision support | Hypothesis testing and methodological research |
| **Applicability gate** | Mandatory, enforced | Optional override with disclosure |
| **Radiobiological models** | Conditional, validated only | Full access for exploration |
| **Physical vs biological branching** | Automatic, gated | User-controlled |
| **Uncertainty reporting** | Conservative, bounded | Full distributional analysis |
| **Model comparison** | Disabled | Enabled |
| **Model disagreement analysis** | Not available | Full analysis |
| **Parameter sweeps** | Disabled | Enabled |
| **Sensitivity analysis** | Limited | Extensive |
| **Fractionation exploration** | Not permitted | Research sandbox |
| **Assumption overrides** | Not permitted | Explicit, logged |
| **AI interaction** | Explanation only | Exploratory interpretation |
| **AI recommendations** | Not permitted | Not permitted |
| **Dose modification** | Not permitted | Not permitted |
| **Plan ranking** | Not permitted | Not permitted |
| **Reproducibility** | Mandatory | Mandatory |
| **Provenance tracking** | Full | Full |
| **Failure mode visibility** | Automatic | Enhanced |
| **Disclaimers** | Clinical decision support | Research-only, non-clinical |
| **Regulatory defensibility** | High | Not intended |

---

### Appendix C: Documentation Structure

rbGyanX requires **two separate documentation contracts**:

#### BASIC Mode Documentation
1. **Intended Use Statement**
2. **Clinical Scope and Limitations**
3. **Ethical Governance Framework**
4. **Quality Assurance Procedures**
5. **Validation Evidence**
6. **Reproducibility Guidelines**
7. **Known Limitations and Caveats**
8. **User Training Requirements**

#### ADVANCED Mode Documentation
1. **Research Intent Declaration**
2. **Experimental Nature Disclosure**
3. **Known Instabilities and Failure Modes**
4. **Model Validity Boundaries**
5. **Assumption Dependencies**
6. **Not-for-Clinical-Use Warnings**
7. **Hypothesis Testing Framework**
8. **Scientific Reproducibility Protocol**

**This protects legally, ethically, and scientifically.**

---

### Appendix D: Glossary of Key Terms

**Applicability Gate**: Runtime validation check that prevents biological calculations outside validated domains

**CCS (Conformal Consensus Score)**: Metric ensuring training data similarity to patient under analysis

**Model Ecology**: Framework treating models as populations with overlapping validity domains rather than competitors

**Flag-Not-Fail QA**: Quality assurance paradigm that exposes degradation rather than binary rejection

**Plateau Detection**: Identification of dose regions where TCP saturates and further escalation provides minimal benefit

**NTCP Cliff**: Steep gradient region where small dose changes dramatically affect toxicity probability

**Uncertainty Decomposition**: Separation of aleatoric, epistemic, and structural uncertainty sources

**Learning Lens**: Educational overlay providing explanations without changing core functionality

**Model Failure as Output**: Explicit labeling when calculations are invalid, unstable, or extrapolated

---

## VERSION HISTORY

**v1.0** (January 2026)
- Initial manifesto release
- Complete philosophical and technical framework
- Roadmap through Phase E

**Future versions will track**:
- Implementation progress
- Community feedback integration
- Validation results
- Regulatory guidance compliance

---

## CONTACT & CONTRIBUTION

**Primary Author**: KB  
**Institution**: GLA University / BHU Varanasi  
**Email**: [To be added]  
**GitHub**: [To be added]

**Community Contributions**: Welcome following the Developer Mode guidelines with Scientific Intent Metadata

---

## LICENSE

[To be determined based on institutional and community input]

Candidates:
- Apache 2.0 (permissive, research-friendly)
- GPL v3 (copyleft, ensures openness)
- Academic Free License
- Custom research + clinical dual license

---

## ACKNOWLEDGMENTS

This manifesto synthesizes insights from:
- Extended technical discussions on rbGyanX architecture
- Literature on responsible medical AI
- Clinical experience in radiation oncology
- Research in radiobiological modeling
- Ethical frameworks for AI in healthcare

**Special recognition** to the principle that **transparency before performance** is not just an ethical choice—it's a technical advantage.

---

## FINAL COMMITMENT

rbGyanX will never compromise on:
1. **Patient safety**
2. **Scientific honesty**
3. **Clinical autonomy**
4. **Ethical transparency**
5. **Reproducible research**

Everything else is negotiable.

**This is not just a mission statement. This is a contract with the community.**

---

*"The problem is not building powerful AI. The problem is building AI worth trusting."*

**— rbGyanX Manifesto, v1.0**

---

## rbGyanX and deep-learning NTCP models

As of 2025, 3D convolutional deep learning NTCP models (using full dose distributions
rather than DVH) outperform LKB models for specific toxicity endpoints, particularly
HN dysphagia and xerostomia (Starke et al. Radiother Oncol 2025).

rbGyanX does not compete with these models. Its role is complementary:

| Property | DL NTCP (e.g. 3D CNN) | rbGyanX LKB/Poisson |
|---|---|---|
| Predictive accuracy (data-rich sites) | Higher | Lower |
| Interpretability | Black box | Full: TD50, m, α/β visible |
| Parameter traceability | None | YAML provenance per run |
| Physics constraint | None | LQ model + bDVH fractionation |
| Regulatory auditability | Difficult | Straightforward |
| Data requirement | 200–500 patients | Works with published parameters |
| Multi-site / rare sites | Limited by data | YAML-extensible |

**Recommended workflow for institutions with outcome data:**
Run both. Use rbGyanX LKB/Poisson as the auditable physics baseline.
Use a trained DL NTCP model for sites where you have ≥200 outcome-labelled
patients. Compare outputs; discordance flags unusual cases worth physicist review.

**Future direction — PINN:**
The ADVANCED-mode `engine_advanced` package bridges classical and ML approaches:
a neural network constrained by LQ physics residuals in its loss function,
trained on institutional outcomes, producing patient-specific effective
parameters (α_eff, β_eff, TD50_eff) alongside the probability output.

---

END OF MANIFESTO
