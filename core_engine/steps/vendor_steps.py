"""Vendor-specific tool steps: Vector DaVinci, EB Tresos, IBM DNG.
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import ConfigLoader
from xc_ce_utils.core_engine.config.action_configuration import (
    ActionConfiguration,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    ConfigurationError,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, ExecutionStep


class VectorDavinciConfigureStepParams(BaseStepParams):
    dpa: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('vector_davinci_configure')
class VectorDavinciConfigureStep(ExecutionStep):
    params_model = VectorDavinciConfigureStepParams

    """Vector DaVinci configuration step - opens GUI for manual configuration."""

    def execute(self) -> None:
        """Execute Vector DaVinci configurator GUI."""
        try:
            from xc_ce_utils.vector_generation.vector_davinci_handler import (
                VectorDaVinciHandler,
            )

            # Get variant from context
            variant = self.context.variant
            if not variant:
                raise ExecutionStepError('Variant information not available in build context')

            # Get configuration file from variant
            vector_config = variant.get_vector_conf()
            if not vector_config:
                raise ConfigurationError(
                    'vector_config not configured for this variant. '
                    "Add 'vector_config' section to variant configuration."
                )

            vector_conf_dump = self.context.build_folder / 'vector_conf.yml'
            vector_conf_dump.parent.mkdir(parents=True, exist_ok=True)

            with vector_conf_dump.open('w') as f:
                yaml.dump(vector_config, f, default_flow_style=False)
            config_loader = ConfigLoader()
            vector_config = config_loader.load_file(vector_conf_dump)
            with vector_conf_dump.open('w') as f:
                yaml.dump(vector_config, f, default_flow_style=False)

            # Get parameters from phase config
            dpa_file = self.config.get(
                'dpa', vector_config.get('dpa')
            )  # Optional override from phase config

            # Get artifact_vector from environment
            artifact_vector = os.environ.get('ARTIFACT_VECTOR', None)
            if not artifact_vector:
                raise ConfigurationError('ARTIFACT_VECTOR environment variable not set')
            artifact_vector = Path(artifact_vector)

            logger.progress('Initializing Vector DaVinci configurator...')
            logger.info(f'DPA file: {dpa_file}')
            logger.info(f'SIP path: {artifact_vector}')

            generation_folder = vector_config.get('generation_folder', None)
            if not generation_folder:
                raise ConfigurationError(
                    'generation_folder not specified in vector_config - required for configurator step'
                )

            # Create handler
            handler = VectorDaVinciHandler(
                dpa_file=Path(dpa_file) if dpa_file else None,
                artifact_vector=artifact_vector,
                variant=variant.get_variant_alias(),
                vector_config=vector_config,
                build_folder=self.get_step_build_folder(),
                log_folder=self.get_step_log_folder(),
                generation_folder=generation_folder,
            )

            if os.environ.get('XC_CE_UTILS_VERBOSE', 'false').lower() == 'true':
                verbose = True
            else:
                verbose = False

            # Launch GUI
            handler.configure(verbose=verbose)
            logger.success('Vector DaVinci configurator launched successfully')

        except ImportError as e:
            raise ExecutionStepError(f'Vector DaVinci handler not available: {e}')
        except Exception as e:
            raise ExecutionStepError(f'Vector DaVinci configure failed: {e}')


class VectorDavinciGenerateStepParams(BaseStepParams):
    mcal_modules: Optional[Any] = Field(default=None)
    module_to_generate: Optional[Any] = Field(default=None)
    modules_to_exclude: Optional[Any] = Field(default=None)
    only_mcal: Optional[Any] = Field(default=None)
    skip_mcal: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('vector_davinci_generate')
class VectorDavinciGenerateStep(ExecutionStep):
    params_model = VectorDavinciGenerateStepParams

    """Vector DaVinci code generation step."""

    def execute(self) -> None:
        """Execute Vector DaVinci code generation."""
        try:
            from xc_ce_utils.vector_generation.vector_davinci_handler import (
                VectorDaVinciHandler,
            )

            # Get variant from context
            variant = self.context.variant
            if not variant:
                raise ExecutionStepError('Variant information not available in build context')

            # Get configuration file from variant
            vector_config = variant.get_vector_conf()
            if not vector_config:
                raise ConfigurationError(
                    'vector_config not configured for this variant. '
                    "Add 'vector_config' section to variant configuration."
                )

            vector_conf_dump = self.context.build_folder / 'vector_conf.yml'
            vector_conf_dump.parent.mkdir(parents=True, exist_ok=True)

            with vector_conf_dump.open('w') as f:
                yaml.dump(vector_config, f, default_flow_style=False)
            config_loader = ConfigLoader()
            vector_config = config_loader.load_file(vector_conf_dump)
            with vector_conf_dump.open('w') as f:
                yaml.dump(vector_config, f, default_flow_style=False)

            # Get parameters from phase config
            dpa_file = vector_config.get('dpa')  # Optional override
            mcal_modules = self.config.get('mcal_modules')  # Optional: comma-separated list
            skip_mcal = self.config.get('skip_mcal', False)
            only_mcal = self.config.get('only_mcal', False)

            # Debug: Log final parameter values before calling handler.generate()
            logger.debug('[TRACE] Final parameters before handler.generate():')
            logger.debug(f'[TRACE]   skip_mcal={skip_mcal} (type: {type(skip_mcal)})')
            logger.debug(f'[TRACE]   only_mcal={only_mcal} (type: {type(only_mcal)})')

            # Validate mutually exclusive parameters
            if only_mcal and skip_mcal:
                raise ConfigurationError(
                    "Phase configuration error: 'only_mcal' and 'skip_mcal' are mutually exclusive. "
                    'Set only one to true, not both.'
                )

            # Get force_gen from context
            force_gen = self.context.force_gen

            # Get artifact_vector from environment
            artifact_vector = os.environ.get('ARTIFACT_VECTOR')
            if not artifact_vector:
                raise ConfigurationError('ARTIFACT_VECTOR environment variable not set')
            artifact_vector = Path(artifact_vector)

            # Parse module list if provided
            module_to_generate = self.config.get('module_to_generate', [])
            modules_to_exclude = self.config.get('modules_to_exclude', [])
            if mcal_modules and skip_mcal:
                modules_to_exclude.extend([m.strip() for m in mcal_modules.split(',')])

            logger.progress('Initializing Vector DaVinci code generation...')
            logger.info(f'DPA file: {dpa_file}')
            logger.info(f'SIP path: {artifact_vector}')
            logger.info(
                f"Modules to generate: {module_to_generate if module_to_generate else 'All'}"
            )
            logger.info(
                f"Modules to exclude: {modules_to_exclude if modules_to_exclude else 'None'}"
            )
            logger.info(f'Force generation: {force_gen}')
            logger.info(f'Skip MCAL: {skip_mcal}')
            logger.info(f'Only MCAL: {only_mcal}')

            generation_folder = vector_config.get('generation_folder', None)
            if not generation_folder:
                raise ConfigurationError(
                    'generation_folder not specified in vector_config - required for configurator step'
                )

            # Create handler
            handler = VectorDaVinciHandler(
                dpa_file=Path(dpa_file) if dpa_file else None,
                artifact_vector=artifact_vector,
                variant=variant.get_variant_alias(),
                vector_config=vector_config,
                build_folder=self.get_step_build_folder(),
                log_folder=self.get_step_log_folder(),
                generation_folder=generation_folder,
            )

            # Execute generation
            logger.info(
                f'Generating Vector DaVinci code (force_gen={force_gen}, skip_mcal={skip_mcal}, only_mcal={only_mcal})...'
            )
            success = handler.generate(
                module_list=module_to_generate,
                modules_to_exclude=modules_to_exclude,
                force_gen=force_gen,
                skip_mcal=skip_mcal,
                only_mcal=only_mcal,
                log_folder=self.get_step_log_folder(),
            )

            if not success:
                raise ExecutionStepError('Vector DaVinci code generation failed')

            logger.success('Vector DaVinci code generation completed successfully')

        except ImportError as e:
            raise ExecutionStepError(f'Vector DaVinci handler not available: {e}')
        except Exception as e:
            raise ExecutionStepError(f'Vector DaVinci generate failed: {e}')


class TresosConfigureStepParams(BaseStepParams):
    project: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('tresos_configure')
class TresosConfigureStep(ExecutionStep):
    params_model = TresosConfigureStepParams

    """TRESOS configuration step - removes project, reimports it, and opens GUI."""

    def execute(self) -> None:
        """Execute TRESOS configurator GUI."""
        if platform.system() != 'Windows':
            raise ExecutionStepError('TRESOS configure is only supported on Windows')
        try:
            from xc_ce_utils.tresos_generator.tresos_generator import (
                TRESOSProjectManager,
            )

            # Get variant from context
            variant = self.context.variant
            if not variant:
                raise ExecutionStepError('Variant information not available in build context')

            # Get TRESOS configuration from variant
            tresos_conf = variant.get_tresos_conf()
            if not tresos_conf:
                raise ConfigurationError(
                    'tresos_conf not configured for this variant. '
                    "Add 'tresos_conf' section to variant configuration."
                )

            tresos_conf_dump = self.context.build_folder / 'tresos_conf.yml'
            tresos_conf_dump.parent.mkdir(parents=True, exist_ok=True)

            with tresos_conf_dump.open('w') as f:
                yaml.dump(tresos_conf, f, default_flow_style=False)

            config_loader = ConfigLoader()
            tresos_conf = config_loader.load_file(tresos_conf_dump)
            with tresos_conf_dump.open('w') as f:
                yaml.dump(tresos_conf, f, default_flow_style=False)

            # Resolve workspace path
            cwd = Path.cwd()
            tresos_workspace_str = tresos_conf.get('workspace')
            if not tresos_workspace_str:
                raise ConfigurationError("'workspace' not found in TRESOS configuration")

            tresos_workspace = Path(tresos_workspace_str)
            if not tresos_workspace.is_absolute():
                tresos_workspace = cwd / tresos_workspace

            if not tresos_workspace.exists():
                raise FileNotFoundError(f'TRESOS workspace not found: {tresos_workspace}')

            # Get executable_path for TRESOS command
            executable_path = tresos_conf.get('executable_path') or tresos_conf.get('tresos_cmd')
            if not executable_path:
                raise ConfigurationError(
                    "'executable_path' or 'tresos_cmd' not found in TRESOS configuration"
                )

            executable_path = Path(executable_path)
            if not executable_path.exists():
                raise FileNotFoundError(f'TRESOS command not found: {executable_path}')

            # Resolve project paths
            projects = {}
            for name, project_path_str in tresos_conf.get('projects', {}).items():
                project_path = Path(project_path_str)
                if not project_path.is_absolute():
                    project_path = cwd / project_path
                projects[name] = project_path.resolve()

            if not projects:
                raise ConfigurationError("'projects' not found or empty in TRESOS configuration")

            # Build configuration dictionary for TRESOSProjectManager
            manager_conf = {
                'workspace': tresos_workspace,
                'projects': projects,
                'executable_path': str(executable_path),
            }

            # Determine project filter from step config
            projects_filter = None
            project_to_configure = self.config.get('project')
            if project_to_configure:
                projects_filter = [project_to_configure]

            # Create manager and delegate to configure
            manager = TRESOSProjectManager(manager_conf)
            manager.configure(projects_filter=projects_filter, launch_gui=True)

        except ImportError as e:
            raise ExecutionStepError(f'TRESOS generator not available: {e}')
        except subprocess.TimeoutExpired as e:
            raise ExecutionStepError(f'TRESOS command timeout: {e}')
        except Exception as e:
            raise ExecutionStepError(f'TRESOS configure failed: {e}')


class TresosGenerateStepParams(BaseStepParams):
    projects: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('tresos_generate')
class TresosGenerateStep(ExecutionStep):
    params_model = TresosGenerateStepParams

    """TRESOS code generation step.

    Generates code for TRESOS (EB TRESOS) projects using the TRESOSProjectManager.
    Configuration is loaded from the variant's TRESOS configuration.

    Configuration Parameters:
        projects (optional): Comma-separated list of project names to generate.
                           If not specified, all projects from variant config are processed.

    Variant Configuration Required:
        - workspace: Path to TRESOS workspace
        - projects: Dictionary of project names to paths
        - executable_path or tresos_cmd: Path to TRESOS executable

    Features:
        - File locking to prevent parallel TRESOS runs
        - Hash-based change detection (skips unchanged projects)
        - Force generation support via context.force_gen
        - Project filtering for selective generation

    Raises:
        ConfigurationError: If required configuration is missing or invalid
        FileNotFoundError: If workspace or executable not found
        ExecutionStepError: If TRESOS generation fails
    """

    def execute(self) -> None:
        """Execute TRESOS code generation.

        Loads TRESOS configuration from variant, validates paths, and generates
        code for all or specified TRESOS projects using file locking to prevent
        parallel execution conflicts.
        """
        try:
            import yaml

            from xc_ce_utils import logger as rb_logger

            # Get variant from context
            variant = self.context.variant
            if not variant:
                raise ExecutionStepError('Variant information not available in build context')

            # Get configuration file from variant
            tresos_conf = variant.get_tresos_conf()
            if not tresos_conf:
                raise ConfigurationError(
                    'tresos_conf not configured for this variant. '
                    "Add 'tresos_conf' section to variant configuration."
                )

            tresos_conf_dump = self.context.build_folder / 'tresos_conf.yml'
            tresos_conf_dump.parent.mkdir(parents=True, exist_ok=True)

            with tresos_conf_dump.open('w') as f:
                yaml.dump(tresos_conf, f, default_flow_style=False)

            config_loader = ConfigLoader()
            tresos_conf = config_loader.load_file(tresos_conf_dump)
            with tresos_conf_dump.open('w') as f:
                yaml.dump(tresos_conf, f, default_flow_style=False)

            # Verify tresos_cmd exists in config
            tresos_workspace_str = tresos_conf.get('workspace')
            # Resolve paths relative to current working directory
            cwd = Path.cwd()
            tresos_workspace = Path(tresos_workspace_str)
            if not tresos_workspace.is_absolute():
                tresos_workspace = cwd / tresos_workspace

            if not tresos_workspace.exists():
                raise ConfigurationError("'workspace' not found in TRESOS configuration")

            # Get executable_path for TRESOS command and locking
            executable_path = tresos_conf.get('executable_path') or tresos_conf.get('tresos_cmd')
            if not executable_path:
                raise ConfigurationError(
                    "'executable_path' or 'tresos_cmd' not found in TRESOS configuration"
                )

            # Verify it exists on filesystem
            if not Path(executable_path).exists():
                raise FileNotFoundError(f'TRESOS command not found: {executable_path}')

            # Get optional project filter from phase config
            projects_filter = self.config.get('projects')
            if projects_filter and isinstance(projects_filter, str):
                projects_filter = [p.strip() for p in projects_filter.split(',')]

            # Get force_gen from context
            force_gen = self.context.force_gen

            projects = {}
            for name, project_path_str in tresos_conf.get('projects', {}).items():
                project_path = Path(project_path_str)
                if not project_path.is_absolute():
                    project_path = cwd / project_path
                projects[name] = project_path.resolve()

            # Build configuration dictionary for TRESOSProjectManager
            tresos_conf = {
                'workspace': tresos_workspace,
                'projects': projects,
                'executable_path': executable_path,
            }

            # Import and use TRESOSProjectManager class directly
            from xc_ce_utils.tresos_generator.tresos_generator import (
                TRESOSProjectManager,
            )

            rb_logger.info('Starting TRESOS code generation...')
            manager = TRESOSProjectManager(tresos_conf)
            successful, failed = manager.generate(
                force_gen=force_gen, projects_filter=projects_filter
            )

            if failed > 0:
                raise ExecutionStepError(
                    f'TRESOS generation failed for {failed} project(s). '
                    f'{successful} successful, {failed} failed.'
                )

            rb_logger.success(
                f'TRESOS code generation completed successfully: {successful} projects'
            )

        except ImportError as e:
            raise ExecutionStepError(f'TRESOS generator not available: {e}')
        except Exception as e:
            raise ExecutionStepError(f'TRESOS generate failed: {e}')


class DngExportStepParams(BaseStepParams):
    config_path: Optional[Any] = Field(default=None)
    log_dir: Optional[Any] = Field(default=None)
    reports_dir: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('dng_export')
class DngExportStep(ExecutionStep):
    params_model = DngExportStepParams

    """DNG artifact export build step.

    Runs the ALM exporter to fetch artifacts from IBM ELM DNG and
    generate RST / CSV / Excel output for Sphinx documentation.
    """

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def execute(self) -> None:
        """Execute DNG export."""
        try:
            # Lazy import to avoid loading DNG/elmclient on every startup
            from xc_ce_utils.alm_utils.alm_exporter import DNGExporter

            config_path = self.config.get('config_path')
            if config_path:
                config_path = Path(config_path)
                if not config_path.is_absolute():
                    config_path = self.context.repo_root / config_path

            log_dir = self.config.get('log_dir', self.get_step_log_folder())
            reports_dir = Path(self.config.get('reports_dir', self.get_step_reports_folder()))

            exporter = DNGExporter.from_config_path(
                config_path=config_path,
                project_root=self.context.repo_root,
            )

            if exporter.config is None:
                raise ExecutionStepError(
                    "No DNG config found. Provide 'config_path' in the phase "
                    'config or place config/dng/dng_conf.yml in the repo root.'
                )

            success, fails, failed_names = exporter.run_all_exports(
                log_dir=log_dir if log_dir else None,
                reports_dir=reports_dir,
            )

            logger.info(f'DNG export complete: {success} succeeded, {fails} failed')

            if fails > 0:
                raise ExecutionStepError(
                    f"DNG export failed for {fails} export(s): " f"{', '.join(failed_names)}"
                )

        except ImportError as e:
            raise ExecutionStepError(f'DNG export requires alm_utils module: {e}')
        except ExecutionStepError:
            raise
        except Exception as e:
            raise ExecutionStepError(f'DNG export failed: {e}')
