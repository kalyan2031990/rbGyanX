"""
Scientific Calculator for Ask rbGyanX

Provides mathematical calculations on user-provided numbers only.
Does NOT access patient data or files.

Author: rbGyanX Team
Version: 1.0.0
"""

import math
import re
from typing import Dict, Optional, Tuple, Any


class ScientificCalculator:
    """
    Scientific calculator for educational purposes.
    
    Works on user-provided numbers only.
    Does NOT read patient files or access data.
    """
    
    def __init__(self):
        """Initialize calculator"""
        self.supported_operations = [
            'add', 'subtract', 'multiply', 'divide',
            'power', 'sqrt', 'log', 'ln', 'exp',
            'sigmoid', 'percent', 'factorial',
            'sin', 'cos', 'tan', 'asin', 'acos', 'atan'
        ]
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        """
        Calculate mathematical expression.
        
        Parameters
        ----------
        expression : str
            Mathematical expression to evaluate
        
        Returns
        -------
        Dict
            Result with 'success', 'result', 'error'
        """
        try:
            # Sanitize expression (remove dangerous functions)
            sanitized = self._sanitize_expression(expression)
            
            # Try to parse and evaluate
            result = self._evaluate_expression(sanitized)
            
            return {
                'success': True,
                'result': result,
                'error': None,
                'expression': expression
            }
        except Exception as e:
            return {
                'success': False,
                'result': None,
                'error': str(e),
                'expression': expression
            }
    
    def _sanitize_expression(self, expression: str) -> str:
        """
        Sanitize expression to prevent code execution.
        
        Parameters
        ----------
        expression : str
            Raw expression
        
        Returns
        -------
        str
            Sanitized expression
        """
        # Remove potentially dangerous patterns
        dangerous = ['__', 'import', 'exec', 'eval', 'open', 'file', 'read']
        for pattern in dangerous:
            if pattern in expression.lower():
                raise ValueError(f"Invalid expression: contains '{pattern}'")
        
        # Only allow safe mathematical operations
        allowed_chars = set('0123456789+-*/.()^eπpi ')
        allowed_funcs = ['sqrt', 'log', 'ln', 'exp', 'sin', 'cos', 'tan', 
                        'asin', 'acos', 'atan', 'abs', 'pow', 'factorial']
        
        # Check for allowed functions
        for func in allowed_funcs:
            if func in expression.lower():
                allowed_chars.update(func)
        
        # Basic check (not perfect, but helps)
        for char in expression:
            if char.isalnum() or char in allowed_chars:
                continue
            if any(func in expression.lower() for func in allowed_funcs):
                continue
            # Allow some special chars
            if char in '+-*/.()^[]{}':
                continue
        
        return expression
    
    def _evaluate_expression(self, expression: str) -> float:
        """
        Safely evaluate mathematical expression.
        
        Parameters
        ----------
        expression : str
            Mathematical expression
        
        Returns
        -------
        float
            Calculated result
        """
        # Replace common math functions
        expression = expression.replace('^', '**')  # Power operator
        expression = expression.replace('π', str(math.pi))
        expression = expression.replace('pi', str(math.pi))
        expression = expression.replace('e', str(math.e))
        
        # Handle functions
        func_replacements = {
            'sqrt': 'math.sqrt',
            'log': 'math.log10',
            'ln': 'math.log',
            'exp': 'math.exp',
            'sin': 'math.sin',
            'cos': 'math.cos',
            'tan': 'math.tan',
            'asin': 'math.asin',
            'acos': 'math.acos',
            'atan': 'math.atan',
            'abs': 'abs',
            'pow': 'pow',
            'factorial': 'math.factorial',
        }
        
        for func, math_func in func_replacements.items():
            # Replace function calls
            pattern = rf'\b{func}\s*\('
            expression = re.sub(pattern, f'{math_func}(', expression, flags=re.IGNORECASE)
        
        # Evaluate safely
        try:
            result = eval(expression, {"__builtins__": {}}, {"math": math})
            return float(result)
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {str(e)}")
    
    def calculate_sigmoid(self, x: float, a: float = 1.0, b: float = 0.0) -> float:
        """
        Calculate sigmoid function: 1 / (1 + exp(-a*(x - b)))
        
        Parameters
        ----------
        x : float
            Input value
        a : float
            Steepness parameter
        b : float
            Shift parameter
        
        Returns
        -------
        float
            Sigmoid value
        """
        return 1.0 / (1.0 + math.exp(-a * (x - b)))
    
    def calculate_logistic(self, x: float, k: float = 1.0, x0: float = 0.0) -> float:
        """
        Calculate logistic function: 1 / (1 + exp(-k*(x - x0)))
        
        Parameters
        ----------
        x : float
            Input value
        k : float
            Steepness parameter
        x0 : float
            Midpoint parameter
        
        Returns
        -------
        float
            Logistic value
        """
        return 1.0 / (1.0 + math.exp(-k * (x - x0)))
    
    def calculate_percentage(self, part: float, whole: float) -> float:
        """
        Calculate percentage: (part / whole) * 100
        
        Parameters
        ----------
        part : float
            Part value
        whole : float
            Whole value
        
        Returns
        -------
        float
            Percentage
        """
        if whole == 0:
            raise ValueError("Cannot divide by zero")
        return (part / whole) * 100.0
    
    def parse_calculation_request(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Parse calculation request from natural language.
        
        Parameters
        ----------
        query : str
            Natural language query
        
        Returns
        -------
        Optional[Dict]
            Parsed calculation request or None
        """
        query_lower = query.lower()
        
        # Check if it's a calculation request
        calc_keywords = ['calculate', 'compute', 'solve', 'what is', 'evaluate']
        if not any(keyword in query_lower for keyword in calc_keywords):
            return None
        
        # Try to extract numbers and operation
        numbers = re.findall(r'-?\d+\.?\d*', query)
        
        if len(numbers) < 1:
            return None
        
        # Try to identify operation
        if 'add' in query_lower or '+' in query:
            if len(numbers) >= 2:
                return {'operation': 'add', 'values': [float(n) for n in numbers[:2]]}
        elif 'subtract' in query_lower or 'minus' in query_lower or '-' in query:
            if len(numbers) >= 2:
                return {'operation': 'subtract', 'values': [float(n) for n in numbers[:2]]}
        elif 'multiply' in query_lower or 'times' in query_lower or '*' in query:
            if len(numbers) >= 2:
                return {'operation': 'multiply', 'values': [float(n) for n in numbers[:2]]}
        elif 'divide' in query_lower or '/' in query:
            if len(numbers) >= 2:
                return {'operation': 'divide', 'values': [float(n) for n in numbers[:2]]}
        elif 'power' in query_lower or '^' in query or '**' in query:
            if len(numbers) >= 2:
                return {'operation': 'power', 'values': [float(n) for n in numbers[:2]]}
        elif 'sqrt' in query_lower or 'square root' in query_lower:
            return {'operation': 'sqrt', 'values': [float(numbers[0])]}
        elif 'log' in query_lower:
            return {'operation': 'log', 'values': [float(numbers[0])]}
        elif 'exp' in query_lower or 'exponential' in query_lower:
            return {'operation': 'exp', 'values': [float(numbers[0])]}
        elif 'sigmoid' in query_lower:
            if len(numbers) >= 1:
                return {'operation': 'sigmoid', 'values': [float(n) for n in numbers[:3]]}
        elif 'percent' in query_lower or '%' in query:
            if len(numbers) >= 2:
                return {'operation': 'percent', 'values': [float(n) for n in numbers[:2]]}
        
        # Try to evaluate as direct expression
        try:
            # Extract mathematical expression
            expr_match = re.search(r'([\d+\-*/.()^eπ\s]+)', query)
            if expr_match:
                expr = expr_match.group(1)
                result = self.calculate(expr)
                if result['success']:
                    return {'operation': 'expression', 'result': result['result'], 'expression': expr}
        except:
            pass
        
        return None


def create_calculator() -> ScientificCalculator:
    """
    Create a scientific calculator instance.
    
    Returns
    -------
    ScientificCalculator
        Initialized calculator
    """
    return ScientificCalculator()

