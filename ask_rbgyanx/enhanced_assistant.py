"""
Enhanced Ask rbGyanX Assistant

Integrates rule-based knowledge, calculator, math tools, and scope guards.

Author: rbGyanX Team
Version: 1.0.0
"""

import re
from typing import Dict, List, Optional, Tuple, Any

# Import components
try:
    from ask_rbgyanx.scope_guard import ScopeGuard, create_scope_guard
    SCOPE_GUARD_AVAILABLE = True
except ImportError:
    SCOPE_GUARD_AVAILABLE = False
    create_scope_guard = None

try:
    from ask_rbgyanx.calculator import ScientificCalculator, create_calculator
    CALCULATOR_AVAILABLE = True
except ImportError:
    CALCULATOR_AVAILABLE = False
    create_calculator = None

try:
    from ask_rbgyanx.math_tools import MathEquationHelper, create_equation_helper
    EQUATION_HELPER_AVAILABLE = True
except ImportError:
    EQUATION_HELPER_AVAILABLE = False
    create_equation_helper = None

try:
    from ai.rule_based_assistant import RuleBasedAssistant, create_rule_based_assistant
    RULE_BASED_AVAILABLE = True
except ImportError:
    RULE_BASED_AVAILABLE = False
    create_rule_based_assistant = None


class EnhancedAskrbGyanX:
    """
    Enhanced Ask rbGyanX assistant with expanded knowledge and tools.
    
    Integrates:
    - Rule-based knowledge base (expanded)
    - Scientific calculator
    - Math equation helper
    - Scope guards for ethics
    """
    
    def __init__(self):
        """Initialize enhanced assistant"""
        # Initialize components
        self.scope_guard = create_scope_guard() if SCOPE_GUARD_AVAILABLE else None
        self.calculator = create_calculator() if CALCULATOR_AVAILABLE else None
        self.equation_helper = create_equation_helper() if EQUATION_HELPER_AVAILABLE else None
        self.rule_based = create_rule_based_assistant() if RULE_BASED_AVAILABLE else None
        
        # Expanded knowledge (will be loaded from registry)
        self.expanded_knowledge = self._load_expanded_knowledge()
    
    def _load_expanded_knowledge(self) -> Dict[str, Dict]:
        """Load expanded knowledge base"""
        # This will be populated with all new topics
        # For now, return structure
        return {
            'eud_geud': {
                'patterns': [r'eud', r'equivalent.*uniform.*dose', r'geud', r'generalized.*eud'],
                'responses': [{
                    'answer': """EUD (Equivalent Uniform Dose) and gEUD:

EUD CONCEPT:
- Converts heterogeneous dose distribution to equivalent uniform dose
- Formula: EUD = (Σᵢ vᵢ × Dᵢ^(1/n))^n
- Where: vᵢ = volume fraction, Dᵢ = dose to voxel i, n = volume effect parameter

gEUD (GENERALIZED EUD):
- Generalization: gEUD = (Σᵢ vᵢ × Dᵢ^a)^(1/a)
- Parameter 'a' determines dose-volume effect
- a → -∞: Minimum dose (serial organ)
- a = 1: Mean dose (parallel organ)
- a → +∞: Maximum dose

PHYSICAL MEANING:
- n ≈ 0: Serial organ behavior (spinal cord)
- n ≈ 1: Parallel organ behavior (lung, liver)
- n ≈ 0.7: Intermediate (parotid)

APPLICATIONS:
- TCP modeling (EUD-based TCP)
- NTCP modeling (dose-volume effects)
- Plan comparison

LIMITATIONS:
- Assumes uniform radiosensitivity
- Does not account for spatial dose distribution
- Simplified volume effect model

References:
- Niemierko (1997) - EUD concept
- Niemierko (1999) - gEUD generalization
- Gay & Niemierko (2003) - Clinical applications""",
                    'confidence': 0.85
                }]
            },
            'bed_eqd2': {
                'patterns': [r'bed', r'biological.*effective.*dose', r'eqd2', r'equivalent.*dose.*2gy'],
                'responses': [{
                    'answer': """BED (Biological Effective Dose) and EQD2:

BED CONCEPT:
- Accounts for fractionation effects using LQ model
- Formula: BED = D × (1 + d/(α/β))
- Where: D = total dose, d = dose per fraction, α/β = tissue-specific ratio

EQD2 (EQUIVALENT DOSE IN 2 GY FRACTIONS):
- Converts any fractionation to 2 Gy equivalent
- Formula: EQD2 = D × (d + α/β) / (2 + α/β)
- Standard reference: 2 Gy per fraction

α/β RATIOS:
- Early effects: 10-15 Gy (skin, mucosa)
- Late effects: 2-3 Gy (spinal cord, brain)
- Tumors: 5-20 Gy (varies by type)

APPLICATIONS:
- Comparing different fractionation schemes
- Hypofractionation studies
- Re-irradiation planning (conceptual)

LIMITATIONS:
- Assumes constant α/β (may vary with dose)
- Does not account for repopulation
- Time effects not included

References:
- Fowler (1989) - Fractionation effects
- Barendsen (1982) - LQ model
- Withers et al. (1983) - α/β ratios""",
                    'confidence': 0.85
                }]
            },
            'hypofractionation': {
                'patterns': [r'hypofraction', r'large.*fraction', r'stereotactic', r'sbrt', r'srs'],
                'responses': [{
                    'answer': """Hypofractionation:

DEFINITION:
- Delivery of radiation in fewer, larger fractions
- Typically: >2.5 Gy per fraction
- Examples: SBRT (5-20 Gy/fx), SRS (single fraction)

RADIOBIOLOGICAL BASIS:
- Higher dose per fraction → increased biological effect
- Late effects increase more than early effects (low α/β)
- Therapeutic window may widen for some tumors

ADVANTAGES:
- Shorter treatment time (patient convenience)
- Potentially improved tumor control (for some sites)
- Resource efficiency

CONSIDERATIONS:
- Normal tissue tolerance limits
- Dose-volume constraints critical
- Requires precise delivery (IGRT, motion management)

MODELING CHALLENGES:
- LQ model may break down at high doses per fraction
- Alternative models: LQ-L model, universal survival curve
- Clinical data essential for validation

References:
- Fowler (2008) - Hypofractionation review
- Brown et al. (2014) - SBRT principles
- Kirkpatrick et al. (2008) - LQ model limitations""",
                    'confidence': 0.8
                }]
            },
            'reirradiation': {
                'patterns': [r're.*irradiat', r'retreatment', r'second.*course'],
                'responses': [{
                    'answer': """Re-irradiation Principles:

DEFINITION:
- Second course of radiation to previously irradiated volume
- Time interval between courses varies

RADIOBIOLOGICAL CONSIDERATIONS:
- Normal tissue recovery (incomplete)
- Cumulative dose effects
- Time-dependent recovery processes

MODELING APPROACHES:
- Cumulative BED/EQD2 (simplified)
- Recovery factor models
- Clinical tolerance data (QUANTEC)

CHALLENGES:
- Limited normal tissue tolerance data
- Recovery kinetics poorly understood
- Individual variation significant

CLINICAL FACTORS:
- Time interval (longer = more recovery)
- Initial dose and volume
- Organ-specific tolerance
- Patient factors (age, comorbidities)

⚠️ EDUCATIONAL NOTE:
Re-irradiation planning requires:
- Careful normal tissue assessment
- Clinical judgment
- Institutional protocols
- Patient-specific considerations

References:
- Nieder et al. (2006) - Re-irradiation review
- QUANTEC (2010) - Normal tissue tolerance
- De Crevoisier et al. (2014) - Head and neck re-irradiation""",
                    'confidence': 0.75
                }]
            },
            'utcp': {
                'patterns': [r'utcp', r'unified.*tcp', r'universal.*tcp'],
                'responses': [{
                    'answer': """UTCP (Unified TCP) Concept:

DEFINITION:
- Framework for combining multiple TCP models
- Accounts for uncertainty in model parameters
- Integrates different modeling approaches

APPROACHES:
- Bayesian model averaging
- Ensemble methods
- Parameter uncertainty propagation

ADVANTAGES:
- More robust predictions
- Accounts for model uncertainty
- Can incorporate multiple data sources

LIMITATIONS:
- Computational complexity
- Requires prior distributions
- Validation challenging

⚠️ EDUCATIONAL NOTE:
UTCP is a research concept. Clinical application requires:
- Extensive validation
- Clinical judgment
- Institutional protocols

References:
- Webb & Nahum (1993) - TCP modeling
- Tome & Fowler (2002) - TCP uncertainty
- Research literature (ongoing)""",
                    'confidence': 0.7
                }]
            },
            'quantec': {
                'patterns': [r'quantec', r'normal.*tissue.*tolerance', r'td50', r'tolerance.*dose'],
                'responses': [{
                    'answer': """QUANTEC (Quantitative Analysis of Normal Tissue Effects):

PURPOSE:
- Comprehensive review of normal tissue tolerance
- Dose-volume constraints for treatment planning
- Evidence-based recommendations

KEY PARAMETERS:
- TD50: Dose for 50% complication probability
- TD5/5: 5% complication at 5 years
- Volume effect parameters (n, m)

ORGAN-SPECIFIC DATA:
- Spinal cord: TD50 ≈ 68.6 Gy (n=0, m=1.6)
- Parotid: TD50 ≈ 46.3 Gy (n=0.7, m=1.8)
- Lung: TD50 varies by endpoint
- Rectum: TD50 ≈ 76.9 Gy (n=0.6, m=1.4)

LIMITATIONS:
- Based on historical data (2D/3D-CRT era)
- May not apply to modern techniques (IMRT, SBRT)
- Individual variation significant

⚠️ EDUCATIONAL NOTE:
QUANTEC provides guidance, not absolute limits.
Clinical judgment essential.

References:
- QUANTEC (2010) - Special issue, Int J Radiat Oncol Biol Phys
- Emami et al. (1991) - Original tolerance data
- Marks et al. (2010) - QUANTEC summary""",
                    'confidence': 0.85
                }]
            },
            'ml_models': {
                'patterns': [r'ml.*model', r'machine.*learning', r'ann', r'neural.*network', r'xgboost', r'random.*forest'],
                'responses': [{
                    'answer': """Machine Learning Models in Radiobiology:

COMMON ALGORITHMS:

1. LOGISTIC REGRESSION:
   - Linear model for binary outcomes
   - Interpretable coefficients
   - Baseline for comparison

2. RANDOM FOREST:
   - Ensemble of decision trees
   - Handles non-linear relationships
   - Feature importance available

3. XGBOOST:
   - Gradient boosting framework
   - High predictive performance
   - Requires careful tuning

4. NEURAL NETWORKS (ANN):
   - Multi-layer perceptrons
   - Can model complex patterns
   - Less interpretable

BIAS-VARIANCE TRADEOFF:
- High bias: Underfitting (too simple)
- High variance: Overfitting (too complex)
- Goal: Optimal balance

OVERFITTING PREVENTION:
- Cross-validation
- Regularization
- Early stopping
- Feature selection

VALIDATION:
- Internal: Cross-validation, bootstrap
- External: Independent test set
- Temporal: Time-based split

References:
- Hastie et al. (2009) - Elements of Statistical Learning
- Breiman (2001) - Random Forests
- Chen & Guestrin (2016) - XGBoost""",
                    'confidence': 0.8
                }]
            },
            'deep_learning': {
                'patterns': [r'deep.*learning', r'cnn', r'convolutional', r'autoencoder', r'dl.*limitation'],
                'responses': [{
                    'answer': """Deep Learning in Radiotherapy (Conceptual):

POTENTIAL APPLICATIONS:

1. CNNs FOR DVH ANOMALY DETECTION:
   - Pattern recognition in dose distributions
   - Quality assurance automation
   - Error detection

2. AUTOENCODERS FOR QA:
   - Dimensionality reduction
   - Anomaly detection
   - Feature learning

LIMITATIONS OF DL IN CLINICAL RADIOTHERAPY:

1. DATA REQUIREMENTS:
   - Large datasets needed
   - Clinical data often limited
   - Quality vs quantity tradeoff

2. INTERPRETABILITY:
   - "Black box" problem
   - Difficult to explain predictions
   - Clinical trust requires transparency

3. GENERALIZATION:
   - May not generalize across institutions
   - Population-specific patterns
   - External validation critical

4. WHY DL ≠ CLINICAL TRUTH:
   - Models learn patterns, not causality
   - Correlation ≠ causation
   - Clinical judgment irreplaceable
   - Regulatory considerations

EDUCATIONAL NOTE:
Deep learning is a tool, not a replacement for:
- Clinical expertise
- Radiobiological understanding
- Quality assurance
- Regulatory compliance

References:
- Litjens et al. (2017) - DL in medical imaging
- Esteva et al. (2017) - DL limitations
- Research literature (ongoing)""",
                    'confidence': 0.75
                }]
            },
            'statistics_advanced': {
                'patterns': [r'likelihood', r'bayesian', r'hypothesis.*test', r'causation', r'correlation.*causation'],
                'responses': [{
                    'answer': """Advanced Statistical Concepts:

LIKELIHOOD:
- Probability of observing data given parameters
- Maximum Likelihood Estimation (MLE)
- Used in model fitting

BAYESIAN STATISTICS:
- Incorporates prior knowledge
- Posterior = Prior × Likelihood
- Useful for parameter estimation

HYPOTHESIS TESTING:
- Null hypothesis (H₀) vs Alternative (H₁)
- Type I error (α): False positive
- Type II error (β): False negative
- Power = 1 - β

CORRELATION vs CAUSATION:
- Correlation: Statistical association
- Causation: Cause-effect relationship
- Correlation ≠ Causation
- Requires experimental design or causal inference

CAUSAL INFERENCE:
- Randomized controlled trials (gold standard)
- Observational studies (confounding)
- Instrumental variables
- Propensity score matching

EDUCATIONAL NOTE:
Statistical significance ≠ Clinical significance
Always consider:
- Effect size
- Clinical relevance
- Practical implications

References:
- Altman & Bland (1995) - Statistics in medicine
- Pearl & Mackenzie (2018) - Causal inference
- Gelman et al. (2013) - Bayesian data analysis""",
                    'confidence': 0.75
                }]
            }
        }
    
    def ask(self, query: str) -> Dict[str, Any]:
        """
        Process query through enhanced assistant.
        
        Parameters
        ----------
        query : str
            User query
        
        Returns
        -------
        Dict
            Response with answer, status, source, etc.
        """
        # Step 1: Scope guard check
        if self.scope_guard:
            is_allowed, block_reason, suggestion = self.scope_guard.check_query(query)
            if not is_allowed:
                return {
                    'answer': None,
                    'status': 'blocked',
                    'error': block_reason,
                    'suggestion': suggestion,
                    'source': 'scope_guard'
                }
        
        # Step 2: Check for calculation request
        if self.calculator:
            calc_request = self.calculator.parse_calculation_request(query)
            if calc_request:
                result = self._handle_calculation(calc_request)
                if result:
                    return result
        
        # Step 3: Check for equation request
        if self.equation_helper:
            eq_request = self.equation_helper.parse_equation_request(query)
            if eq_request:
                result = self._handle_equation(eq_request)
                if result:
                    return result
        
        # Step 4: Try expanded knowledge base
        result = self._search_expanded_knowledge(query)
        if result:
            return result
        
        # Step 5: Fallback to rule-based assistant
        if self.rule_based:
            result = self.rule_based.ask(query)
            # Add scope guard disclaimer
            if self.scope_guard and result.get('status') == 'success':
                result['answer'] = self.scope_guard.add_safety_disclaimer(result['answer'])
            return result
        
        # Step 6: Default response
        return {
            'answer': "I'm sorry, I couldn't process your query. Please try rephrasing or ask about a specific topic.",
            'status': 'error',
            'error': 'No assistant components available',
            'source': 'enhanced_assistant'
        }
    
    def _handle_calculation(self, calc_request: Dict) -> Optional[Dict[str, Any]]:
        """Handle calculation request"""
        if not self.calculator:
            return None
        
        try:
            operation = calc_request.get('operation')
            values = calc_request.get('values', [])
            
            if operation == 'add' and len(values) >= 2:
                result = values[0] + values[1]
                return {
                    'answer': f"Calculation: {values[0]} + {values[1]} = {result}",
                    'status': 'success',
                    'source': 'calculator',
                    'result': result
                }
            elif operation == 'subtract' and len(values) >= 2:
                result = values[0] - values[1]
                return {
                    'answer': f"Calculation: {values[0]} - {values[1]} = {result}",
                    'status': 'success',
                    'source': 'calculator',
                    'result': result
                }
            elif operation == 'multiply' and len(values) >= 2:
                result = values[0] * values[1]
                return {
                    'answer': f"Calculation: {values[0]} × {values[1]} = {result}",
                    'status': 'success',
                    'source': 'calculator',
                    'result': result
                }
            elif operation == 'divide' and len(values) >= 2:
                if values[1] == 0:
                    return {
                        'answer': None,
                        'status': 'error',
                        'error': 'Division by zero',
                        'source': 'calculator'
                    }
                result = values[0] / values[1]
                return {
                    'answer': f"Calculation: {values[0]} ÷ {values[1]} = {result}",
                    'status': 'success',
                    'source': 'calculator',
                    'result': result
                }
            elif operation == 'expression' and 'result' in calc_request:
                return {
                    'answer': f"Calculation: {calc_request.get('expression', '')} = {calc_request['result']}",
                    'status': 'success',
                    'source': 'calculator',
                    'result': calc_request['result']
                }
        except Exception as e:
            return {
                'answer': None,
                'status': 'error',
                'error': str(e),
                'source': 'calculator'
            }
        
        return None
    
    def _handle_equation(self, eq_request: Dict) -> Optional[Dict[str, Any]]:
        """Handle equation request"""
        if not self.equation_helper:
            return None
        
        matches = eq_request.get('matches', [])
        if matches:
            # Return first match
            eq = matches[0]
            answer = self.equation_helper.format_equation_for_display(eq['name'])
            
            # Add disclaimer
            if self.scope_guard:
                answer = self.scope_guard.add_safety_disclaimer(answer)
            
            return {
                'answer': answer,
                'status': 'success',
                'source': 'equation_helper',
                'equation': eq
            }
        
        return None
    
    def _search_expanded_knowledge(self, query: str) -> Optional[Dict[str, Any]]:
        """Search expanded knowledge base"""
        query_lower = query.lower().strip()
        
        for category, kb_entry in self.expanded_knowledge.items():
            for pattern in kb_entry['patterns']:
                if re.search(pattern, query_lower):
                    # Found match
                    response = kb_entry['responses'][0]
                    answer = response['answer']
                    
                    # Add disclaimer
                    if self.scope_guard:
                        answer = self.scope_guard.add_safety_disclaimer(answer)
                    
                    return {
                        'answer': answer,
                        'status': 'success',
                        'confidence': response['confidence'],
                        'source': 'expanded_knowledge',
                        'category': category
                    }
        
        return None


def create_enhanced_assistant() -> EnhancedAskrbGyanX:
    """
    Create enhanced Ask rbGyanX assistant.
    
    Returns
    -------
    EnhancedAskrbGyanX
        Initialized enhanced assistant
    """
    return EnhancedAskrbGyanX()

