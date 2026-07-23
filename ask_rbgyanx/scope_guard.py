"""
Scope Guard for Ask rbGyanX

Enforces ethical boundaries and prevents clinical decision making.

Author: rbGyanX Team
Version: 1.0.0
"""

import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class ScopeGuard:
    """
    Hard guard system to prevent Ask rbGyanX from:
    - Making clinical decisions
    - Accessing patient data
    - Providing treatment recommendations
    """
    
    def __init__(self):
        """Initialize scope guard with blocking patterns"""
        self.blocked_patterns = self._load_blocked_patterns()
        self.allowed_patterns = self._load_allowed_patterns()
        self.data_access_patterns = self._load_data_access_patterns()
    
    def _load_blocked_patterns(self) -> List[Tuple[str, str]]:
        """
        Load patterns that should be blocked (clinical decision making).
        
        Returns
        -------
        List[Tuple[str, str]]
            List of (pattern, reason) tuples
        """
        return [
            # Treatment recommendations
            (r'should.*treat', 'Treatment recommendations are not allowed'),
            (r'recommend.*treatment', 'Treatment recommendations are not allowed'),
            (r'prescribe.*dose', 'Dose prescription is a clinical decision'),
            (r'what.*dose.*give', 'Dose prescription is a clinical decision'),
            (r'optimal.*dose', 'Optimal dose determination requires clinical judgment'),
            
            # Patient-specific predictions
            (r'predict.*outcome', 'Outcome prediction for specific patients is not allowed'),
            (r'will.*patient.*survive', 'Prognostic predictions are clinical decisions'),
            (r'patient.*prognosis', 'Prognostic assessment requires clinical judgment'),
            (r'calculate.*for.*patient', 'Patient-specific calculations are not allowed'),
            
            # Clinical advice
            (r'clinical.*advice', 'Clinical advice must come from qualified professionals'),
            (r'what.*should.*do', 'Clinical decision making is not allowed'),
            (r'how.*treat.*patient', 'Treatment planning requires clinical expertise'),
            (r'diagnosis', 'Diagnostic information requires clinical assessment'),
            
            # Data access attempts
            (r'read.*dvh', 'DVH file access is blocked'),
            (r'load.*patient.*data', 'Patient data access is blocked'),
            (r'access.*clinical.*file', 'Clinical file access is blocked'),
            (r'open.*excel.*file', 'File access is not allowed'),
            
            # Autonomous decisions
            (r'make.*decision', 'Autonomous decision making is not allowed'),
            (r'decide.*for.*me', 'Decision making requires human judgment'),
            (r'automatically.*choose', 'Automatic selection is not allowed'),
        ]
    
    def _load_allowed_patterns(self) -> List[str]:
        """
        Load patterns that are explicitly allowed (educational).
        
        Returns
        -------
        List[str]
            List of allowed pattern strings
        """
        return [
            r'explain.*concept',
            r'what.*is.*tcp',
            r'what.*is.*ntcp',
            r'how.*does.*model.*work',
            r'what.*does.*parameter.*mean',
            r'calculate.*equation',  # Mathematical calculations OK
            r'solve.*math',  # Math problems OK
            r'write.*equation',  # Equation drafting OK
            r'help.*with.*paper',  # Research writing help OK
            r'explain.*output',  # Output interpretation OK
            r'what.*does.*warning.*mean',  # QA explanation OK
        ]
    
    def _load_data_access_patterns(self) -> List[str]:
        """
        Load patterns that indicate data access attempts.
        
        Returns
        -------
        List[str]
            List of data access pattern strings
        """
        return [
            r'read.*file',
            r'load.*data',
            r'access.*dvh',
            r'open.*patient',
            r'get.*from.*file',
            r'import.*data',
            r'read.*excel',
            r'load.*clinical',
        ]
    
    def check_query(self, query: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if query is within allowed scope.
        
        Parameters
        ----------
        query : str
            User query to check
        
        Returns
        -------
        Tuple[bool, Optional[str], Optional[str]]
            (is_allowed, block_reason, suggestion)
            - is_allowed: True if query is allowed
            - block_reason: Reason for blocking if not allowed
            - suggestion: Educational guidance if blocked
        """
        query_lower = query.lower().strip()
        
        # Check for blocked patterns
        for pattern, reason in self.blocked_patterns:
            if re.search(pattern, query_lower):
                suggestion = self._generate_suggestion(query_lower, reason)
                return False, reason, suggestion
        
        # Check for data access attempts
        for pattern in self.data_access_patterns:
            if re.search(pattern, query_lower):
                return False, 'Data access is not allowed. Ask rbGyanX cannot read files or access patient data.', \
                       'Please ask about concepts, equations, or theory instead of requesting data access.'
        
        # Query is allowed
        return True, None, None
    
    def _generate_suggestion(self, query: str, reason: str) -> str:
        """
        Generate educational suggestion when query is blocked.
        
        Parameters
        ----------
        query : str
            Blocked query
        reason : str
            Reason for blocking
        
        Returns
        -------
        str
            Educational suggestion
        """
        suggestions = {
            'treatment': (
                "I cannot provide treatment recommendations. "
                "For treatment planning, please consult:\n"
                "- Qualified radiation oncologists\n"
                "- Clinical practice guidelines\n"
                "- Institutional protocols\n\n"
                "I can help explain:\n"
                "- TCP/NTCP model theory\n"
                "- Dose-response relationships\n"
                "- Model parameters and their meanings"
            ),
            'prediction': (
                "I cannot predict patient outcomes. "
                "For prognostic information, please consult:\n"
                "- Clinical staging systems\n"
                "- Evidence-based prognostic factors\n"
                "- Published survival data\n\n"
                "I can help explain:\n"
                "- Statistical concepts (survival analysis, hazard ratios)\n"
                "- Model validation methods\n"
                "- Literature search strategies"
            ),
            'data': (
                "I cannot access patient data or files. "
                "For data analysis, please use:\n"
                "- rbGyanX analysis tools (Steps 1-4)\n"
                "- Clinical data management systems\n"
                "- Statistical software\n\n"
                "I can help explain:\n"
                "- How to interpret rbGyanX outputs\n"
                "- Statistical methods\n"
                "- Data analysis concepts"
            ),
            'default': (
                "This question is outside my educational scope. "
                "I can help with:\n"
                "- Radiobiology theory and models\n"
                "- Physics and statistics concepts\n"
                "- Software usage and workflow\n"
                "- Mathematical calculations\n"
                "- Research writing assistance\n\n"
                "For clinical questions, please consult qualified healthcare professionals."
            )
        }
        
        if 'treatment' in reason.lower() or 'dose' in reason.lower():
            return suggestions['treatment']
        elif 'predict' in reason.lower() or 'outcome' in reason.lower():
            return suggestions['prediction']
        elif 'data' in reason.lower() or 'file' in reason.lower():
            return suggestions['data']
        else:
            return suggestions['default']
    
    def add_safety_disclaimer(self, response: str) -> str:
        """
        Add safety disclaimer to response.
        
        Parameters
        ----------
        response : str
            Response text
        
        Returns
        -------
        str
            Response with disclaimer appended
        """
        disclaimer = (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ EDUCATIONAL USE ONLY\n"
            "This is educational support, not clinical decision making.\n"
            "All clinical decisions must be made by qualified healthcare professionals.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Only add if not already present
        if disclaimer.strip() not in response:
            return response + disclaimer
        
        return response


def create_scope_guard() -> ScopeGuard:
    """
    Create a scope guard instance.
    
    Returns
    -------
    ScopeGuard
        Initialized scope guard
    """
    return ScopeGuard()

