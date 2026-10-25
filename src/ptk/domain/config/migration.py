"""Conservative legacy conversion: unsupported structures fail, never disappear."""

from __future__ import annotations

import copy
import re
from typing import Any

from pydantic import ValidationError

from ..errors import PtkError
from .model import PtkConfig
from .rules import validate


def _rename(data: dict, old: str, new: str) -> None:
    if old in data:
        if new in data:
            raise PtkError(f"migration: both {old} and {new} are present")
        data[new] = data.pop(old)


def _templates(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"\$VAR\{([A-Za-z_][\w.]*)\}", r"${vars.\1}", value)
        if "$VAR{" in value:
            raise PtkError("migration: unsupported $VAR expression")
        return value
    if isinstance(value, list):
        return [_templates(v) for v in value]
    if isinstance(value, dict):
        return {k: _templates(v) for k, v in value.items()}
    return value


def _steps(raw: Any) -> list[dict]:
    if isinstance(raw, dict):
        raw = [{k: v} for k, v in raw.items()]
    if not isinstance(raw, list):
        raise PtkError("migration: steps/PHASES/SETS must be a mapping or list")
    result = []
    for item in raw:
        if not isinstance(item, dict) or len(item) != 1:
            raise PtkError("migration: each legacy step must have one name")
        name, body = next(iter(item.items()))
        if isinstance(body, (str, list)):
            body = {"run": body}
        if not isinstance(body, dict):
            raise PtkError(f"migration: step {name} must be a command or mapping")
        body = copy.deepcopy(body)
        for old, new in [
            ("PHASES", "steps"),
            ("SETS", "steps"),
            ("shell_run_command", "run"),
            ("custom_script", "run"),
            ("non_blocking", "background"),
        ]:
            _rename(body, old, new)
        if "game_stopper" in body:
            if "continue_on_error" in body or not isinstance(
                body["game_stopper"], bool
            ):
                raise PtkError(f"migration: ambiguous game_stopper in {name}")
            body["continue_on_error"] = not body.pop("game_stopper")
        conditions = []
        if "when" in body:
            conditions.append(body.pop("when"))
        for key, operator in [("only_variants", "in"), ("omit_variants", "not in")]:
            if key in body:
                names = body.pop(key)
                if isinstance(names, str):
                    names = [names]
                if not isinstance(names, list) or not all(
                    isinstance(n, str) for n in names
                ):
                    raise PtkError(f"migration: {key} must contain variant names")
                conditions.append(f"variant {operator} {names!r}")
        if "execute_if" in body:
            raise PtkError(
                "migration: translate execute_if manually to when (env, vars or feature scope is ambiguous)"
            )
        if conditions:
            if not all(isinstance(c, str) for c in conditions):
                raise PtkError("migration: conditions must be strings")
            body["when"] = " and ".join(f"({c})" for c in conditions)
        if "steps" in body:
            body["steps"] = _steps(body["steps"])
        result.append({name: body})
    return result


def migrate(raw: Any, name: str) -> dict:
    if not isinstance(raw, dict):
        raise PtkError("migration: configuration must be a mapping")
    data = copy.deepcopy(raw)
    _rename(data, "ACTIONS", "actions")
    _rename(data, "VARS", "vars")
    data.setdefault("project", {"name": name})
    data.setdefault("schema_version", 1)
    if not isinstance(data.get("actions"), dict):
        raise PtkError("migration: ACTIONS/actions must be a mapping")
    for action, body in data["actions"].items():
        if not isinstance(body, dict):
            raise PtkError(f"migration: action {action} must be a mapping")
        for key in ("PHASES", "SETS"):
            _rename(body, key, "steps")
        if "DEFAULT_PARAMETERS" in body:
            if "params" in body:
                raise PtkError(
                    "migration: both DEFAULT_PARAMETERS and params are present"
                )
            defaults = body.pop("DEFAULT_PARAMETERS")
            if not isinstance(defaults, dict):
                raise PtkError("migration: DEFAULT_PARAMETERS must be a mapping")
            kinds = {bool: "bool", int: "int", float: "float", list: "list", str: "str"}
            body["params"] = {}
            for key, value in defaults.items():
                if type(value) not in kinds:
                    raise PtkError(f"migration: unsupported default parameter {key}")
                body["params"][key] = {"type": kinds[type(value)], "default": value}
        body["steps"] = _steps(body.get("steps"))
    data = _templates(data)
    try:
        config = PtkConfig.model_validate(data)
    except ValidationError as exc:
        # Do not echo input values: legacy files may contain credentials.
        details = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
        )
        raise PtkError(f"migration requires manual changes: {details}") from None
    problems = validate(config)
    if problems:
        raise PtkError(
            "migration requires manual changes: "
            + "; ".join(
                f"{'.'.join(map(str, path))}: {message}" for path, message in problems
            )
        )
    return data
