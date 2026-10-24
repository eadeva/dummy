"""``${...}`` substitution (pure).

Syntax::

    ${env:NAME}  ${env:NAME:-default}       environment of the run
    ${vars.build_dir}                       configuration vars (may reference others)
    ${params.jobs}                          action parameters
    ${vh.variant} ${vh.features.X} ${vh.components.camera} ${vh.data.toolchain}
    ${project.root} ${project.name}
    ${run.build_dir} ${run.bin_dir} ${run.log_dir} ${run.reports_dir} ${run.id} ${run.action} ${run.step}
    ${secret:artifactory.token}             only in step env values
    $${literal}                             escapes -> ${literal}

A string that is exactly one reference keeps the value's type (``${params.jobs}``
-> 8); otherwise values are inserted as text (booleans as ``true``/``false``).
Unknown names are errors with suggestions.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..suggest import did_you_mean

_TOKEN = re.compile(r"\$\$\{|\$\{([^{}]*)\}")
NAMESPACES = ("env", "vars", "params", "vh", "project", "run", "secret")


class SubstitutionError(ValueError):
    pass


def references(text: str) -> list[str]:
    return [m.group(1).strip() for m in _TOKEN.finditer(text) if m.group(0) != "$${"]


def iter_references(value: Any):
    """All references inside nested strings / lists / dicts."""
    if isinstance(value, str):
        yield from references(value)
    elif isinstance(value, list):
        for item in value:
            yield from iter_references(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_references(item)


def to_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(to_text(v) for v in value)
    return str(value)


def substitute(value: Any, resolve: Callable[[str], Any]) -> Any:
    if isinstance(value, str):
        match = _TOKEN.fullmatch(value)
        if match and match.group(0) != "$${":
            return resolve(match.group(1).strip())

        def repl(m: re.Match[str]) -> str:
            return "${" if m.group(0) == "$${" else to_text(resolve(m.group(1).strip()))

        return _TOKEN.sub(repl, value)
    if isinstance(value, list):
        return [substitute(v, resolve) for v in value]
    if isinstance(value, dict):
        return {k: substitute(v, resolve) for k, v in value.items()}
    return value


def split_reference(ref: str) -> tuple[str, str]:
    """('env', 'HOME:-x') / ('vars', 'a.b') ..."""
    for ns in ("env", "secret"):
        if ref.startswith(ns + ":"):
            return ns, ref[len(ns) + 1 :]
    head, _, rest = ref.partition(".")
    return head, rest


@dataclass
class Scope:
    """Resolves references against namespaces; vars are resolved lazily."""

    env: Mapping[str, str] = field(default_factory=dict)
    vars: Mapping[str, Any] = field(default_factory=dict)
    namespaces: dict[str, Any] = field(default_factory=dict)  # params, vh, project, run
    secret: Callable[[str], str] | None = None
    _resolving: list[str] = field(default_factory=list)
    _cache: dict[str, Any] = field(default_factory=dict)

    def resolve(self, ref: str) -> Any:
        ns, rest = split_reference(ref)
        if ns == "env":
            name, sep, default = rest.partition(":-")
            if name in self.env:
                return self.env[name]
            if sep:
                return default
            raise SubstitutionError(
                f"environment variable '{name}' is not set (use ${{env:{name}:-default}})"
            )
        if ns == "secret":
            if self.secret is None:
                raise SubstitutionError(f"secret '{rest}' is not available here")
            return self.secret(rest)
        if ns == "vars":
            return self._var(rest)
        if ns not in self.namespaces:
            known = [
                n
                for n in NAMESPACES
                if n in self.namespaces or n in ("env", "vars", "secret")
            ]
            raise SubstitutionError(
                f"unknown namespace '{ns}' in ${{{ref}}}{did_you_mean(ns, known)}"
            )
        return _walk(self.namespaces[ns], rest, ns, ref)

    def _var(self, dotted: str) -> Any:
        name, _, rest = dotted.partition(".")
        if name not in self.vars:
            raise SubstitutionError(
                f"unknown variable 'vars.{name}'{did_you_mean(name, self.vars)}"
            )
        if name not in self._cache:
            if name in self._resolving:
                raise SubstitutionError(
                    f"circular vars reference: {' -> '.join(self._resolving + [name])}"
                )
            self._resolving.append(name)
            try:
                self._cache[name] = substitute(self.vars[name], self.resolve)
            finally:
                self._resolving.pop()
        value = self._cache[name]
        return _walk(value, rest, f"vars.{name}", dotted) if rest else value

    def __call__(self, value: Any) -> Any:
        return substitute(value, self.resolve)


def _walk(value: Any, dotted: str, prefix: str, ref: str) -> Any:
    if not dotted:
        return value
    current = value
    walked = prefix
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            options = list(current) if isinstance(current, Mapping) else []
            raise SubstitutionError(
                f"unknown name '{walked}.{part}' in ${{{ref}}}{did_you_mean(part, options)}"
            )
        current = current[part]
        walked += f".{part}"
    return current
