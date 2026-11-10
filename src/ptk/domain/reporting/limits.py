"""Size limit of imported report evidence; larger inputs are omitted with a warning."""

MAX_BYTES = 100 * 1024 * 1024
_MARKER = "exceeds the 100 MiB report import limit"


def exceeded(what: str, consequence: str = "section omitted") -> str:
    return f"{what} {_MARKER}; {consequence}"


def is_limit(message: str) -> bool:
    return _MARKER in message
