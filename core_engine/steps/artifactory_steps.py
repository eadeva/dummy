"""Artifactory download steps.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, ClassVar, Dict

from xc_ce_utils import logger
from xc_ce_utils.artifactory_utils.artifactory_downloader import (
    ArtifactoryDownloader,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepEvaluationStatus,
    StepExecutionStatus,
)


class ArtifactoryStepParams(BaseStepParams):
    pass
    model_config: ClassVar[dict] = {'extra': 'forbid'}


@StepRegistry.register(
    'art_downloader_setup',
    'art_download',
    'art_download_central',
)
class ArtifactoryStep(ExecutionStep):
    params_model = ArtifactoryStepParams

    """Unified Artifactory download step.

    Handles Artifactory downloader setup and artifact downloads. The
    concrete action is determined by the ``step_type`` field in the
    step configuration and dispatched internally.

    Config parameters (vary per action):
        id (str):               Identifier for the downloader in the shared
                                resource pool (art_downloader_setup).
        base_url (str):         Artifactory base URL (art_downloader_setup).
        repository (str):       Artifactory repository name (art_downloader_setup).
        download_path (str):    Default download path for all downloads using
                                this downloader (art_downloader_setup, optional).
        downloader_id (str):    Identifier of the downloader to use (art_download).
        type (str):             Download type (art_download).
        art_rel_path (str):     Relative path in Artifactory (art_download).
                                Optional when *properties* are provided;
                                defaults to repo root.
        download_path (str):    Local destination path (art_download, optional).
                                Falls back to the downloader's download_path,
                                then to the step build folder.
        download_id (str):      Identifier for the download (art_download).
        latest (bool):          Whether to download the latest version (art_download).
        properties (dict):      Artifactory property filters for search (art_download).
        output_variable (str):  Global variable name to store the result (art_download).
        central_path (bool):    Store under machine-wide C:\tools instead of
                                download_path (art_download, default false).
                                Always true for art_download_central.
        target_dir (str):       Subdirectory under the repository in the
                                central path (e.g. ``rb_artifacts``,
                                ``supplied``).  Optional, only used with
                                central_path or art_download_central.
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    @staticmethod
    def _build_metadata_env(download_id: str, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Build environment variables from artifact metadata.

        Returns a mapping of environment variable name -> value.
        """
        ignored_properties = {'retention.RetDate', 'retention.RetTimeStamp'}
        env_prefix = f'ARTIFACT_{download_id.upper().replace("-", "_")}'

        if not isinstance(metadata, dict):
            raise ValueError('Artifact metadata must be a mapping')

        url = metadata.get('download_url')
        if not url:
            raise ValueError('Artifact metadata download_url is missing or empty')

        props = metadata.get('properties') or {}
        result: Dict[str, str] = {}

        # add properties
        for k, v in props.items():
            if k in ignored_properties or k == 'rb_version':
                # rb_version handled specially below
                continue
            name = k.upper().replace('-', '_')
            value = '' if v is None else str(v)
            result[f'{env_prefix}_{name}'] = value

        # handle rb_version specially
        version = props.get('rb_version')
        if version is not None:
            version_str = str(version)
            result[f'{env_prefix}_VERSION'] = version_str
            version_match = re.search(r'(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)', version_str)
            if version_match:
                major, minor, bug = (
                    version_match.group(1),
                    version_match.group(2),
                    version_match.group(3),
                )
                result[f'{env_prefix}_VERSION_MAJOR'] = major
                result[f'{env_prefix}_VERSION_MINOR'] = minor
                result[f'{env_prefix}_VERSION_BUGFIX'] = bug

        # add URL
        result[f'{env_prefix}_URL'] = str(url)

        return result

    def _export_metadata_env(self, download_id: str, artifact_dir: str) -> None:
        """Read metadata file and export environment variables + append to env file."""
        meta_file = Path(artifact_dir) / '.artifact_meta.json'
        env_file = Path(self.context.build_folder) / 'xc-ce-utils.env'

        try:
            text = Path(meta_file).read_text(encoding='utf-8')
        except OSError as e:
            raise ValueError(f'{meta_file}: {e!s}') from e

        try:
            metadata = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f'{meta_file}: invalid JSON: {e!s}') from e

        if not isinstance(metadata, dict):
            raise ValueError(f'{meta_file}: root JSON is not an object')

        env_map = self._build_metadata_env(download_id, metadata)

        # ensure env file directory exists
        env_file.parent.mkdir(parents=True, exist_ok=True)

        with env_file.open('a', encoding='utf-8') as fh:
            for name, value in env_map.items():
                os.environ[name] = value
                fh.write(f'{name}={value}\n')
                logger.debug(
                    f'[{getattr(self, "name", "artifactory")}] exported metadata env: {name}={value}'
                )

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured Artifactory action."""
        try:
            self.pre_processing()

            step_type = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if step_type == 'art_downloader_setup':
                self._art_downloader_setup(params)
            elif step_type == 'art_download':
                self._art_download(params)
            elif step_type == 'art_download_central':
                self._art_download(params, force_central=True)
            else:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"step_type '{step_type}' not recognized!"
                )
                logger.critical(message)
                raise AbortError(message, phase=self.name)

        except RuntimeConfigError as e:
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Unknown exception: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _art_downloader_setup(self, params: Dict[str, Any]) -> None:
        """Set up an Artifactory downloader.

        Creates a new ``ArtifactoryDownloader`` instance and stores it in
        ``self.resources["artifactory_downloaders"]`` keyed by the
        configured ``id``. If a downloader with the same id already exists,
        checks whether the configuration matches: if it does, the existing
        instance is reused; if it differs, a ``ExecutionStepError`` is raised.
        """
        # ArtifactoryDownloader imported at module top-level

        try:
            dl_id = params['id']
            base_url = params['base_url']
            repository = params['repository']

            if 'artifactory_downloaders' not in self.resources:
                self.resources['artifactory_downloaders'] = {}

            if dl_id in self.resources['artifactory_downloaders']:
                existing = self.resources['artifactory_downloaders'][dl_id]
                existing_url = getattr(existing, 'base_url', None)
                existing_repo = getattr(existing, 'repository', None)

                if existing_url == base_url and existing_repo == repository:
                    logger.warning(
                        f"[{self.name}] Artifactory downloader '{dl_id}' already "
                        f'set up with same configuration. Reusing existing instance.'
                    )
                    self.add_to_report = False
                    return
                else:
                    message = (
                        f"Artifactory downloader '{dl_id}' already set up with "
                        f'different configuration (url: {existing_url} vs {base_url}, '
                        f'repo: {existing_repo} vs {repository}). '
                        f'Cannot overwrite with different config.'
                    )
                    self.result_string.append(message)
                    raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name)

            logger.info(
                f"[{self.name}] Setting up Artifactory downloader '{dl_id}' "
                f'(url={base_url}, repository={repository})'
            )

            downloader = ArtifactoryDownloader(base_url, repository)
            downloader.default_download_path = params.get('download_path')
            self.resources['artifactory_downloaders'][dl_id] = downloader

            self.result_string.append(f"Artifactory downloader '{dl_id}' set up successfully")

        except ExecutionStepError:
            raise
        except Exception as e:
            message = f"Artifactory downloader '{params.get('id', 'unknown')}' setup failed: {e!s}"
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f"[{self.name}] Artifactory downloader '{dl_id}' set up")

    def _art_download(self, params: Dict[str, Any], *, force_central: bool = False) -> None:
        """Download an artifact from Artifactory.

        Retrieves the downloader from the resource pool by ``downloader_id``
        and calls ``downloader.download``.  When *download_id* is provided
        (or defaults to the step name), a subfolder with that name is
        created under *download_path*.  Version freshness is tracked via
        a metadata file so that ``latest=True`` only re-downloads when a
        newer artifact exists in Artifactory.

        CLI overrides via ``--artifact`` flag:
            - ``local:<path>`` â€” skip download, set ARTIFACT_ env var to path
            - ``version:<ver>`` â€” inject version into property filter

        When *force_central* is ``True`` (used by ``art_download_central``)
        or the YAML parameter ``central_path`` is ``true``, the artifact
        is stored under the machine-wide tools directory (C:\\tools).

        The result is stored in ``self.global_variables[output_variable]``.
        """
        try:
            downloader_id = params['downloader_id']
            download_type = params.get('type', 'artifact')
            art_rel_path = params.get('art_rel_path', '')
            download_id = params.get('download_id', self.name)
            latest = params.get('latest', False)
            properties = params.get('properties')
            target_dir = params.get('target_dir')
            output_variable = params.get('output_variable')
            no_cache = bool(params.get('no-cache', params.get('no_cache', False)))

            # --- CLI override check via --artifact flag ---
            env_key = download_id.upper().replace('-', '_')
            artifact_source = os.environ.get(f'ARTIFACT_{env_key}_SOURCE')

            if artifact_source == 'local':
                local_path = os.environ.get(f'ARTIFACT_{env_key}', '')
                logger.info(f'[{self.name}] Using local artifact override: {local_path}')
                if output_variable:
                    self.global_variables[output_variable] = local_path
                self.result_string.append(f'Artifact override (local): {local_path}')
                self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
                self.test_status = StepEvaluationStatus.PASSED
                logger.success(f'[{self.name}] Local artifact set: {local_path}')
                return

            if artifact_source == 'remote':
                override_version = os.environ.get(f'ARTIFACT_{env_key}_VERSION')
                if override_version and properties is not None:
                    properties['rb_version'] = override_version
                    logger.info(f'[{self.name}] Artifact version override: {override_version}')

            # --- Standard download flow ---
            downloader = self.resources['artifactory_downloaders'][downloader_id]

            # Resolve download_path: step param ' downloader default ' step build folder
            download_path = (
                params.get('download_path')
                or getattr(downloader, 'default_download_path', None)
                or str(self.build_folder)
            )

            use_central = force_central or params.get('central_path', False)

            if use_central:
                logger.info(
                    f"[{self.name}] Downloading artifact '{download_id}' "
                    f'to central tools folder (type={download_type}, '
                    f'latest={latest}, no_cache={no_cache}, properties={properties})'
                )
            else:
                logger.info(
                    f"[{self.name}] Downloading artifact '{download_id}' "
                    f"to '{download_path}/{download_id}' (type={download_type}, "
                    f'latest={latest}, no_cache={no_cache}, properties={properties})'
                )

            result = downloader.download(
                download_type,
                art_rel_path,
                download_path,
                download_id,
                latest,
                properties,
                use_central_path=use_central,
                target_dir=target_dir,
                no_cache=no_cache,
            )

            # Set ARTIFACT_ env vars after successful download
            os.environ[f'ARTIFACT_{env_key}'] = str(result)
            logger.debug(f'  env: ARTIFACT_{env_key}={result}')

            # Export metadata-derived environment variables if metadata exists
            try:
                self._export_metadata_env(download_id, result)
            except Exception as e:
                # Convert metadata failures into an ExecutionStepError with artifact context
                raise ExecutionStepError(
                    f'[{self.name}] Artifact metadata export failed for {result}: {e!s}',
                    phase=self.name,
                ) from e

            if output_variable:
                self.global_variables[output_variable] = result

            self.result_string.append(f'Artifact downloaded successfully: {result}')

        except KeyError:
            message = (
                f"Artifactory downloader '{params.get('downloader_id', 'unknown')}' "
                f'not found in resources. Was art_downloader_setup executed?'
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name) from None
        except Exception as e:
            message = (
                f'Artifact download failed (path={params.get("art_rel_path", "unknown")}): {e!s}'
            )
            self.result_string.append(message)
            raise ExecutionStepError(f'[{self.name}] {message}', phase=self.name) from e

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        self.test_status = StepEvaluationStatus.PASSED
        logger.success(f'[{self.name}] Artifact downloaded: {result}')
