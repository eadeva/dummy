"""Reusable comparison utility for step verification."""

import operator

from xc_ce_utils import logger

OPERATORS = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
}


def _parse_numeric(value: str):
    """Try to parse a string as a number.

    Handles hex (0x...), octal (0o...), binary (0b...) via int(x, 0),
    then falls back to float for decimal/scientific notation.

    Returns the numeric value or None if not parseable.
    """
    s = value.strip()
    # Try int with auto-base detection (handles 0x, 0o, 0b prefixes)
    try:
        return int(s, 0)
    except (ValueError, TypeError):
        pass
    # Try float for decimal/scientific notation
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_for_comparison(value: str) -> str:
    """Normalize a string for comparison.

    Strips outer whitespace and normalizes tuple-like strings by removing
    spaces around commas, e.g. '(2, 70, 0)' -> '(2,70,0)'.
    """
    s = value.strip()
    if s.startswith('(') and s.endswith(')'):
        inner = s[1:-1]
        parts = [p.strip() for p in inner.split(',')]
        return '(' + ','.join(parts) + ')'
    return s


def evaluate_comparison(actual: str, expected: str, op: str = '==') -> bool:
    """
    Compare actual vs expected using the given operator.

    Attempts numeric comparison first (supports hex 0x, octal 0o, binary 0b,
    decimal, and float); falls back to string comparison for == and !=.
    For tuple-like strings e.g. '(2, 70, 0)', normalizes whitespace before
    comparison. Returns False for ordering operators on non-numeric values.

    Args:
        actual: The actual value (as string).
        expected: The expected value (as string).
        op: One of "==", "!=", ">", ">=", "<", "<=".

    Returns:
        True if the comparison holds, False otherwise.

    Raises:
        ValueError: If the operator is not supported.
    """
    if op not in OPERATORS:
        raise ValueError(
            f"Unsupported operator '{op}'. Supported: {list(OPERATORS.keys())}"
        )

    comparator = OPERATORS[op]

    # Try numeric comparison first
    actual_num = _parse_numeric(actual)
    expected_num = _parse_numeric(expected)

    if actual_num is not None and expected_num is not None:
        result = comparator(actual_num, expected_num)
        logger.debug(
            f'Numeric comparison: {actual_num} {op} {expected_num} = {result}'
        )
        return result

    # String fallback only for equality operators
    if op in ('==', '!='):
        actual_norm = _normalize_for_comparison(str(actual))
        expected_norm = _normalize_for_comparison(str(expected))
        result = comparator(actual_norm, expected_norm)
        logger.debug(
            f"String comparison: '{actual_norm}' {op} '{expected_norm}' = {result}"
        )
        return result

    logger.warning(
        f"Cannot apply ordering operator '{op}' to non-numeric values: "
        f"actual='{actual}', expected='{expected}'"
    )
    return False
