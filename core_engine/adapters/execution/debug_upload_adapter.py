"""Adapter for debug-artifact upload plan assembly and deploy-alias resolution.

Extracted from the former ``adapters/execution/infra.py`` monolith. Used by
:class:`~xc_ce_utils.core_engine.application.orchestration.debug_artifact_uploader.DebugArtifactUploader`
to assemble the CI debug-artifact upload plan and discover the Artifactory
alias to upload to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class DebugDeploymentPayload:
    """Payload descriptor used to build one debug deployment entry."""

    deployment_key: str
    folder: Path
    artifactory_alias: str
    action_name: str
    zip_name: str
    repository_full_path: str


@dataclass(frozen=True)
class DebugUploadPlan:
    """Stable values reused by debug artifact deployment flow."""

    zip_prefix: str
    debug_repository_path: str
    base_url: str


@dataclass(frozen=True)
class DebugUploadPlanInput:
    """Input payload for building a debug upload plan."""

    action_name: str
    variant_path: str
    version: str
    commit_hash: str
    upload_folder: str
    artifactory_url: str
    artifactory_repo: str


@dataclass(frozen=True)
class StandardDebugDeploymentsInput:
    """Input payload for standard debug log/report deployment assembly."""

    artifactory_alias: str
    action_name: str
    upload_plan: DebugUploadPlan
    logs_folder: Path
    reports_folder: Path


@dataclass(frozen=True)
class DebugUploadPlanAssemblyInput:
    """Input payload for assembling debug upload plan from runtime state."""

    config: Any
    action_name: str
    artifactory_alias: str
    commit_hash: str
    upload_folder: str


def create_debug_upload_plan(
    *,
    payload: DebugUploadPlanInput,
) -> DebugUploadPlan:
    """Build a debug upload plan from resolved deploy/context inputs."""
    zip_prefix = f'debug_{payload.action_name}_{payload.variant_path}_{payload.version}_{payload.commit_hash}'
    debug_repository_path = f'{payload.upload_folder}/debug'
    base_url = f"{payload.artifactory_url.rstrip('/')}/{payload.artifactory_repo}/{payload.upload_folder}/debug"
    return DebugUploadPlan(
        zip_prefix=zip_prefix,
        debug_repository_path=debug_repository_path,
        base_url=base_url,
    )


def resolve_debug_variant_path(config: Any) -> str:
    """Return sanitized variant path component used in debug artifacts."""
    if hasattr(config, 'variant'):
        return config.variant.get_variant_path().replace('/', '_')
    return 'unknown'


def assemble_debug_upload_plan(
    *,
    payload: DebugUploadPlanAssemblyInput,
) -> DebugUploadPlan:
    """Assemble debug upload plan from action configuration and deploy context."""
    variant_path = resolve_debug_variant_path(payload.config)
    artifactory_cfg = payload.config.get_artifactories()[
        payload.artifactory_alias
    ]
    return create_debug_upload_plan(
        payload=DebugUploadPlanInput(
            action_name=payload.action_name,
            variant_path=variant_path,
            version=str(payload.config.artifact_version or 'unknown'),
            commit_hash=payload.commit_hash,
            upload_folder=payload.upload_folder,
            artifactory_url=str(artifactory_cfg['url']),
            artifactory_repo=str(artifactory_cfg['repository']),
        ),
    )


def build_debug_deployments(
    *,
    payloads: list[DebugDeploymentPayload],
    log_debug: Callable[[str], None],
) -> dict[str, Any]:
    """Build deployment payload map for folders that contain files."""
    deployments: dict[str, Any] = {}
    for payload in payloads:
        deployment_key = str(payload.deployment_key).strip()
        folder = payload.folder
        if not (folder.exists() and any(folder.iterdir())):
            log_debug(
                f"Folder '{folder}' is empty or missing - skipping {deployment_key}"
            )
            continue

        deployments[deployment_key] = {
            'artifactory': str(payload.artifactory_alias).strip(),
            'zip': True,
            'zip_name': str(payload.zip_name).strip(),
            'path': str(folder),
            'repository_full_path': str(payload.repository_full_path).strip(),
            'properties': {
                'artifact': deployment_key,
                'action': str(payload.action_name).strip(),
            },
        }

    return deployments


def build_standard_debug_deployments(
    *,
    payload: StandardDebugDeploymentsInput,
    log_debug: Callable[[str], None],
) -> dict[str, Any]:
    """Build standard debug log/report deployment payloads."""
    payloads = [
        DebugDeploymentPayload(
            deployment_key='debug_logs',
            folder=payload.logs_folder,
            artifactory_alias=payload.artifactory_alias,
            action_name=payload.action_name,
            zip_name=f'{payload.upload_plan.zip_prefix}_logs',
            repository_full_path=payload.upload_plan.debug_repository_path,
        ),
        DebugDeploymentPayload(
            deployment_key='debug_reports',
            folder=payload.reports_folder,
            artifactory_alias=payload.artifactory_alias,
            action_name=payload.action_name,
            zip_name=f'{payload.upload_plan.zip_prefix}_reports',
            repository_full_path=payload.upload_plan.debug_repository_path,
        ),
    ]
    return build_debug_deployments(payloads=payloads, log_debug=log_debug)


def log_debug_artifact_urls(
    *,
    base_url: str,
    deployments: dict[str, Any],
    log_phase_header: Callable[[str], None],
    log_info: Callable[[str], None],
) -> None:
    """Log per-artifact debug URLs after successful deployment."""
    log_phase_header('DEBUG ARTIFACT URLS')
    log_info('Debug artifacts are available at:')
    for dep_name, dep in deployments.items():
        url = f"{base_url}/{dep['zip_name']}.zip"
        log_info(f'  [{dep_name}]  {url}')


@dataclass(frozen=True)
class DeployArtifactoryResolverAdapter:
    """Dependency boundary for deploy Artifactory alias discovery."""

    get_action_config: Callable[[], dict[str, Any]]
    scan_steps_for_deploy_artifactory: Callable[[dict[str, Any]], Optional[str]]
    fallback_deploy_artifactory_alias: Callable[[], Optional[str]]
    log_debug: Callable[[str], None]


@dataclass(frozen=True)
class DeployArtifactoryResolverFactoryInput:
    """Input payload for building deploy Artifactory resolver adapter."""

    get_action_config: Callable[[], dict[str, Any]]
    get_artifactories: Callable[[], dict[str, Any]]
    log_debug: Callable[[str], None]


def create_deploy_artifactory_resolver_adapter(
    *,
    payload: DeployArtifactoryResolverFactoryInput,
) -> DeployArtifactoryResolverAdapter:
    """Create deploy Artifactory resolver adapter from standard dependencies."""
    return DeployArtifactoryResolverAdapter(
        get_action_config=payload.get_action_config,
        scan_steps_for_deploy_artifactory=scan_steps_for_deploy_artifactory,
        fallback_deploy_artifactory_alias=lambda: fallback_first_artifactory_alias(
            payload.get_artifactories()
        ),
        log_debug=payload.log_debug,
    )


def resolve_deploy_artifactory_alias(
    adapter: DeployArtifactoryResolverAdapter,
) -> Optional[str]:
    """Resolve deploy alias from action structure with fallback behavior."""
    try:
        action_config = adapter.get_action_config()
        for source_steps in _deploy_search_sources(action_config):
            found = adapter.scan_steps_for_deploy_artifactory(source_steps)
            if found:
                return found

        return adapter.fallback_deploy_artifactory_alias()
    except Exception as error:
        adapter.log_debug(
            f'Could not determine debug upload Artifactory: {error}'
        )
    return None


def _deploy_search_sources(
    action_config: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Return ordered action sections used during deploy alias scan."""
    return tuple(
        action_config.get(source) or {}
        for source in ('PHASES', 'SETS', 'steps')
    )


def scan_steps_for_deploy_artifactory(
    steps: dict[str, Any],
) -> Optional[str]:
    """Scan nested step mappings and return first deploy Artifactory alias."""
    for step_cfg in (steps or {}).values():
        if not isinstance(step_cfg, dict):
            continue

        step_type = step_cfg.get('type') or step_cfg.get('step_type')
        if step_type == 'deploy':
            for dep in (step_cfg.get('deployments', {}) or {}).values():
                alias = str(dep.get('artifactory', '') or '').strip()
                if alias:
                    return alias.split(',')[0].strip()

        nested = step_cfg.get('steps')
        if isinstance(nested, dict):
            nested_match = scan_steps_for_deploy_artifactory(nested)
            if nested_match:
                return nested_match
    return None


def fallback_first_artifactory_alias(
    artifactories: dict[str, Any],
) -> Optional[str]:
    """Return first configured Artifactory alias when available."""
    if artifactories:
        return next(iter(artifactories))
    return None
