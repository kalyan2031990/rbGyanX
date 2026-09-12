"""
The expression calculator: correct for what it advertises, and closed to everything else.

Two problems, one cause. ``_evaluate_expression`` called ``eval`` on user input behind a
substring blocklist, and prepared the string for ``eval`` by textual substitution -- replacing
``'e'`` with ``str(math.e)`` before rewriting function names. So:

* ``exp(1)`` became ``2.718281828459045xp(1)`` and raised a syntax error;
* ``abs(-3)`` and ``pow(2,3)`` raised NameError, because they are builtins and the ``eval``
  globals set ``{"__builtins__": {}}``;
* the accompanying character check rejected nothing at all -- every branch of its loop ended in
  ``continue`` -- so the only real defence was a list of six substrings.

All three advertised-but-broken functions are pinned below, and the refusal tests are written as
payloads rather than as assertions about implementation, so they stay meaningful if the evaluator
is ever rewritten again.
"""

from __future__ import annotations

import math

import pytest

pytestmark = pytest.mark.unit

calculator_module = pytest.importorskip("ask_rbgyanx.calculator")
UnsafeExpressionError = calculator_module.UnsafeExpressionError


@pytest.fixture()
def calc():
    return calculator_module.create_calculator()


# ------------------------------------------- the advertised functions that failed


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("exp(1)", math.e),
        ("abs(-3)", 3.0),
        ("pow(2,3)", 8.0),
    ],
)
def test_previously_broken_advertised_functions(calc, expression: str, expected: float) -> None:
    """These three were named in the external review as advertised and non-functional."""
    result = calc.calculate(expression)
    assert result["success"], f"{expression} failed: {result['error']}"
    assert result["result"] == pytest.approx(expected)


def test_exp_is_not_corrupted_by_constant_substitution(calc) -> None:
    """The specific old bug: 'e' inside a function name was replaced with math.e."""
    assert calc.calculate("exp(0)")["result"] == pytest.approx(1.0)
    assert calc.calculate("exp(1)")["result"] == pytest.approx(math.e)
    # 'e' as a bare constant must still work -- the fix must not have removed it.
    assert calc.calculate("e")["result"] == pytest.approx(math.e)
    assert calc.calculate("ln(e)")["result"] == pytest.approx(1.0)


# ------------------------------------------------------------------ correctness


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2+2", 4.0),
        ("2*(3+4)", 14.0),
        ("10/4", 2.5),
        ("7%3", 1.0),
        ("7//2", 3.0),
        ("-3 + abs(-4)", 1.0),
        ("2^10", 1024.0),  # user-facing caret notation
        ("2**10", 1024.0),
        ("sqrt(16)", 4.0),
        ("log(100)", 2.0),  # base 10, matching the original intent
        ("log10(1000)", 3.0),
        ("log2(8)", 3.0),
        ("sin(0)", 0.0),
        ("cos(0)", 1.0),
        ("atan(0)", 0.0),
        ("factorial(5)", 120.0),
        ("floor(2.7)", 2.0),
        ("ceil(2.1)", 3.0),
        ("degrees(pi)", 180.0),
        ("radians(180)", math.pi),
        ("pi", math.pi),
        ("tau", math.tau),
    ],
)
def test_expressions_evaluate_correctly(calc, expression: str, expected: float) -> None:
    result = calc.calculate(expression)
    assert result["success"], f"{expression} failed: {result['error']}"
    assert result["result"] == pytest.approx(expected)


def test_result_contract_is_preserved(calc) -> None:
    """Callers read these four keys; enhanced_assistant depends on them."""
    ok = calc.calculate("1+1")
    assert set(ok) == {"success", "result", "error", "expression"}
    assert ok["expression"] == "1+1"
    assert ok["error"] is None

    bad = calc.calculate("nope(")
    assert bad["success"] is False
    assert bad["result"] is None
    assert bad["error"]


# ------------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    "payload",
    [
        "__import__('os').system('id')",
        "().__class__.__bases__[0].__subclasses__()",
        "math.__loader__.load_module",
        "math.pi",
        "open('/etc/passwd').read()",
        "globals()",
        "locals()",
        "quit()",
        "exit()",
        "(lambda: 1)()",
        "[x for x in (1,2)]",
        "{1: 2}",
        "1 if print('side effect') else 2",
        "'a' * 99999999",
        "sqrt.__self__",
        "True",
        "False",
        "None",
    ],
)
def test_unsafe_expressions_are_refused(calc, payload: str) -> None:
    """Nothing outside the allow-list evaluates, whatever it is spelled like."""
    result = calc.calculate(payload)
    assert result["success"] is False, f"{payload!r} was evaluated and returned {result['result']}"


def test_attribute_access_is_refused_by_shape_not_by_name(calc) -> None:
    """The defence is "no Attribute nodes", so it does not depend on guessing attribute names."""
    with pytest.raises(UnsafeExpressionError):
        calc._evaluate_expression("math.sqrt(4)")
    with pytest.raises(UnsafeExpressionError):
        calc._evaluate_expression("(1).bit_length()")


def test_a_blocked_substring_is_no_longer_the_defence(calc) -> None:
    """The old blocklist rejected any expression containing "eval" or "import" as a substring.

    That both over-rejected harmless text and under-rejected real payloads. An identifier that
    merely contains such a substring should now fail because it is an unknown name, not because
    of string matching -- and the message should say so.
    """
    result = calc.calculate("evaluate(2)")
    assert result["success"] is False
    assert "Unknown function" in result["error"]


# ---------------------------------------------------------------- resource caps


def test_huge_exponent_is_refused_rather_than_computed(calc) -> None:
    """2**10**10 would otherwise hang the interpreter building the integer."""
    result = calc.calculate("2**10**10")
    assert result["success"] is False
    assert "xponent" in result["error"]


def test_huge_factorial_is_refused(calc) -> None:
    result = calc.calculate("factorial(999999)")
    assert result["success"] is False
    assert "factorial" in result["error"]


def test_overlong_expression_is_refused(calc) -> None:
    result = calc.calculate("1+" * 400 + "1")
    assert result["success"] is False


@pytest.mark.parametrize("payload", ["", "   "])
def test_empty_expression_is_refused(calc, payload: str) -> None:
    assert calc.calculate(payload)["success"] is False


# ------------------------------------------------------- mathematical validity


def test_division_by_zero_is_an_error_not_a_crash(calc) -> None:
    result = calc.calculate("1/0")
    assert result["success"] is False
    assert "zero" in result["error"].lower()


def test_domain_errors_are_reported(calc) -> None:
    """sqrt(-1) is allowed syntax but invalid maths; it must not return a complex number."""
    result = calc.calculate("sqrt(-1)")
    assert result["success"] is False


def test_negative_factorial_is_reported(calc) -> None:
    assert calc.calculate("factorial(-1)")["success"] is False


# ------------------------------------------------------- the untouched helpers


def test_sigmoid_and_logistic_are_unchanged(calc) -> None:
    assert calc.calculate_sigmoid(0.0) == pytest.approx(0.5)
    assert calc.calculate_logistic(0.0) == pytest.approx(0.5)
    assert calc.calculate_sigmoid(100.0) > 0.99


def test_percentage_helper(calc) -> None:
    assert calc.calculate_percentage(25.0, 200.0) == pytest.approx(12.5)
    with pytest.raises(ValueError):
        calc.calculate_percentage(1.0, 0.0)


def test_parse_calculation_request_still_recognises_queries(calc) -> None:
    """enhanced_assistant routes through this; it must keep returning the same shape."""
    parsed = calc.parse_calculation_request("calculate 2 + 3")
    assert parsed is not None
    assert "operation" in parsed

    assert calc.parse_calculation_request("what is radiobiology") is None
