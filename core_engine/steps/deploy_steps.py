"""Deployment and artifact management steps.
"""

import errno
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.config.action_configuration import (
    ActionConfiguration,
)
from xc_ce_utils.core_engine.domain.exceptions import (
    ConfigurationError,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, ExecutionStep
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

HTTP_POSITIVE_RESPONSE_CODES = [200, 201, 202, 204]
_UNC_PATH_MIN_PARTS = 2  # server + share
# A recursive delete of a shared per-release folder (accumulated files from
# several CI jobs) has been observed to keep it in STATUS_DELETE_PENDING for
# well over 5s - use exponential backoff with a generous ceiling instead of a
# short fixed delay.
_SMB_DELETE_PENDING_MAX_RETRIES = 10
_SMB_DELETE_PENDING_BASE_DELAY_SECONDS = 2.0
_SMB_DELETE_PENDING_MAX_DELAY_SECONDS = 20.0


class DeployStepParams(BaseStepParams):
    deployments: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('deploy')
class DeployStep(ExecutionStep):
    params_model = DeployStepParams

    """Deployment build step."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate deployment configuration."""
        if 'deployments' not in self.config:
            msg = "Deploy step requires 'deployments' configuration"
            raise ConfigurationError(msg)

    def execute(self) -> None:
        """Execute deployment."""
        if not is_running_in_ci():
            logger.warning(
                'Deployment phase is only executed in CI pipelines. Skipping deployment.'
            )
            return

        try:
            from xc_ce_utils.core_engine.adapters.deployment.artifactory_deployer import (  # noqa: PLC0415
                Deployer,
            )

            deployer = Deployer(
                repo_root=self.context.repo_root,
                build_conf=self.context,
                repo_name=self.context.repo_name,
                logs_folder=self.get_step_log_folder(),
                deploy_folder=self.get_step_deploy_folder(),
            )
            deployer.deploy(self.config['deployments'])
        except ImportError as e:
            msg = f'Deployment requires deployer module: {e}'
            raise ExecutionStepError(msg) from e
        except Exception as e:
            msg = f'Deployment failed: {e}'
            raise ExecutionStepError(msg) from e


class ArtifactoryCleanupStepParams(BaseStepParams):
    artifactory_alias: Optional[Any] = Field(default=None)
    removal_path: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('artifactory_cleanup')
class ArtifactoryCleanupStep(ExecutionStep):
    params_model = ArtifactoryCleanupStepParams

    """Artifactory cleanup step - removes artifacts from Artifactory repository."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate Artifactory cleanup configuration."""
        required_fields = ['artifactory_alias', 'removal_path']
        for field in required_fields:
            if field not in self.config:
                msg = f"Artifactory cleanup step requires '{field}' configuration"
                raise ConfigurationError(msg)

    def execute(self) -> None:
        """Execute Artifactory cleanup."""
        if not is_running_in_ci():
            logger.warning('Artifactory cleanup phase type only runs under CI/CX pipelines')
            return

        try:
            from xc_ce_utils.artifactory_utils.artifactory_cleaner import (  # noqa: PLC0415
                ArtifactoryCleaner,
            )

            artifactory_alias = self.config['artifactory_alias']
            removal_path = self.config['removal_path']

            # Get Artifactory configuration from context
            if (
                not hasattr(self.context, 'artifactories')
                or artifactory_alias not in self.context.artifactories
            ):
                msg = f"Artifactory alias '{artifactory_alias}' not found in configuration"
                raise ConfigurationError(msg)

            artifactory_config = self.context.artifactories[artifactory_alias]
            artifactory_url = artifactory_config['url']
            artifactory_repository = artifactory_config['repository']

            logger.info(f'Artifactory URL: {artifactory_url}')
            logger.info(f'Artifactory Repository: {artifactory_repository}')
            logger.info(f'Removal Path: {removal_path}')

            # Initialize cleaner
            cleaner = ArtifactoryCleaner(artifactory_url, artifactory_repository)

            try:
                # Perform deletion
                cleaner.delete_path(removal_path)
                logger.success(f'Successfully cleaned up: {removal_path}')
            finally:
                cleaner.close()

        except ImportError as e:
            msg = f'Artifactory cleanup requires artifactory_cleaner module: {e}'
            raise ExecutionStepError(msg) from e
        except Exception as e:
            msg = f'Artifactory cleanup failed: {e}'
            raise ExecutionStepError(msg) from e


class SplunkExportStepParams(BaseStepParams):
    code_metrics: Optional[Any] = Field(default=None)
    file_path: Optional[Any] = Field(default=None)
    file_paths: Optional[Any] = Field(default=None)
    release_level1: Optional[Any] = Field(default=None)
    release_level2: Optional[Any] = Field(default=None)
    remove_old_files: Optional[Any] = Field(default=None)
    shared_folder_rel_path: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('splunk_export')
class SplunkExportStep(ExecutionStep):
    params_model = SplunkExportStepParams

    """Copy an exported file into a shared Splunk network folder."""

    def __init__(self, name: str, config: Dict[str, Any], context: ActionConfiguration):
        """Initialize with context."""
        super().__init__(name, config, context)

    def validate(self) -> None:
        """Validate splunk export configuration."""
        if 'file_paths' not in self.config and 'file_path' not in self.config:
            msg = "Splunk export step requires 'file_paths' or 'file_path' configuration"
            raise ConfigurationError(msg)
        if 'shared_folder_rel_path' not in self.config:
            msg = "Splunk export step requires 'shared_folder_rel_path' configuration"
            raise ConfigurationError(msg)

    @staticmethod
    def _resolve_source_files(
        file_paths: Any,
        file_path: Any,
        repo_root: Path,
    ) -> list[Path]:
        """Resolve source files from either file_paths(list) or file_path(str)."""
        entries: list[str] = []

        if file_paths is not None:
            if not isinstance(file_paths, list) or not file_paths:
                msg = "splunk_export 'file_paths' must be a non-empty list"
                raise ConfigurationError(msg)
            entries.extend(str(item) for item in file_paths)

        if file_path is not None:
            if not isinstance(file_path, str) or not file_path.strip():
                msg = "splunk_export 'file_path' must be a non-empty string"
                raise ConfigurationError(msg)
            entries.append(file_path)

        if not entries:
            msg = "splunk_export requires at least one file input via 'file_paths' or 'file_path'"
            raise ConfigurationError(msg)

        source_files: list[Path] = []
        for file_entry in entries:
            source_file = Path(file_entry)
            if not source_file.is_absolute():
                source_file = repo_root / source_file

            if not source_file.exists() or not source_file.is_file():
                msg = f'splunk_export source file does not exist: {source_file}'
                raise ConfigurationError(msg)
            source_files.append(source_file)

        return source_files

    @staticmethod
    def _split_code_metrics_csv(source_file: Path) -> Dict[str, Any]:
        """Split a source CSV into Splunk code-metrics categories.

        Returns mapping of category suffix to DataFrame-like objects:
        ``MV``, ``SV``, ``CCV``, ``OV``.
        """
        try:
            import pandas as pd  # noqa: PLC0415, performance reasons: avoid pulling pandas in unless needed
        except ImportError as e:
            msg = f'code_metrics=true requires pandas: {e}'
            raise ExecutionStepError(msg) from e

        try:
            df = pd.read_csv(
                source_file,
                sep=None,
                engine='python',
                dtype=str,
                keep_default_na=False,
            )
        except Exception as e:
            msg = f'Failed to read code metrics CSV {source_file}: {e}'
            raise ExecutionStepError(msg) from e

        def _upper_col(name: str):
            if name not in df.columns:
                return pd.Series([''] * len(df), dtype='string')
            return df[name].fillna('').astype(str).str.upper()

        err_no = _upper_col('Error Number')
        metric = _upper_col('Metric')
        rule_group = _upper_col('Rule Group')
        rule_scope = _upper_col('Rule Scope')
        rule_text = _upper_col('Rule Text')
        msg_text = _upper_col('Message')

        is_metric = (
            err_no.str.startswith('METRIC-')
            | metric.str.contains('METRIC', regex=False)
            | rule_group.str.contains(r'\bXC-CE\s+METRICS\b|\bMETRICS?\b', regex=True)
        )

        is_cert = (
            err_no.str.contains('CERT', regex=False)
            | rule_group.str.contains('CERT', regex=False)
            | rule_scope.str.contains('CERT', regex=False)
            | rule_text.str.contains('CERT', regex=False)
            | msg_text.str.contains('CERT', regex=False)
        )

        is_style = (
            err_no.str.contains(r'MISRA|M3CM|M2CM|AUTOSAR', regex=True)
            | rule_group.str.contains(r'MISRA|M3CM|M2CM|AUTOSAR', regex=True)
            | rule_scope.str.contains(r'MISRA|M3CM|M2CM|AUTOSAR', regex=True)
        )

        # Priority order avoids double-assignment across categories.
        mv_mask = is_metric
        ccv_mask = (~mv_mask) & is_cert
        sv_mask = (~mv_mask) & (~ccv_mask) & is_style
        ov_mask = (~mv_mask) & (~ccv_mask) & (~sv_mask)

        return {
            'MV': df.loc[mv_mask].copy(),
            'SV': df.loc[sv_mask].copy(),
            'CCV': df.loc[ccv_mask].copy(),
            'OV': df.loc[ov_mask].copy(),
        }

    # -- SMB/UNC support ---------------------------------------------------
    # `shared_network_drive_path` is frequently a Windows UNC path
    # (\\server\share\...). Plain os/pathlib calls only reach it when the
    # process already has an OS-level session to that host (e.g. an
    # interactively logged-in Windows user) - inside a CI container there is
    # no such session, so those calls either fail or (on POSIX, where a
    # leading "//" collapses to a normal root-relative path) silently write
    # to the container's own local disk. Detect UNC paths and go through
    # ``smbclient`` with explicit, resolved credentials instead.

    @staticmethod
    def _is_unc_path(path_str: str) -> bool:
        """Return True if *path_str* is a Windows UNC path (\\\\ or // prefixed)."""
        return path_str.startswith('\\\\') or path_str.startswith('//')

    @staticmethod
    def _smb_split_unc(path_str: str) -> Tuple[str, list]:
        """Split a UNC path string into (``\\\\server\\share``, [remaining, parts])."""
        normalized = path_str.replace('/', '\\')
        parts = [p for p in normalized.split('\\') if p]
        if len(parts) < _UNC_PATH_MIN_PARTS:
            msg = f'Invalid UNC path (expected \\\\server\\share\\...): {path_str}'
            raise ExecutionStepError(msg)
        smb_base = '\\\\' + '\\'.join(parts[:2])
        return smb_base, parts[2:]

    @classmethod
    def _unc_server(cls, path_str: str) -> str:
        """Extract the server/host name from a UNC path string."""
        smb_base, _ = cls._smb_split_unc(path_str)
        return smb_base.lstrip('\\').split('\\')[0]

    @staticmethod
    def _unc_join(folder: str, filename: str) -> str:
        """Join a UNC folder path and a filename with a backslash."""
        return f'{folder.rstrip(chr(92))}\\{filename}'

    @classmethod
    def _unc_split_join(cls, base: str, relative_folder: Path) -> str:
        """Join a UNC base path string with a relative sub-path (multi-part Path)."""
        current = base.replace('/', '\\').rstrip('\\')
        for part in relative_folder.parts:
            current = f'{current}\\{part}'
        return current

    def _child_path(self, *, is_unc: bool, folder: str, filename: str) -> str:
        """Join *folder* and *filename*, going through UNC or pathlib as appropriate."""
        if is_unc:
            return self._unc_join(folder, filename)
        return str(Path(folder) / filename)

    @staticmethod
    def _qualify_smb_username(username: str) -> str:
        """Append the default AD domain (UPN suffix) if *username* has none.

        NTLM logon against a real Bosch fileserver rejects a bare technical
        user ID (e.g. 'tet6yh') with STATUS_LOGON_FAILURE even with the
        correct password - verified live against SI0VMC2745.de.bosch.com.
        A UPN-qualified form ('tet6yh@bosch.com') or a NetBIOS-qualified
        form ('DOMAIN\\tet6yh') is required.
        """
        if '@' in username or '\\' in username:
            return username
        return f'{username}@bosch.com'

    @classmethod
    def _ensure_smb_session(cls, server: str) -> None:
        """Register an authenticated SMB session for *server* (idempotent)."""
        try:
            import smbclient  # noqa: PLC0415, only needed for real network-share exports
        except ImportError as e:
            msg = (
                "splunk_export target is a UNC path but the 'smbprotocol' package "
                'is not installed'
            )
            raise ExecutionStepError(msg) from e

        from xc_ce_utils.auth import get_credentials_manager  # noqa: PLC0415

        username, password = get_credentials_manager().get_credentials(f'smb://{server}')
        if not username or not password:
            msg = f'Could not resolve SMB credentials for {server}'
            raise ExecutionStepError(msg)
        username = cls._qualify_smb_username(username)
        smbclient.register_session(server, username=username, password=password, port=445)

    def _smb_mkdir_segment(self, current_path: str) -> None:
        """Create one SMB directory segment, tolerating already-existing / delete-pending ones.

        A directory just removed by another client or a retention job stays in
        STATUS_DELETE_PENDING (0xC0000056) on the server until the deferred
        delete completes - any create for the same name fails until then
        (verified live against SI0VMC2745.de.bosch.com). This status is not in
        smbprotocol's SMBOSError known-error map, so it otherwise surfaces as
        an opaque 'Unknown NtStatus error' instead of being retried.
        """
        import smbclient  # noqa: PLC0415
        from smbprotocol.exceptions import SMBException  # noqa: PLC0415
        from smbprotocol.header import NtStatus  # noqa: PLC0415

        for attempt in range(1, _SMB_DELETE_PENDING_MAX_RETRIES + 1):
            try:
                smbclient.mkdir(current_path)
                return
            except SMBException as e:
                # smbclient maps STATUS_OBJECT_NAME_COLLISION to errno.EEXIST
                # (verified against a real share - the message text is
                # "[NtStatus 0xc0000035]", not the STATUS_* name).
                if getattr(e, 'errno', None) == errno.EEXIST:
                    return
                is_delete_pending = getattr(e, 'ntstatus', None) == NtStatus.STATUS_DELETE_PENDING
                if is_delete_pending and attempt < _SMB_DELETE_PENDING_MAX_RETRIES:
                    delay = min(
                        _SMB_DELETE_PENDING_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
                        _SMB_DELETE_PENDING_MAX_DELAY_SECONDS,
                    )
                    logger.warning(
                        f'{current_path} is pending deletion on the server '
                        f'(attempt {attempt}/{_SMB_DELETE_PENDING_MAX_RETRIES}), '
                        f'retrying in {delay:.0f}s...'
                    )
                    time.sleep(delay)
                    continue
                msg = f'Failed to create SMB directory {current_path}: {e}'
                raise ExecutionStepError(msg) from e

    def _smb_makedirs(self, path_str: str) -> None:
        """Create every segment of a UNC path, tolerating already-existing ones."""
        import smbclient  # noqa: PLC0415

        smb_base, rel_parts = self._smb_split_unc(path_str)
        current_path = smb_base
        for part in rel_parts:
            current_path = f'{current_path}\\{part}'
            self._smb_mkdir_segment(current_path)
        # Confirm the final path is actually listable instead of trusting mkdir's
        # return value, so masked failures don't get reported as success.
        list(smbclient.scandir(current_path))

    @staticmethod
    def _path_exists(*, is_unc: bool, path_str: str) -> bool:
        """Return True if *path_str* already exists, via SMB or the local filesystem."""
        if is_unc:
            import smbclient.path  # noqa: PLC0415

            return smbclient.path.exists(path_str)
        return Path(path_str).exists()

    @staticmethod
    def _remove_matching_files(*, is_unc: bool, folder: str, name_pattern: str) -> None:
        """Delete files directly under *folder* whose name matches *name_pattern* (glob)."""
        if is_unc:
            import fnmatch  # noqa: PLC0415

            import smbclient  # noqa: PLC0415

            for entry in smbclient.scandir(folder):
                if entry.is_file() and fnmatch.fnmatch(entry.name, name_pattern):
                    smbclient.remove(f'{folder}\\{entry.name}')
        else:
            for old_file in Path(folder).glob(name_pattern):
                if old_file.is_file():
                    old_file.unlink()

    @staticmethod
    @contextmanager
    def _open_for_write(
        *,
        is_unc: bool,
        path_str: str,
        mode: str,
        encoding: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> Iterator[Any]:
        """Open *path_str* for writing, transparently via SMB or the local filesystem."""
        kwargs: Dict[str, Any] = {}
        if encoding is not None:
            kwargs['encoding'] = encoding
        if newline is not None:
            kwargs['newline'] = newline
        if is_unc:
            import smbclient  # noqa: PLC0415

            with smbclient.open_file(path_str, mode=mode, **kwargs) as handle:
                yield handle
        else:
            with open(path_str, mode=mode, **kwargs) as handle:
                yield handle

    def _release_level(self, key: str, default: str) -> str:
        """Return the configured metadata release level, or *default* when not set."""
        value = self.config.get(key)
        if value is None or not str(value).strip():
            return default
        return str(value).strip()

    def execute(self) -> None:
        """Execute file export to the configured shared network drive."""
        try:
            splunk_config = getattr(self.context, 'splunk_config', None)
            if not isinstance(splunk_config, dict):
                msg = 'SPLUNK configuration is missing or invalid in main configuration'
                raise ConfigurationError(msg)

            shared_network_drive_path = splunk_config.get('shared_network_drive_path', '')
            if (
                not isinstance(shared_network_drive_path, str)
                or not shared_network_drive_path.strip()
            ):
                msg = 'SPLUNK.shared_network_drive_path is missing or empty'
                raise ConfigurationError(msg)
            shared_network_drive_path = shared_network_drive_path.strip()

            code_metrics = bool(self.config.get('code_metrics', False))
            source_files = self._resolve_source_files(
                self.config.get('file_paths'),
                self.config.get('file_path'),
                self.context.repo_root,
            )

            relative_folder = Path(str(self.config['shared_folder_rel_path']).strip())
            if str(relative_folder) in {'', '.'}:
                msg = 'shared_folder_rel_path must not be empty'
                raise ConfigurationError(msg)
            if relative_folder.is_absolute():
                msg = 'shared_folder_rel_path must be a relative path'
                raise ConfigurationError(msg)
            if '..' in relative_folder.parts:
                msg = "shared_folder_rel_path must not contain parent path traversal ('..')"
                raise ConfigurationError(msg)

            is_unc = self._is_unc_path(shared_network_drive_path)
            if is_unc:
                target_folder = self._unc_split_join(shared_network_drive_path, relative_folder)
                self._ensure_smb_session(self._unc_server(shared_network_drive_path))
                self._smb_makedirs(target_folder)
            else:
                target_folder_path = Path(shared_network_drive_path) / relative_folder
                target_folder_path.mkdir(parents=True, exist_ok=True)
                target_folder = str(target_folder_path)

            project_name = str(
                os.environ.get(
                    'PROJECT_NAME',
                    getattr(self.context, 'repo_name', self.context.repo_root.name),
                )
            ).strip()
            variant_alias = str(os.environ.get('XC_CE_UTILS_VARIANT_ALIAS', '')).strip()
            remove_old_files = bool(self.config.get('remove_old_files', False))

            export_timestamp = time.strftime('%Y-%m-%d_%H-%M', time.localtime())
            copied_files: list[str] = []
            if code_metrics:
                if len(source_files) != 1:
                    msg = (
                        'splunk_export with code_metrics=true requires exactly '
                        "one input file via 'file_path' or one element in "
                        "'file_paths'"
                    )
                    raise ConfigurationError(msg)
                source_file = source_files[0]
                if source_file.suffix.lower() != '.csv':
                    msg = 'splunk_export with code_metrics=true requires a .csv input file'
                    raise ConfigurationError(msg)

                split_frames = self._split_code_metrics_csv(source_file)
                for suffix, frame in split_frames.items():
                    if remove_old_files:
                        self._remove_matching_files(
                            is_unc=is_unc,
                            folder=target_folder,
                            name_pattern=f'{project_name}_{suffix}_*.csv',
                        )
                    destination_file = self._child_path(
                        is_unc=is_unc,
                        folder=target_folder,
                        filename=f'{project_name}_{suffix}_{export_timestamp}.csv',
                    )
                    with self._open_for_write(
                        is_unc=is_unc,
                        path_str=destination_file,
                        mode='w',
                        encoding='utf-8',
                        newline='',
                    ) as handle:
                        frame.to_csv(handle, index=False)
                    copied_files.append(destination_file)
            else:
                for source_file in source_files:
                    if remove_old_files:
                        self._remove_matching_files(
                            is_unc=is_unc,
                            folder=target_folder,
                            name_pattern=f'{project_name}_{source_file.stem}_*{source_file.suffix}',
                        )
                    destination_file_name = (
                        f'{project_name}_{source_file.stem}_{export_timestamp}{source_file.suffix}'
                    )
                    destination_file = self._child_path(
                        is_unc=is_unc, folder=target_folder, filename=destination_file_name
                    )
                    with (
                        open(source_file, 'rb') as src,
                        self._open_for_write(
                            is_unc=is_unc, path_str=destination_file, mode='wb'
                        ) as dst,
                    ):
                        shutil.copyfileobj(src, dst)
                    copied_files.append(destination_file)

            metadata_file_name = f'{project_name}_MD.json'
            metadata_path = self._child_path(
                is_unc=is_unc, folder=target_folder, filename=metadata_file_name
            )

            # The shared per-release folder is written to by several independent
            # actions (build/unit-tests/sca/docs) and may be re-run after a
            # partial failure - never delete/recreate it or its metadata file;
            # only create the folder if missing (above) and skip the metadata
            # write entirely if a prior run already deposited it.
            if self._path_exists(is_unc=is_unc, path_str=metadata_path):
                logger.info(
                    f'Splunk export metadata file already exists, skipping: {metadata_path}'
                )
            else:
                metadata_payload = {
                    'MetaDataVersion': '1',
                    'TimeStamp': int(time.time()),
                    'ReleaseLevel1': {
                        'Name': self._release_level('release_level1', variant_alias),
                        'Default': True,
                    },
                    'ReleaseLevel2': {
                        'Name': self._release_level(
                            'release_level2', str(os.environ.get('RB_VERSION', ''))
                        ),
                        'Default': True,
                    },
                }
                with self._open_for_write(
                    is_unc=is_unc, path_str=metadata_path, mode='w', encoding='utf-8'
                ) as handle:
                    handle.write(json.dumps(metadata_payload, indent=4) + '\n')
                logger.success(f'Splunk export generated metadata file: {metadata_path}')

            logger.info(f'Splunk export target folder: {target_folder}')
            for copied_file in copied_files:
                logger.success(f'Splunk export copied file to: {copied_file}')

        except Exception as e:
            msg = f'Splunk export failed: {e}'
            raise ExecutionStepError(msg) from e
