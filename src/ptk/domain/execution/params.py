"""Parameter resolution with precedence and sources (pure).

Precedence: command line > params file > declared environment variable > default.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..config.model import ParamSpec
from ..errors import PtkError
from ..suggest import did_you_mean


class ParamError(PtkError):
    pass


def resolve_params(
    specs: Mapping[str, ParamSpec],
    *,
    cli: Mapping[str, Any] | None = None,
    file_values: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    resolve_default: Callable[[str], Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    cli = dict(cli or {})
    file_values = dict(file_values or {})
    environ = environ or {}
    for source_name, given in (("command line", cli), ("params file", file_values)):
        for name in given:
            if name not in specs:
                raise ParamError(
                    f"unknown parameter '{name}' ({source_name}){did_you_mean(name, specs)}"
                    + ("" if specs else " - this action declares no parameters")
                )
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for name, spec in specs.items():
        try:
            if name in cli:
                values[name], sources[name] = spec.convert(cli[name]), "command line"
            elif name in file_values:
                values[name], sources[name] = (
                    spec.convert(file_values[name]),
                    "params file",
                )
            elif spec.env and spec.env in environ:
                values[name], sources[name] = (
                    spec.convert(environ[spec.env]),
                    f"env:{spec.env}",
                )
            elif spec.default is not None and spec.default_is_template:
                if resolve_default is None:
                    raise ParamError(
                        f"parameter '{name}': default {spec.default!r} "
                        "cannot be resolved here"
                    )
                values[name] = spec.convert(resolve_default(spec.default))
                sources[name] = f"default {spec.default}"
            elif spec.default is not None:
                values[name], sources[name] = spec.default, "default"
            elif spec.required:
                hint = f" or set {spec.env}" if spec.env else ""
                raise ParamError(
                    f"parameter '{name}' is required (--{name.replace('_', '-')} VALUE{hint})"
                )
            else:
                values[name], sources[name] = None, "unset"
        except ValueError as exc:
            raise ParamError(f"parameter '{name}': {exc}") from None
    return values, sources
