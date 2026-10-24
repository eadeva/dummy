"""Parsing helpers for repeatable / CSV-style CLI options.

These were extracted from ``DynamicCLIGenerator`` because they are pure
string-to-value transforms with no dependency on the generator's state.

Used by the ``-bo / --build-option``, ``-mp / --misc-param`` and
``-art / --artifact`` flags, all of which accept either repeated values
(``-bo a=1 -bo b=2``) or a single comma-separated payload
(``-bo "a=1,b=2"``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


def parse_multiple_options(options_tuple: Tuple[str, ...]) -> Dict[str, Any]:
    """Merge values from a repeatable Click option into a single dict.

    Supports both repeated flags and comma-separated pairs:
        -bo name1=value1 -bo name2=value2
        -bo "name1=value1,name2=value2"
    """
    merged: Dict[str, Any] = {}
    for entry in options_tuple:
        merged.update(parse_options_parameter(entry))
    return merged


def parse_options_parameter(options_string: str) -> Dict[str, Any]:
    """Parse a single ``name=value[,name=value...]`` string into a dict.

    A bare ``name`` (no ``=``) is treated as a boolean flag set to True.
    """
    parsed_options: Dict[str, Any] = {}

    if not options_string:
        return parsed_options

    for pair in options_string.split(','):
        pair = pair.strip()
        if '=' not in pair:
            name = pair
            converted_value: Any = True
        else:
            name, value = pair.split('=', 1)
            value = value.strip()
            converted_value = convert_option_value(value)

        name = name.strip()
        parsed_options[name] = converted_value

        logger.debug(
            'Parsed option: %s = %s (type: %s)',
            name,
            converted_value,
            type(converted_value).__name__,
        )

    return parsed_options


def convert_option_value(value: str) -> Any:
    """Coerce a string CLI value to bool / int / float / str."""
    if value.lower() in ('true', 'yes', '1', 'on'):
        return True
    if value.lower() in ('false', 'no', '0', 'off'):
        return False

    try:
        if '.' not in value:
            return int(value)
        return float(value)
    except ValueError:
        pass

    return value


__all__ = [
    'convert_option_value',
    'parse_multiple_options',
    'parse_options_parameter',
]
