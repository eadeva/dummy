"""Adapter for platform tool-requires installation orchestration.

Extracted from the former ``adapters/execution/infra.py`` monolith. Defines
the dependency boundary used by
:class:`~xc_ce_utils.core_engine.application.orchestration.tool_requires_installer.ToolRequiresInstaller`
and the ``tool_requires`` filtering helpers it relies on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolRequiresInstallationAdapter:
    """Dependency boundary for tool-require installation orchestration."""

    resolve_install_prerequisites: Callable[[], tuple[Any, dict[str, Any]]]
    log_runtime_context: Callable[[Any], None]
    install_platform_tool_requires: Callable[
        [list[dict[str, Any]], dict[str, Any], Any],
        None,
    ]
    install_artifact_requires: Callable[
        [list[dict[str, Any]], dict[str, Any]],
        None,
    ]
    write_tool_requirements_file: Callable[[list[dict[str, Any]]], None]


def run_tool_requires_installation(
    adapter: ToolRequiresInstallationAdapter,
) -> None:
    """Execute tool-require installation through adapter boundary."""
    tool_reqs: list[dict[str, Any]] = []
    context, variant_requires = adapter.resolve_install_prerequisites()

    adapter.log_runtime_context(context)
    adapter.install_platform_tool_requires(
        tool_reqs,
        variant_requires,
        context,
    )
    adapter.install_artifact_requires(tool_reqs, variant_requires)
    adapter.write_tool_requirements_file(tool_reqs)


def is_matching_tool_require(
    *,
    tool_require: dict[str, Any],
    type_: str,
    action_name: str,
) -> bool:
    """Return True when one tool requirement applies to current action/type."""
    return (
        'type' in tool_require
        and tool_require['type'] == type_
        and action_name in tool_require['needed_for']
    )


def filter_tool_requires_by_type(
    *,
    requires: dict[str, Any],
    type_: str,
    action_name: str,
) -> dict[str, Any]:
    """Filter tool requirements for a given type and action name."""
    return {
        tool_name: tool_require
        for tool_name, tool_require in requires.items()
        if is_matching_tool_require(
            tool_require=tool_require,
            type_=type_,
            action_name=action_name,
        )
    }
