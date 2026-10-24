"""Quality, documentation, and code analysis steps.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.config.action_configuration import (
    ActionConfiguration,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, ExecutionStep
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci


class DocasCodeStepParams(BaseStepParams):
    allow_warnings: Optional[Any] = Field(default=None)
    builder: Optional[Any] = Field(default=None)
    docascode_config_folder: Optional[Any] = Field(default=None)
    exclude_directives: Optional[Any] = Field(default=None)
    meta_model_deviations: Optional[Any] = Field(default=None)
    open_docs: Optional[Any] = Field(default=None)
    pre_build_steps: Optional[Any] = Field(default=None)
    taco_results_dir: Optional[Any] = Field(default=None)
    taco_results_artifactory: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('docascode')
class DocasCodeStep(ExecutionStep):
    params_model = DocasCodeStepParams

    """Documentation generation build step using DocAsCode."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def execute(self) -> None:
        """Execute documentation generation."""
        try:
            # Lazy import to avoid loading Sphinx/matplotlib on every startup
            import xc_ce_utils.docascode.generate_docs as doc_generator

            fail_on_warnings = not self.config.get('allow_warnings', False)
            pre_build_steps = self.config.get('pre_build_steps')
            builder = self.config.get('builder', 'html')
            exclude_directives = self.config.get('exclude_directives', [])
            docascode_config_folder = self.config.get('docascode_config_folder')

            if not isinstance(exclude_directives, list):
                raise ExecutionStepError(
                    "Documentation generation requires 'exclude_directives' to be a list when provided"
                )

            if pre_build_steps is not None and not isinstance(pre_build_steps, list):
                raise ExecutionStepError(
                    "Documentation generation requires 'pre_build_steps' to be a list when provided"
                )

            reports_folder = self.context.get_build_folder() / (
                'needs' if builder == 'needs' else 'html'
            )

            taco_results_dir = self.config.get('taco_results_dir')
            taco_results = None
            if taco_results_dir:
                results_path = (Path(self.context.repo_root) / taco_results_dir).resolve()
                # read by the verdict_overlay extension
                os.environ['TACO_RESULTS_DIR'] = str(results_path)
                taco_results = self._taco_results_download(results_path)

            meta_model_deviations = self.config.get('meta_model_deviations')
            if meta_model_deviations:
                # read by the needs config generation (pmt_meta_model.meta_model_project_overrides)
                os.environ['META_MODEL_DEVIATIONS'] = str(
                    (Path(self.context.repo_root) / meta_model_deviations).resolve()
                )

            # Enable install=True to ensure Python requirements (including myst-parser) are installed
            # LOGS_FOLDER is read by the pre-build steps and Sphinx extensions (docascode.log_folder)
            action_logs_folder = os.environ.get('LOGS_FOLDER')
            os.environ['LOGS_FOLDER'] = str(self.get_step_log_folder().resolve())
            self._export_variant_config()
            try:
                if taco_results:
                    doc_generator.download_taco_results(**taco_results)
                doc_generator.generate_documentation(
                    build_folder=self.context.get_build_folder(),
                    reports_folder=reports_folder,
                    logs_folder=self.get_step_log_folder(),
                    clean=False,
                    install=False,
                    fail_on_warning=fail_on_warnings,
                    pre_build_steps=pre_build_steps,
                    builder=builder,
                    exclude_directives=exclude_directives,
                    docascode_config_folder=docascode_config_folder,
                )
            finally:
                if action_logs_folder is None:
                    os.environ.pop('LOGS_FOLDER', None)
                else:
                    os.environ['LOGS_FOLDER'] = action_logs_folder
        except ImportError as e:
            raise ExecutionStepError(f'Documentation generation requires docascode module: {e}')
        except Exception as e:
            raise ExecutionStepError(f'Documentation generation failed: {e}')

        if self.config.get('open_docs', False):
            self._open_docs(builder, reports_folder / 'index.html')

    def _export_variant_config(self) -> None:
        """Variant configuration and all variant aliases for the variant_handling extension."""
        variant = self.context.get_variant()
        if variant is None:
            return
        variant_config = {**variant.get_raw_dict(), **variant.get_variant_dict()}
        os.environ['XC_CE_UTILS_VARIANT_CONFIG'] = json.dumps(variant_config, default=str)
        variant_matrix = getattr(self.context, 'variant_matrix', None)
        aliases = list(
            getattr(variant_matrix, 'variants_by_alias', {}) or [variant.get_variant_alias()]
        )
        os.environ['XC_CE_UTILS_VARIANT_ALIASES'] = json.dumps(aliases)

    def _taco_results_download(self, results_path: Path) -> Optional[Dict[str, Any]]:
        """Download settings for the TACO results of the CI test jobs (taco_results_artifactory)."""
        alias = self.config.get('taco_results_artifactory')
        if not alias:
            return None
        if not is_running_in_ci():
            logger.info('TACO results download skipped outside CI; using the local results')
            return None
        artifactory = (self.context.artifactories or {}).get(alias)
        if not artifactory:
            raise ExecutionStepError(f"taco_results_artifactory: unknown artifactory '{alias}'")
        return {
            'results_dir': results_path,
            'artifactory_url': artifactory['url'],
            'repository': artifactory['repository'],
        }

    @staticmethod
    def _open_docs(builder: str, index_html: Path) -> None:
        """Open the generated HTML documentation in the default browser (local runs only)."""
        if builder != 'html':
            logger.warning(f"open_docs is only supported with builder 'html' (builder: {builder})")
            return
        if is_running_in_ci():
            return
        if not index_html.is_file():
            logger.warning(f'open_docs: {index_html} not found')
            return
        logger.progress(f'Opening documentation: {index_html.resolve()}')
        try:
            if os.name == 'nt':
                os.startfile(str(index_html.resolve()))
            else:
                import webbrowser  # noqa: PLC0415

                webbrowser.open(index_html.resolve().as_uri())
        except Exception as e:
            logger.warning(f'open_docs: could not open the browser: {e}')


class OssStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('oss')
class OssStep(ExecutionStep):
    params_model = OssStepParams

    """OSS scanning build step using FOSSID."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def execute(self) -> None:
        """Execute OSS scanning."""
        if not is_running_in_ci():
            logger.warning('OSS phase types only run under CX pipelines')
            return

        try:
            # Lazy import to avoid loading OSS tools on every startup
            import xc_ce_utils.oss.fossid_script_api as fossid_api
            import xc_ce_utils.oss.sw_source_extractor as oss_sw_extractor

            if not self.context.oss_config:
                raise ExecutionStepError('OSS configuration is missing.')

            oss_conf = self.context.oss_config
            oss_sw_extractor.extract_sources(
                oss_conf,
                f'{self.context.build_folder.resolve()!s}/sources_for_fossid',
            )

            # Running FOSSID scan
            self.context.reports_folder.mkdir(parents=True, exist_ok=True)
            fossid_api.create_and_run_scan(
                self.context.repo_name.upper(),
                f'{self.context.repo_name.upper()}_v{self.context.artifact_version}',
                [f'{self.context.build_folder.resolve()!s}/fossid.zip'],
                str(self.context.reports_folder.resolve()),
            )
        except ImportError as e:
            raise ExecutionStepError(f'OSS scanning requires oss modules: {e}')
        except Exception as e:
            raise ExecutionStepError(f'OSS scanning failed: {e}')


class QACStepParams(BaseStepParams):
    adapt_datastore: Optional[Any] = Field(default=None)
    artifactory_alias: Optional[Any] = Field(default=None)
    artifactory_repository: Optional[Any] = Field(default=None)
    artifactory_url: Optional[Any] = Field(default=None)
    baseline_repository_full_path: Optional[Any] = Field(default=None)
    create_baseline: Optional[Any] = Field(default=None)
    data_store_path: Optional[Any] = Field(default=None)
    datastore: Optional[Any] = Field(default=None)
    ref_branch: Optional[Any] = Field(default=None)
    report_formats: Optional[Any] = Field(default=None)
    sfa: Optional[Any] = Field(default=None)
    strict: Optional[Any] = Field(default=None)
    swq_sca_tools_version: Optional[Any] = Field(default=None)
    target: Optional[Any] = Field(default=None)
    violation_gate: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('qac')
class QACStep(ExecutionStep):
    params_model = QACStepParams

    """QAC/Helix QAC static code analysis build step."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate QAC configuration."""
        create_baseline = self.config.get('create_baseline', is_running_in_ci())
        sfa = self.config.get('sfa', False)

        if create_baseline or sfa:
            baseline_repository_full_path = self.config.get('baseline_repository_full_path', '')
            if not str(baseline_repository_full_path).strip():
                raise ExecutionStepError(
                    "QAC step requires 'baseline_repository_full_path' when "
                    'create_baseline=true or sfa=true'
                )

        violation_gate = self.config.get('violation_gate')
        if violation_gate is None:
            return

        if not isinstance(violation_gate, dict):
            raise ExecutionStepError("QAC step 'violation_gate' must be a dictionary when provided")

        enabled = violation_gate.get('enabled', True)
        fail_on_violation = violation_gate.get('fail_on_violation', True)
        levels = violation_gate.get('levels', None)
        thresholds = violation_gate.get('thresholds', {})

        if not isinstance(enabled, bool):
            raise ExecutionStepError("QAC step 'violation_gate.enabled' must be boolean")
        if not isinstance(fail_on_violation, bool):
            raise ExecutionStepError("QAC step 'violation_gate.fail_on_violation' must be boolean")

        if levels is not None:
            if not isinstance(levels, list) or not levels:
                raise ExecutionStepError(
                    "QAC step 'violation_gate.levels' must be a non-empty list"
                )

            normalized_levels = set()
            for level_raw in levels:
                try:
                    level = int(level_raw)
                except (TypeError, ValueError):
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.levels' must contain integers between 1 and 9"
                    )
                if level < 1 or level > 9:
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.levels' must contain integers between 1 and 9"
                    )
                normalized_levels.add(level)

            if not isinstance(thresholds, dict):
                raise ExecutionStepError(
                    "QAC step 'violation_gate.thresholds' must be a dictionary"
                )

            for key, value in thresholds.items():
                try:
                    key_level = int(key)
                except (TypeError, ValueError):
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.thresholds' keys must be integers between 1 and 9"
                    )

                if key_level not in normalized_levels:
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.thresholds' keys must be a subset of 'violation_gate.levels'"
                    )

                try:
                    threshold = int(value)
                except (TypeError, ValueError):
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.thresholds' values must be integers >= 0"
                    )

                if threshold < 0:
                    raise ExecutionStepError(
                        "QAC step 'violation_gate.thresholds' values must be integers >= 0"
                    )

    def execute(self) -> None:
        """Execute QAC analysis by delegating to helix_qac runtime."""
        try:
            # Lazy import keeps startup light for actions that do not use QAC.
            from xc_ce_utils.helix_qac.helix_qac import run_static_code_analysis

            create_baseline = self.config.get('create_baseline', is_running_in_ci())
            strict = self.config.get('strict', False)
            logger.info(f'create_baseline = {create_baseline}')
            logger.info(f'strict = {strict}')

            report_formats = self.config.get('report_formats', ['csv', 'html'])
            artifactory_url = ''
            artifactory_repository = ''

            if 'artifactory_alias' in self.config:
                artifactory_alias = self.config['artifactory_alias']
                if (
                    not hasattr(self.context, 'artifactories')
                    or artifactory_alias not in self.context.artifactories
                ):
                    raise RuntimeError(
                        f"Artifactory alias '{artifactory_alias}' not found in configuration"
                    )
                artifactory_config = self.context.artifactories[artifactory_alias]
                artifactory_url = artifactory_config['url']
                artifactory_repository = artifactory_config['repository']
            elif 'artifactory_url' in self.config:
                artifactory_url = self.config['artifactory_url']
                if 'artifactory_repository' in self.config:
                    artifactory_repository = self.config['artifactory_repository']

            logger.info('Running QAC analysis via xc_ce_utils.helix_qac runtime')
            datastore_path = self.config.get('data_store_path', self.config.get('datastore', ''))
            swq_sca_tools_version = self.config.get(
                'swq_sca_tools_version',
                self.config.get('swq-sca-tools_version', '1.12.1'),
            )
            run_static_code_analysis(
                sfa=self.config.get('sfa', False),
                create_baseline=create_baseline,
                strict=strict,
                adapt_datastore=self.config.get('adapt_datastore', False),
                data_store_path=datastore_path,
                datastore_target=self.config.get('target', ''),
                baseline_repository_full_path=self.config.get('baseline_repository_full_path', ''),
                source_branch=self.config.get('ref_branch', 'develop'),
                build_folder=self.get_step_build_folder().as_posix(),
                logs_folder=self.get_step_log_folder().as_posix(),
                reports_folder=self.get_step_reports_folder().as_posix(),
                artifactory_url=artifactory_url,
                artifactory_repository=artifactory_repository,
                report_formats=report_formats,
                swq_sca_tools_version=swq_sca_tools_version,
                violation_gate=self.config.get('violation_gate'),
            )

            logger.success('QAC analysis completed successfully')

        except Exception as e:
            raise RuntimeError(f'QAC analysis failed: {e}')


class SbomStepParams(BaseStepParams):
    config_file: Optional[Any] = Field(default=None)
    build_inputs_artifact_type: Optional[Any] = Field(default=None)
    build_inputs_artifactory: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('sbom')
class SbomStep(ExecutionStep):
    params_model = SbomStepParams

    """SBOM/SecBOM/CSI generation from CSI manifests, configured by one SBOM configuration file.

    The configuration file (``config_file``) holds all generator inputs; the step writes the outputs
    into its report folder and, on CI, downloads the build inputs the build job uploaded.
    """

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate SBOM step parameters."""
        if not self.config.get('config_file'):
            raise RuntimeConfigError("SBOM step requires 'config_file' (SBOM configuration file).")
        if self.config.get('build_inputs_artifact_type') and not self.config.get(
            'build_inputs_artifactory'
        ):
            raise RuntimeConfigError(
                "'build_inputs_artifact_type' requires 'build_inputs_artifactory' (artifactory alias)."
            )

    def _config_path(self) -> Path:
        path = Path(self.config['config_file'])
        return path if path.is_absolute() else Path(self.context.repo_root) / path

    def _download_build_inputs(self, sbom_config: Any) -> None:
        """On CI, fetch the build inputs the build job uploaded (build_inputs_artifact_type)."""
        from xc_ce_utils.sbom.build_inputs import download_build_inputs  # noqa: PLC0415

        artifact_type = self.config.get('build_inputs_artifact_type')
        if not artifact_type or not is_running_in_ci():
            return
        if sbom_config.discovery == 'arclbuild':
            target, clean = sbom_config.arclbuild_inputs, True
        elif sbom_config.discovery == 'compile_db' and sbom_config.compile_db:
            # may also hold other build outputs
            target, clean = sbom_config.compile_db.parent, False
        else:
            raise ExecutionStepError(
                "'build_inputs_artifact_type' requires discovery 'arclbuild' or 'compile_db' with 'compile_db' "
                'in the SBOM configuration.'
            )
        alias = self.config.get('build_inputs_artifactory')
        artifactory = (getattr(self.context, 'artifactories', None) or {}).get(alias)
        if not artifactory:
            raise ExecutionStepError(f"build_inputs_artifactory: unknown artifactory '{alias}'")
        download_build_inputs(
            target, artifactory['url'], artifactory['repository'], artifact_type, clean=clean
        )

    def execute(self) -> None:
        """Run the SBOM generator with the configuration file; outputs go to the step report folder."""
        try:
            # Lazy import to avoid loading jinja2/openpyxl on every startup
            from xc_ce_utils.sbom import sbom_generator  # noqa: PLC0415
            from xc_ce_utils.sbom.sbom_config import load_config, validate_config  # noqa: PLC0415
        except ImportError as e:
            raise ExecutionStepError(f'SBOM generation requires sbom modules: {e}') from e

        try:
            sbom_config = load_config(self._config_path(), base_dir=Path(self.context.repo_root))
            sbom_config.output_dir = self.get_step_reports_folder()
            # e.g. set by a CI workflow for short-lived develop SBOMs
            retention = os.environ.get('XC_CE_UTILS_SBOM_RETENTION_POLICY', '').strip()
            if retention:
                sbom_config.retention_policy = retention
            if not sbom_config.repo_versioning.variant:
                sbom_config.repo_versioning.variant = str(self.context.variant.get_variant_alias())
            sbom_config.tooling.requirements = dict(self.context.variant.get_tool_requires() or {})
            validate_config(sbom_config)

            self._download_build_inputs(sbom_config)
            sbom_generator.run(sbom_config)
            logger.success('SBOM generation completed successfully')
        except ExecutionStepError:
            raise
        except Exception as e:
            raise ExecutionStepError(f'SBOM generation failed: {e}') from e
