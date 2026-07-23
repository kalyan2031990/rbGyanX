"""
Rule-Based Assistant for Ask rbGyanX

Provides educational responses without requiring LLM.
Always available as fallback.

Author: rbGyanX Team
Version: 1.0.0
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class RuleBasedAssistant:
    """
    Rule-based educational assistant for rbGyanX.
    
    Provides answers about:
    - Software usage
    - Radiobiology theory
    - Physics & statistics explanation
    
    Explicitly does NOT provide:
    - Clinical advice
    - Treatment recommendations
    """
    
    def __init__(self):
        """Initialize rule-based assistant with knowledge base"""
        self.knowledge_base = self._load_knowledge_base()
        self.disclaimer = (
            "⚠️ DISCLAIMER: This assistant provides educational information only. "
            "It does NOT provide clinical advice or treatment recommendations. "
            "All clinical decisions must be made by qualified healthcare professionals."
        )
    
    def _load_knowledge_base(self) -> Dict[str, Dict]:
        """Load knowledge base of common questions and answers"""
        return {
            # Software Usage
            'software_usage': {
                'patterns': [
                    r'how.*use.*rbgyanx',
                    r'how.*run.*step',
                    r'how.*select.*dvh',
                    r'how.*load.*data',
                    r'what.*step.*do',
                    r'workflow',
                    r'user.*manual',
                    r'getting.*started'
                ],
                'responses': [
                    {
                        'answer': """rbGyanX Workflow:

STEP 1: DVH Preprocessing
- Select your DVH folder (CSV files)
- Choose analysis type: TCP, NTCP, or Both
- Click "Run Step 1" to process DVH files

STEP 2: Clinical Data (Optional)
- Select clinical Excel file if available
- The system will validate and adapt the data
- ML analysis requires clinical data

STEP 3: Analysis Execution
- Choose which engines to run:
  * Physics only (DVH analysis)
  * Radiobiology only (TCP/NTCP models)
  * Radiobiology + ML (with clinical data)
- Click "Run Step 3" to execute

STEP 4: Results Review
- View visualizations and reports
- Check output files in the output directory

For detailed instructions, see Help → User Manual.""",
                        'confidence': 0.9
                    }
                ]
            },
            
            # TCP Models
            'tcp_models': {
                'patterns': [
                    r'what.*tcp',
                    r'tcp.*model',
                    r'tumor.*control',
                    r'poisson.*tcp',
                    r'eud.*tcp',
                    r'logistic.*tcp'
                ],
                'responses': [
                    {
                        'answer': """TCP (Tumor Control Probability) Models:

1. POISSON TCP:
   - Based on Poisson statistics
   - Assumes uniform cell kill probability
   - Formula: TCP = exp(-N₀ × exp(-αD - βD²))
   - Parameters: N₀ (initial cell number), α, β (radiosensitivity)

2. LKB-ADAPTED TCP:
   - Extends Lyman model for tumors
   - Accounts for dose heterogeneity
   - Uses D50, m, and n parameters

3. LOGISTIC TCP:
   - Sigmoid dose-response curve
   - Formula: TCP = 1 / (1 + (D50/D)^k)
   - Parameters: D50 (50% control dose), k (steepness)

4. EUD-BASED TCP:
   - Uses Equivalent Uniform Dose
   - EUD = (Σ vᵢ × Dᵢ^(1/n))^n
   - TCP calculated from EUD

References:
- Webb & Nahum (1993) - Poisson TCP
- Niemierko (1997) - EUD concept
- Wheldon et al. (1991) - TCP models""",
                        'confidence': 0.85
                    }
                ]
            },
            
            # NTCP Models
            'ntcp_models': {
                'patterns': [
                    r'what.*ntcp',
                    r'ntcp.*model',
                    r'normal.*tissue',
                    r'complication.*probability',
                    r'lyman.*kutcher',
                    r'lkb.*model',
                    r'relative.*seriality'
                ],
                'responses': [
                    {
                        'answer': """NTCP (Normal Tissue Complication Probability) Models:

1. LKB LOG-LOGISTIC:
   - Lyman-Kutcher-Burman model
   - Formula: NTCP = 1 / (1 + (TD50/m)^n)
   - Parameters: TD50 (50% complication dose), m (steepness), n (volume effect)
   - Uses effective volume: Veff = Σ(vᵢ × (Dᵢ/Dmax)^(1/n))

2. LKB PROBIT:
   - Probit transformation of LKB
   - Formula: NTCP = Φ((D - TD50) / (m × TD50))
   - Φ is the cumulative normal distribution

3. RELATIVE SERIALITY (RS) POISSON:
   - Accounts for serial vs parallel tissue architecture
   - Formula: NTCP = 1 - Π(1 - P(Dᵢ)^s)
   - Parameters: s (seriality parameter), D50, γ50

Common Parameters:
- D50: Dose for 50% complication probability
- m: Steepness of dose-response curve
- n: Volume effect parameter (0=serial, 1=parallel)

References:
- Lyman (1985) - LKB model
- Kutcher & Burman (1989) - Effective volume
- Niemierko & Goitein (1993) - Relative seriality""",
                        'confidence': 0.85
                    }
                ]
            },
            
            # Model Parameters
            'parameters': {
                'patterns': [
                    r'what.*parameter',
                    r'alpha.*beta',
                    r'd50',
                    r'td50',
                    r'gamma',
                    r'm.*parameter',
                    r'n.*parameter',
                    r'meaning.*parameter'
                ],
                'responses': [
                    {
                        'answer': """Model Parameters Explained:

TCP PARAMETERS:
- α (alpha): Linear radiosensitivity coefficient (Gy⁻¹)
- β (beta): Quadratic radiosensitivity coefficient (Gy⁻²)
- α/β ratio: Determines fractionation sensitivity
- N₀: Initial clonogenic cell number
- D50: Dose for 50% tumor control (Gy)
- m: Steepness parameter (dimensionless)
- n: Volume effect parameter (0-1)

NTCP PARAMETERS:
- TD50: Tolerance dose for 50% complication (Gy)
- m: Steepness of dose-response curve
- n: Volume effect parameter
  * n ≈ 0: Serial organ (spinal cord)
  * n ≈ 1: Parallel organ (lung, liver)
  * n ≈ 0.7: Intermediate (parotid)
- D50: Dose for 50% complication (Gy)
- γ50: Normalized dose-response gradient

PHYSICAL MEANING:
- α/β: Low values (2-3 Gy) = late effects, high values (10+ Gy) = early effects
- n: Determines how volume affects complication risk
- m: Controls steepness of dose-response relationship

References:
- Fowler (1989) - α/β ratios
- Emami et al. (1991) - TD50 values
- Burman et al. (1991) - Normal tissue parameters""",
                        'confidence': 0.8
                    }
                ]
            },
            
            # Statistics
            'statistics': {
                'patterns': [
                    r'statistic',
                    r'p.*value',
                    r'confidence.*interval',
                    r'significance',
                    r'correlation',
                    r'regression',
                    r'auc',
                    r'roc.*curve'
                ],
                'responses': [
                    {
                        'answer': """Statistical Concepts in rbGyanX:

P-VALUE:
- Probability of observing results as extreme if null hypothesis is true
- p < 0.05 typically considered significant
- Lower p-value = stronger evidence against null hypothesis

CONFIDENCE INTERVAL (CI):
- Range of values likely to contain true parameter
- 95% CI means 95% confidence true value is within range
- Narrower CI = more precise estimate

CORRELATION:
- Measures linear relationship between variables
- Pearson r: -1 to +1 (0 = no correlation)
- Spearman ρ: For non-linear relationships

REGRESSION:
- Linear: y = a + bx (predicts continuous outcome)
- Logistic: logit(p) = a + bx (predicts probability)
- Used for NTCP/TCP modeling

ROC CURVE & AUC:
- ROC: Receiver Operating Characteristic curve
- Plots sensitivity vs (1 - specificity)
- AUC: Area Under Curve (0.5 = random, 1.0 = perfect)
- AUC > 0.7 considered good discrimination

References:
- Altman & Bland (1995) - Statistics in medicine
- Hanley & McNeil (1982) - ROC curve analysis""",
                        'confidence': 0.75
                    }
                ]
            },
            
            # Physics
            'physics': {
                'patterns': [
                    r'dose.*response',
                    r'radiosensitivity',
                    r'fractionation',
                    r'eqd2',
                    r'biological.*dose',
                    r'linear.*quadratic',
                    r'lq.*model'
                ],
                'responses': [
                    {
                        'answer': """Medical Physics Concepts:

LINEAR-QUADRratic (LQ) MODEL:
- Describes cell survival: S = exp(-αD - βD²)
- α: Linear component (single-hit events)
- β: Quadratic component (two-hit events)
- α/β ratio: Determines fractionation sensitivity

FRACTIONATION:
- Multiple small doses instead of single large dose
- Spares normal tissues more than tumors (if α/β_tumor > α/β_normal)
- Standard: 2 Gy per fraction

EQD2 (EQUIVALENT DOSE IN 2 GY FRACTIONS):
- Converts any fractionation to 2 Gy equivalent
- Formula: EQD2 = D × (d + α/β) / (2 + α/β)
- Where D = total dose, d = dose per fraction

BIOLOGICAL DOSE:
- Accounts for fractionation effects
- Uses LQ model to calculate equivalent dose
- Important for comparing different fractionation schemes

RADIOSENSITIVITY:
- Intrinsic sensitivity of cells to radiation
- Depends on DNA repair capacity
- Varies by tissue type and tumor type

References:
- Fowler (1989) - Fractionation effects
- Barendsen (1982) - LQ model
- Withers (1992) - Biological dose concepts""",
                        'confidence': 0.8
                    }
                ]
            },
            
            # General Help
            'general_help': {
                'patterns': [
                    r'help',
                    r'what.*can.*ask',
                    r'what.*questions',
                    r'how.*work'
                ],
                'responses': [
                    {
                        'answer': """Ask rbGyanX can help with:

✅ SOFTWARE USAGE:
- How to use rbGyanX
- Workflow steps
- Data input requirements
- Output interpretation

✅ RADIOBIOLOGY THEORY:
- TCP/NTCP model explanations
- Model parameters and meanings
- Dose-response relationships
- Literature references

✅ PHYSICS & STATISTICS:
- Medical physics concepts
- Statistical methods
- Model validation
- Quality assurance

❌ CANNOT PROVIDE:
- Clinical advice
- Treatment recommendations
- Patient-specific interpretations
- Diagnostic suggestions

This assistant is for educational purposes only.""",
                        'confidence': 0.9
                    }
                ]
            }
        }
    
    def ask(self, query: str) -> Dict[str, Any]:
        """
        Answer a query using rule-based matching.
        
        Parameters
        ----------
        query : str
            User query
        
        Returns
        -------
        Dict
            Response with 'answer', 'status', 'confidence', 'source'
        """
        query_lower = query.lower().strip()
        
        # Check for clinical advice requests (block these)
        clinical_patterns = [
            r'should.*treat',
            r'recommend.*treatment',
            r'what.*dose.*give',
            r'clinical.*advice',
            r'patient.*should',
            r'diagnosis',
            r'prognosis'
        ]
        
        for pattern in clinical_patterns:
            if re.search(pattern, query_lower):
                return {
                    'answer': None,
                    'status': 'blocked',
                    'error': (
                        "I cannot provide clinical advice or treatment recommendations. "
                        "This assistant is for educational purposes only. "
                        "Please consult qualified healthcare professionals for clinical decisions."
                    ),
                    'confidence': 1.0,
                    'source': 'rule_based'
                }
        
        # Try to match against knowledge base
        best_match = None
        best_confidence = 0.0
        
        for category, kb_entry in self.knowledge_base.items():
            for pattern in kb_entry['patterns']:
                if re.search(pattern, query_lower):
                    # Found a match, get best response
                    for response in kb_entry['responses']:
                        if response['confidence'] > best_confidence:
                            best_match = response['answer']
                            best_confidence = response['confidence']
                            break
                    break
        
        if best_match:
            # Add disclaimer
            full_answer = f"{best_match}\n\n{self.disclaimer}"
            return {
                'answer': full_answer,
                'status': 'success',
                'error': None,
                'confidence': best_confidence,
                'source': 'rule_based'
            }
        else:
            # No match found - provide helpful response
            return {
                'answer': (
                    "I couldn't find a specific answer to your question in my knowledge base.\n\n"
                    "I can help with:\n"
                    "- Software usage and workflow\n"
                    "- TCP/NTCP model explanations\n"
                    "- Model parameters and physics concepts\n"
                    "- Statistical methods\n\n"
                    "Please try rephrasing your question or ask about a specific topic.\n\n"
                    f"{self.disclaimer}"
                ),
                'status': 'partial',
                'error': None,
                'confidence': 0.5,
                'source': 'rule_based'
            }
    
    def is_available(self) -> bool:
        """
        Check if rule-based assistant is available.
        
        Returns
        -------
        bool
            Always True (rule-based is always available)
        """
        return True


def create_rule_based_assistant() -> RuleBasedAssistant:
    """
    Create a rule-based assistant instance.
    
    Returns
    -------
    RuleBasedAssistant
        Initialized rule-based assistant
    """
    return RuleBasedAssistant()

