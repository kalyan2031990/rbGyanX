"""
Math Tools and Equation Helper for Ask rbGyanX

Provides equation rendering and symbolic expression help.
Does NOT access patient data.

Author: rbGyanX Team
Version: 1.0.0
"""

import re
from typing import Dict, List, Optional, Tuple, Any


class MathEquationHelper:
    """
    Helper for mathematical equations and symbolic expressions.
    
    Provides LaTeX-style equation rendering and equation drafting assistance.
    """
    
    def __init__(self):
        """Initialize equation helper"""
        self.equation_templates = self._load_equation_templates()
    
    def _load_equation_templates(self) -> Dict[str, Dict]:
        """Load equation templates for common radiobiology equations"""
        return {
            'tcp_poisson': {
                'name': 'Poisson TCP',
                'latex': r'TCP = \exp(-N_0 \cdot \exp(-\alpha D - \beta D^2))',
                'text': 'TCP = exp(-N₀ × exp(-αD - βD²))',
                'parameters': {
                    'N₀': 'Initial clonogenic cell number',
                    'α': 'Linear radiosensitivity coefficient (Gy⁻¹)',
                    'β': 'Quadratic radiosensitivity coefficient (Gy⁻²)',
                    'D': 'Dose (Gy)'
                }
            },
            'tcp_logistic': {
                'name': 'Logistic TCP',
                'latex': r'TCP = \frac{1}{1 + \left(\frac{D_{50}}{D}\right)^k}',
                'text': 'TCP = 1 / (1 + (D₅₀/D)^k)',
                'parameters': {
                    'D₅₀': 'Dose for 50% tumor control (Gy)',
                    'D': 'Dose (Gy)',
                    'k': 'Steepness parameter'
                }
            },
            'ntcp_lkb': {
                'name': 'LKB NTCP',
                'latex': r'NTCP = \frac{1}{1 + \left(\frac{TD_{50}}{m}\right)^n}',
                'text': 'NTCP = 1 / (1 + (TD₅₀/m)^n)',
                'parameters': {
                    'TD₅₀': 'Tolerance dose for 50% complication (Gy)',
                    'm': 'Steepness parameter',
                    'n': 'Volume effect parameter'
                }
            },
            'eud': {
                'name': 'Equivalent Uniform Dose',
                'latex': r'EUD = \left(\sum_i v_i \cdot D_i^{1/n}\right)^n',
                'text': 'EUD = (Σᵢ vᵢ × Dᵢ^(1/n))^n',
                'parameters': {
                    'vᵢ': 'Volume fraction of voxel i',
                    'Dᵢ': 'Dose to voxel i (Gy)',
                    'n': 'Volume effect parameter'
                }
            },
            'bed': {
                'name': 'Biological Effective Dose',
                'latex': r'BED = D \cdot \left(1 + \frac{d}{\alpha/\beta}\right)',
                'text': 'BED = D × (1 + d/(α/β))',
                'parameters': {
                    'D': 'Total dose (Gy)',
                    'd': 'Dose per fraction (Gy)',
                    'α/β': 'Alpha/beta ratio (Gy)'
                }
            },
            'eqd2': {
                'name': 'Equivalent Dose in 2 Gy Fractions',
                'latex': r'EQD_2 = D \cdot \frac{d + \alpha/\beta}{2 + \alpha/\beta}',
                'text': 'EQD₂ = D × (d + α/β) / (2 + α/β)',
                'parameters': {
                    'D': 'Total dose (Gy)',
                    'd': 'Dose per fraction (Gy)',
                    'α/β': 'Alpha/beta ratio (Gy)'
                }
            },
            'lq_survival': {
                'name': 'Linear-Quadratic Cell Survival',
                'latex': r'S = \exp(-\alpha D - \beta D^2)',
                'text': 'S = exp(-αD - βD²)',
                'parameters': {
                    'S': 'Surviving fraction',
                    'α': 'Linear radiosensitivity coefficient (Gy⁻¹)',
                    'β': 'Quadratic radiosensitivity coefficient (Gy⁻²)',
                    'D': 'Dose (Gy)'
                }
            },
            'sigmoid': {
                'name': 'Sigmoid Function',
                'latex': r'f(x) = \frac{1}{1 + \exp(-a(x - b))}',
                'text': 'f(x) = 1 / (1 + exp(-a(x - b)))',
                'parameters': {
                    'a': 'Steepness parameter',
                    'b': 'Shift parameter',
                    'x': 'Input value'
                }
            },
            'logistic': {
                'name': 'Logistic Function',
                'latex': r'f(x) = \frac{1}{1 + \exp(-k(x - x_0))}',
                'text': 'f(x) = 1 / (1 + exp(-k(x - x₀)))',
                'parameters': {
                    'k': 'Steepness parameter',
                    'x₀': 'Midpoint parameter',
                    'x': 'Input value'
                }
            }
        }
    
    def get_equation(self, equation_name: str) -> Optional[Dict[str, Any]]:
        """
        Get equation template by name.
        
        Parameters
        ----------
        equation_name : str
            Name of equation (e.g., 'tcp_poisson', 'ntcp_lkb')
        
        Returns
        -------
        Optional[Dict]
            Equation template or None if not found
        """
        return self.equation_templates.get(equation_name.lower())
    
    def list_equations(self) -> List[str]:
        """
        List all available equations.
        
        Returns
        -------
        List[str]
            List of equation names
        """
        return list(self.equation_templates.keys())
    
    def search_equations(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for equations matching query.
        
        Parameters
        ----------
        query : str
            Search query
        
        Returns
        -------
        List[Dict]
            List of matching equations
        """
        query_lower = query.lower()
        matches = []
        
        for name, eq_data in self.equation_templates.items():
            if (query_lower in name.lower() or 
                query_lower in eq_data['name'].lower() or
                query_lower in eq_data['text'].lower()):
                matches.append({
                    'name': name,
                    'display_name': eq_data['name'],
                    'text': eq_data['text'],
                    'latex': eq_data.get('latex', ''),
                    'parameters': eq_data.get('parameters', {})
                })
        
        return matches
    
    def format_equation_for_display(self, equation_name: str) -> str:
        """
        Format equation for display in text.
        
        Parameters
        ----------
        equation_name : str
            Name of equation
        
        Returns
        -------
        str
            Formatted equation text
        """
        eq = self.get_equation(equation_name)
        if not eq:
            return f"Equation '{equation_name}' not found."
        
        result = f"{eq['name']}:\n\n"
        result += f"Text form: {eq['text']}\n\n"
        
        if eq.get('latex'):
            result += f"LaTeX form: {eq['latex']}\n\n"
        
        if eq.get('parameters'):
            result += "Parameters:\n"
            for param, desc in eq['parameters'].items():
                result += f"  {param}: {desc}\n"
        
        return result
    
    def parse_equation_request(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Parse equation request from natural language.
        
        Parameters
        ----------
        query : str
            Natural language query
        
        Returns
        -------
        Optional[Dict]
            Parsed equation request or None
        """
        query_lower = query.lower()
        
        # Check for equation keywords
        eq_keywords = ['equation', 'formula', 'write', 'show', 'display']
        if not any(keyword in query_lower for keyword in eq_keywords):
            return None
        
        # Search for equation matches
        matches = self.search_equations(query)
        
        if matches:
            return {
                'type': 'equation_request',
                'matches': matches,
                'query': query
            }
        
        return None


def create_equation_helper() -> MathEquationHelper:
    """
    Create an equation helper instance.
    
    Returns
    -------
    MathEquationHelper
        Initialized equation helper
    """
    return MathEquationHelper()

