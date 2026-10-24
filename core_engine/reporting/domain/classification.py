"""Classification helpers for the canonical report model."""

from typing import Optional


def normalize_severity(value: Optional[str]) -> str:
    """Normalize tool-specific severities into a compact shared scale."""
    if value is None:
        return 'unknown'

    text = str(value).strip().lower()
    if not text:
        return 'unknown'

    mapping = {
        '1': 'critical',
        '2': 'high',
        '3': 'medium',
        '4': 'low',
        '5': 'low',
        '6': 'info',
        '7': 'info',
        '8': 'info',
        '9': 'info',
        'critical': 'critical',
        'fatal': 'critical',
        'high': 'high',
        'error': 'high',
        'medium': 'medium',
        'warning': 'medium',
        'warn': 'medium',
        'low': 'low',
        'minor': 'low',
        'info': 'info',
        'information': 'info',
    }
    return mapping.get(text, text)
