"""Runtime facade for loading and validating core-engine configuration.

This module is intentionally application-layer only. It exposes a stable
ingress boundary that adapters (CLI today, GUI later) can consume without
depending on dynamic_cli internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from xc_ce_utils import logger

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.config_models import MainConfig


LoadEntryConfig = Callable[[Path], dict[str, Any]]
ResolveEntryConfPath = Callable[[Path, Path], Path | None]


@dataclass(frozen=True)
class RuntimeConfigEnvelope:
    """Carrier for raw and canonical runtime configuration views."""

    conf_file: Path
    raw_main_config: dict[str, Any]
    canonical_main_config: MainConfig | None


@dataclass(frozen=True)
class RuntimeConfigDependencies:
    """Injected callables used to load/resolve runtime configuration."""

    load_entry_config: LoadEntryConfig
    resolve_entry_conf_path: ResolveEntryConfPath


def _resolve_runtime_dependencies(
    dependency_kwargs: dict[str, Any],
) -> RuntimeConfigDependencies:
    """Resolve runtime config dependency callables.

    Supports both the new ``dependencies=RuntimeConfigDependencies(...)``
    style and legacy keyword arguments ``load_entry_config=...`` and
    ``resolve_entry_conf_path=...``.
    """

    provided_dependencies = dependency_kwargs.get('dependencies')
    if isinstance(provided_dependencies, RuntimeConfigDependencies):
        return provided_dependencies

    load_entry_config = dependency_kwargs.get('load_entry_config')
    resolve_entry_conf_path = dependency_kwargs.get('resolve_entry_conf_path')
    if callable(load_entry_config) and callable(resolve_entry_conf_path):
        return RuntimeConfigDependencies(
            load_entry_config=load_entry_config,
            resolve_entry_conf_path=resolve_entry_conf_path,
        )

    from xc_ce_utils.conf_file_loader.conf_file_loader import (  # noqa: PLC0415
        load_entry_config as default_load_entry_config,
    )
    from xc_ce_utils.conf_file_loader.conf_file_loader import (  # noqa: PLC0415
        resolve_entry_conf_path as default_resolve_entry_conf_path,
    )

    return RuntimeConfigDependencies(
        load_entry_config=default_load_entry_config,
        resolve_entry_conf_path=default_resolve_entry_conf_path,
    )


def _validate_main_config(
    raw_main_config: dict[str, Any],
    conf_file: Path,
    configuration_error_cls: type[Exception],
) -> MainConfig:
    """Validate main config against the canonical pydantic model.

    Lazy imports are intentional: for metadata-only requests (for example,
    ``--help`` and ``--version``) we skip schema hydration to avoid loading the
    full model graph and keep startup latency low.
    """

    from pydantic import ValidationError  # noqa: PLC0415

    from xc_ce_utils.core_engine.config.config_models import (  # noqa: PLC0415
        MainConfig,
    )

    try:
        return MainConfig.model_validate(raw_main_config)
    except ValidationError as validation_error:
        message = (
            f'Invalid main configuration ({conf_file}): {validation_error}'
        )
        raise configuration_error_cls(message) from validation_error


def load_runtime_config(
    repo_root: Path,
    cwd: Path,
    configuration_error_cls: type[Exception],
    *,
    validate_schema: bool,
    **dependency_kwargs: Any,
) -> RuntimeConfigEnvelope:
    """Load and optionally validate resolved main configuration.

    Args:
        repo_root: Active repository root.
        cwd: Working directory used for entry-config discovery.
        configuration_error_cls: Exception type raised for config errors.
        validate_schema: Enable canonical pydantic validation.
        dependency_kwargs: Optional dependency injection kwargs.
    """

    dependencies = _resolve_runtime_dependencies(dependency_kwargs)

    conf_file = dependencies.resolve_entry_conf_path(repo_root, cwd=cwd)
    if conf_file is None:
        message = 'Main configuration file not found'
        raise configuration_error_cls(message)

    raw_main_config = dependencies.load_entry_config(repo_root)
    canonical_main_config: MainConfig | None = None

    if validate_schema:
        canonical_main_config = _validate_main_config(
            raw_main_config,
            conf_file,
            configuration_error_cls,
        )
    else:
        logger.trace(
            'Schema validation deferred: metadata-only request detected'
        )

    return RuntimeConfigEnvelope(
        conf_file=conf_file,
        raw_main_config=raw_main_config,
        canonical_main_config=canonical_main_config,
    )
