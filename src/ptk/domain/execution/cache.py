"""Stable cache keys and receipt matching, independent of storage."""

import hashlib
import json


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def input_key(configuration: str, dependencies: dict[str, str | None]) -> str | None:
    if not dependencies or not all(dependencies.values()):
        return None
    return fingerprint([configuration, dependencies])


def matches(record, key: str | None, outputs: str | None) -> bool:
    return bool(
        key
        and outputs
        and isinstance(record, dict)
        and record.get("version") == 1
        and record.get("inputs") == key
        and record.get("outputs") == outputs
        and isinstance(record.get("run_id"), str)
        and record["run_id"]
    )
