"""Debug-artifact upload orchestration for failed CI actions.

Extracted from the former ``ExecutionAction`` god-class (``execution_engine.py``).
The CI-gating/exception-swallowing boundary itself
(``run_upload_debug_artifacts_use_case``) remains in
``application/use_cases/execution.py``; this module provides the concrete
implementation callback it invokes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.deployment.artifactory_deployer import (
    Deployer,
)
from xc_ce_utils.core_engine.adapters.execution.debug_upload_adapter import (
    DebugUploadPlanAssemblyInput,
    DeployArtifactoryResolverFactoryInput,
    StandardDebugDeploymentsInput,
    assemble_debug_upload_plan,
    build_standard_debug_deployments,
    create_deploy_artifactory_resolver_adapter,
    log_debug_artifact_urls,
    resolve_deploy_artifactory_alias,
)

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )


class DebugArtifactUploader:
    """Uploads ``_log``/``_reports`` folders to Artifactory on CX failure."""

    def __init__(self, config: 'ActionConfiguration') -> None:
        self.config = config

    def find_deploy_artifactory(self) -> Optional[str]:
        """Find the first Artifactory alias referenced in deploy steps of this action.

        Scans PHASES (and nested steps) for the first ``deploy`` step that declares
        an ``artifactory`` key.  Falls back to the first configured Artifactory if
        no deploy step is found.

        Returns:
            Artifactory alias string, or None when no Artifactory is configured.
        """
        resolver = create_deploy_artifactory_resolver_adapter(
            payload=DeployArtifactoryResolverFactoryInput(
                get_action_config=self.config.get_action_config,
                get_artifactories=self.config.get_artifactories,
                log_debug=logger.debug,
            )
        )
        return resolve_deploy_artifactory_alias(resolver)

    def upload_impl(self, error: Exception) -> None:
        """Upload debug artifacts for a failed action (only when in CI).

        Args:
            error: The exception that caused the failure (used for log context only).
        """
        logger.log_phase_header('DEBUG ARTIFACT UPLOAD')
        logger.warning(
            f'Action failed ({type(error).__name__}) - uploading debug artifacts to Artifactory...'
        )

        artifactory_alias = self.find_deploy_artifactory()
        if not artifactory_alias:
            logger.warning(
                'No Artifactory alias found - skipping debug artifact upload'
            )
            return

        action_name = self.config.get_action_name()
        deployer = Deployer(self.config.repo_root, self.config)
        upload_plan = assemble_debug_upload_plan(
            payload=DebugUploadPlanAssemblyInput(
                config=self.config,
                action_name=action_name,
                artifactory_alias=artifactory_alias,
                commit_hash=deployer.commit_hash,
                upload_folder=str(deployer.upload_folder),
            )
        )
        deployments = build_standard_debug_deployments(
            payload=StandardDebugDeploymentsInput(
                artifactory_alias=artifactory_alias,
                action_name=action_name,
                upload_plan=upload_plan,
                logs_folder=self.config.get_logs_folder(),
                reports_folder=self.config.get_reports_folder(),
            ),
            log_debug=logger.debug,
        )

        if not deployments:
            logger.warning(
                'No log or report files found - skipping debug artifact upload'
            )
            return

        deployer.deploy(deployments)
        log_debug_artifact_urls(
            base_url=upload_plan.base_url,
            deployments=deployments,
            log_phase_header=logger.log_phase_header,
            log_info=logger.info,
        )
        logger.log_phase_header('DEBUG ARTIFACT UPLOAD - END')
