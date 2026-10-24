"""
Report upload orchestration.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.deployment.artifactory_deployer import (
    Deployer,
)
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )


class ReportUploader:
    """Uploads generated reports to Artifactory."""

    def __init__(self, config: 'ActionConfiguration'):
        self.config = config

    def upload_reports(self, generated_reports: Dict[str, str]):
        """Delegates zipping and upload of generated reports to the Deployer."""
        reporting_config = getattr(self.config, 'reporting_config', {})
        if not isinstance(reporting_config, dict):
            return

        upload_config = reporting_config.get('upload')
        if not isinstance(upload_config, dict):
            logger.debug('[ReportUploader] No upload configuration found in reporting.yml.')
            return

        if not upload_config.get('enabled', False) or not is_running_in_ci():
            logger.info('[ReportUploader] Report upload disabled or not running in CI, skipping.')
            return

        artifactory_alias = upload_config.get('artifactory')
        if not artifactory_alias:
            logger.warning(
                '[ReportUploader] No artifactory alias specified in upload config, skipping.'
            )
            return

        if not generated_reports:
            logger.info('[ReportUploader] No reports found to upload.')
            return

        # Create a temporary directory to stage the reports for zipping
        temp_dir = self.config.get_build_folder() / 'report_upload_stage'
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)

        for report_path_str in generated_reports.values():
            report_path = Path(report_path_str)
            if report_path.exists():
                shutil.copy(report_path, temp_dir / report_path.name)

        zip_name = (
            f'{self.config.get_action_name()}-{self.config.variant.get_variant_alias()}-reports'
        )

        deployer = Deployer(self.config.repo_root, self.config)

        deployment_name = 'unified_reports_zip_upload'
        deployments = {
            deployment_name: {
                'artifactory': artifactory_alias,
                'path': str(temp_dir),  # Folder to zip and upload
                'zip': True,
                'zip_name': zip_name,
                'properties': upload_config.get('properties', {}),
            }
        }

        logger.log_phase_header('UPLOADING REPORT ARCHIVE')
        try:
            deployer.deploy(deployments)
            logger.success('[ReportUploader] Report archive upload completed successfully.')
        except Exception as e:
            logger.error(f'[ReportUploader] Report archive upload failed: {e}')
        finally:
            logger.log_phase_header('UPLOADING REPORT ARCHIVE - END')
            # Clean up the staging directory after upload
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
