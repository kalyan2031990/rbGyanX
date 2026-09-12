"""
Scientific Calculator for Ask rbGyanX

Provides mathematical calculations on user-provided numbers only.
Does NOT access patient data or files.

Evaluation strategy (rewritten in v1.3.0). Expressions are parsed with :mod:`ast` and walked
against an explicit allow-list of node types, operators, functions and constants. Anything not on
the list is refused by name. ``eval`` is not used.

The previous implementation called ``eval(expression, {"__builtins__": {}}, {"math": math})``
behind a blocklist that checked for a handful of substrings ("import", "exec", "__", ...). A
blocklist on an ``eval`` of user input is the wrong shape of defence: it has to anticipate every
spelling of every attack, and its companion character check was inert -- every branch of that
loop ended in ``continue``, so it rejected nothing.

Fixing it also fixed three advertised functions that had never worked. ``exp(1)``, ``abs(-3)``
and ``pow(2,3)`` all failed: the old code textually substituted ``'e'`` with ``str(math.e)``
*before* rewriting function names, which turned ``exp(`` into ``2.718281828459045xp(``, and
``abs``/``pow`` are builtins that an empty ``__builtins__`` had removed. Resolving names against
an explicit table instead of rewriting the source string removes both failure modes at once.

Author: rbGyanX Team
Version: 1.0.0
"""

import ast
import math
import re
from collections.abc import Callable
from typing import Any

#: Functions callable from an expression, resolved by name rather than by string rewriting.
#: ``log`` is base 10 (matching the original intent) and ``ln`` is the natural log.
_ALLOWED_FUNCTIONS: dict[str, Callable[..., float]] = {
    "sqrt": math.sqrt,
    "log": math.log10,
    "log10": math.log10,
    "log2": math.log2,
    "ln": math.log,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "abs": abs,
    "pow": pow,
    "factorial": math.factorial,
    "floor": math.floor,
    "ceil": math.ceil,
    "degrees": math.degrees,
    "radians": math.radians,
}

#: The only bare names an expression may reference.
_ALLOWED_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

#: Binary and unary operators, mapped to their implementations.
_ALLOWED_BINARY_OPERATORS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}

_ALLOWED_UNARY_OPERATORS: dict[type, Callable[[Any], Any]] = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}

#: Caps that keep a one-line expression from becoming a denial of service. ``2**10**10`` would
#: otherwise try to materialise a number with billions of digits before anything could reject it.
_MAX_POW_EXPONENT = 1000
_MAX_FACTORIAL_INPUT = 170  # 171! overflows a float


class UnsafeExpressionError(ValueError):
    """The expression contains something outside the allow-list.

    A ValueError subclass so that ``calculate`` keeps reporting it through the same
    ``{'success': False, 'error': ...}`` contract as any other bad input.
    """


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
    
    def calculate(self, expression: str) -> dict[str, Any]:
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
        """Normalise user-friendly notation into Python syntax.

        Only two rewrites happen, both purely syntactic: ``^`` means exponentiation to a user but
        bitwise XOR to Python, and ``\u03c0`` is a spelling of ``pi``. Everything else is left alone --
        the safety decision belongs to the AST walk in :meth:`_evaluate_expression`, not to string
        munging. In particular no attempt is made to substitute constants textually, which is what
        used to corrupt ``exp(`` into ``2.718...xp(``.
        """
        if not isinstance(expression, str):
            raise UnsafeExpressionError("Expression must be a string")
        if not expression.strip():
            raise UnsafeExpressionError("Empty expression")
        if len(expression) > 500:
            raise UnsafeExpressionError("Expression too long (limit 500 characters)")

        return expression.replace("^", "**").replace("\u03c0", "pi")

    def _evaluate_expression(self, expression: str) -> float:
        """Parse and evaluate an expression against the allow-list.

        Returns
        -------
        float
            Calculated result.

        Raises
        ------
        UnsafeExpressionError
            If the expression contains any construct not explicitly permitted.
        ValueError
            If the expression is permitted but mathematically invalid (e.g. ``sqrt(-1)``).
        """
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise UnsafeExpressionError(f"Could not parse expression: {exc.msg}") from exc

        result = self._eval_node(tree.body)

        if isinstance(result, complex):
            raise ValueError("Expression produced a complex number")
        return float(result)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate one allow-listed AST node.

        Written as an explicit type dispatch rather than a generic visitor so that the set of
        permitted constructs is readable in one place, and so that anything new in the grammar
        is refused by default instead of inherited silently.
        """
        if isinstance(node, ast.Constant):
            # bool is a subclass of int; reject it so True/False cannot stand in for 1/0.
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise UnsafeExpressionError(
                    f"Only numeric literals are allowed, got {type(node.value).__name__}"
                )
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in _ALLOWED_CONSTANTS:
                raise UnsafeExpressionError(
                    f"Unknown name '{node.id}'. Allowed constants: "
                    f"{', '.join(sorted(_ALLOWED_CONSTANTS))}."
                )
            return _ALLOWED_CONSTANTS[node.id]

        if isinstance(node, ast.BinOp):
            operator = _ALLOWED_BINARY_OPERATORS.get(type(node.op))
            if operator is None:
                raise UnsafeExpressionError(
                    f"Operator {type(node.op).__name__} is not allowed"
                )
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Pow):
                self._check_power(right)
            try:
                return operator(left, right)
            except ZeroDivisionError as exc:
                raise ValueError("Division by zero") from exc

        if isinstance(node, ast.UnaryOp):
            operator = _ALLOWED_UNARY_OPERATORS.get(type(node.op))
            if operator is None:
                raise UnsafeExpressionError(
                    f"Unary operator {type(node.op).__name__} is not allowed"
                )
            return operator(self._eval_node(node.operand))

        if isinstance(node, ast.Call):
            return self._eval_call(node)

        raise UnsafeExpressionError(
            f"Expression element {type(node).__name__} is not allowed"
        )

    def _eval_call(self, node: ast.Call) -> Any:
        """Evaluate a call to an allow-listed function.

        ``node.func`` must be a bare :class:`ast.Name`. Rejecting :class:`ast.Attribute` here is
        what keeps ``math.__loader__`` and every other dotted traversal out, without needing to
        guess at attribute names.
        """
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError(
                "Only direct calls to named functions are allowed (no attribute access)"
            )
        name = node.func.id
        function = _ALLOWED_FUNCTIONS.get(name)
        if function is None:
            raise UnsafeExpressionError(
                f"Unknown function '{name}'. Allowed: {', '.join(sorted(_ALLOWED_FUNCTIONS))}."
            )
        if node.keywords:
            raise UnsafeExpressionError(f"{name}() does not accept keyword arguments here")

        args = [self._eval_node(arg) for arg in node.args]

        if name == "factorial":
            self._check_factorial(args)
        if name == "pow" and len(args) >= 2:
            self._check_power(args[1])

        try:
            return function(*args)
        except ZeroDivisionError as exc:
            raise ValueError("Division by zero") from exc
        except (TypeError, OverflowError) as exc:
            raise ValueError(f"{name}(): {exc}") from exc

    @staticmethod
    def _check_power(exponent: Any) -> None:
        """Refuse exponents large enough to hang the interpreter."""
        if isinstance(exponent, (int, float)) and abs(exponent) > _MAX_POW_EXPONENT:
            raise UnsafeExpressionError(
                f"Exponent magnitude exceeds the limit of {_MAX_POW_EXPONENT}"
            )

    @staticmethod
    def _check_factorial(args: list) -> None:
        """factorial() grows fast enough that the input needs a cap, not just a type check."""
        if len(args) != 1:
            raise ValueError("factorial() takes exactly one argument")
        value = args[0]
        if isinstance(value, float) and not value.is_integer():
            raise ValueError("factorial() requires an integer")
        if value < 0:
            raise ValueError("factorial() requires a non-negative integer")
        if value > _MAX_FACTORIAL_INPUT:
            raise UnsafeExpressionError(
                f"factorial() input exceeds the limit of {_MAX_FACTORIAL_INPUT}"
            )

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
    
    def parse_calculation_request(self, query: str) -> dict[str, Any] | None:
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
        elif ('percent' in query_lower or '%' in query) and len(numbers) >= 2:
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
        except (ValueError, TypeError, ArithmeticError):
            # A query that merely looks like it contains an expression is not an error; fall
            # through to the caller's other handlers. Narrowed from a bare except, which also
            # swallowed KeyboardInterrupt.
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

