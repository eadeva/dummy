"""Platform tool-requires installation orchestration.

Extracted from the former ``ExecutionAction`` god-class (``execution_engine.py``).
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.execution.tool_installer_adapter import (
    ToolRequiresInstallationAdapter,
    filter_tool_requires_by_type,
    run_tool_requires_installation,
)
from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError
from xc_ce_utils.global_modules.aux_helper import (
    load_environment_variables_from_env_file,
)
from xc_ce_utils.global_modules.rb_file_lock import FileLock
from xc_ce_utils.tool_installers.artifactory_installer import (
    ArtifactoryInstaller,
)

if platform.system() == 'Windows':
    from xc_ce_utils.tool_installers import choco_installer
    from xc_ce_utils.tool_installers import toolbase_installer as tb_installer
elif platform.system() == 'Linux':
    from xc_ce_utils.tool_installers import (
        linux_package_installer as linux_installer,
    )

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )
    from xc_ce_utils.core_engine.domain.runtime_context import RuntimeContext


class ToolRequiresInstaller:
    """Installs platform-specific ``tool_requires`` for the active variant."""

    def __init__(
        self,
        config: 'ActionConfiguration',
        runtime_context: 'RuntimeContext',
    ) -> None:
        self.config = config
        self.runtime_context = runtime_context

    def install(self) -> None:
        run_tool_requires_installation(
            ToolRequiresInstallationAdapter(
                resolve_install_prerequisites=self._resolve_install_prerequisites,
                log_runtime_context=self._log_runtime_context,
                install_platform_tool_requires=lambda tool_reqs,
                variant_requires,
                context: self._install_platform_tool_requires(
                    tool_reqs=tool_reqs,
                    variant_requires=variant_requires,
                    context=context,
                ),
                install_artifact_requires=lambda tool_reqs,
                variant_requires: self._install_artifact_requires(
                    tool_reqs=tool_reqs,
                    variant_requires=variant_requires,
                ),
                write_tool_requirements_file=self._write_tool_requirements_file,
            )
        )

    def _resolve_install_prerequisites(self):
        """Resolve runtime context and variant tool-requirements mapping."""
        context = self.runtime_context
        variant_requires = self.config.get_variant().get_tool_requires()
        if not isinstance(variant_requires, dict):
            return context, {}
        return context, variant_requires

    @staticmethod
    def _log_runtime_context(context: Any) -> None:
        logger.info(
            f'Runtime context: os={context.os_name}, is_docker={context.is_docker}'
        )

    def _install_platform_tool_requires(
        self,
        *,
        tool_reqs: List[Dict[str, Any]],
        variant_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        current_platform = platform.system()
        if current_platform == 'Windows':
            self._install_windows_platform_requires(
                tool_reqs=tool_reqs,
                variant_requires=variant_requires,
                context=context,
            )
            return

        if current_platform == 'Linux':
            self._install_linux_platform_requires(
                tool_reqs=tool_reqs,
                variant_requires=variant_requires,
                context=context,
            )
            return

        msg = f'Platform {current_platform} not supported'
        raise ConfigurationError(msg)

    def _install_windows_platform_requires(
        self,
        *,
        tool_reqs: List[Dict[str, Any]],
        variant_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        toolbase_requires = filter_tool_requires_by_type(
            requires=variant_requires,
            type_='toolbase',
            action_name=self.config.get_action_name(),
        )
        self._append_tool_requirements(
            tool_reqs,
            toolbase_requires,
            req_type='toolbase',
        )
        self._install_windows_toolbase(toolbase_requires, context)

        choco_requires = filter_tool_requires_by_type(
            requires=variant_requires,
            type_='choco',
            action_name=self.config.get_action_name(),
        )
        self._append_tool_requirements(
            tool_reqs,
            choco_requires,
            req_type='choco',
            include_properties=True,
        )
        self._install_windows_choco(choco_requires, context)

    def _install_linux_platform_requires(
        self,
        *,
        tool_reqs: List[Dict[str, Any]],
        variant_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        linux_package_requires = filter_tool_requires_by_type(
            requires=variant_requires,
            type_='linux_package',
            action_name=self.config.get_action_name(),
        )
        self._append_tool_requirements(
            tool_reqs,
            linux_package_requires,
            req_type='linux_package',
        )
        self._install_linux_packages(linux_package_requires, context)

    def _install_artifact_requires(
        self,
        *,
        tool_reqs: List[Dict[str, Any]],
        variant_requires: Dict[str, Any],
    ) -> None:
        artifact_tool_requires = filter_tool_requires_by_type(
            requires=variant_requires,
            type_='artifact',
            action_name=self.config.get_action_name(),
        )
        self._append_tool_requirements(
            tool_reqs,
            artifact_tool_requires,
            req_type='artifact',
            version_field='properties.rb_version',
            include_properties=True,
        )
        self._install_artifact_tool_requires(artifact_tool_requires)

    @staticmethod
    def _append_tool_requirements(
        tool_reqs: List[Dict[str, Any]],
        requires: Dict[str, Any],
        *,
        req_type: str,
        version_field: str = 'version',
        include_properties: bool = False,
    ) -> None:
        for name, conf in requires.items():
            properties = {
                k: str(v) for k, v in conf.get('properties', {}).items()
            }
            version = conf.get(version_field, '')
            if version_field.startswith('properties.'):
                version_key = version_field.split('.', maxsplit=1)[1]
                version = properties.get(version_key, '')

            tool_reqs.append(
                {
                    'name': name,
                    'type': req_type,
                    'version': version,
                    'properties': properties if include_properties else {},
                }
            )

    def _resolve_tool_env_file(self) -> Path:
        return self.config.get_build_folder() / 'xc-ce-utils.env'

    def _install_windows_toolbase(
        self,
        toolbase_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        if not toolbase_requires:
            return
        if context.is_docker:
            logger.info(
                'Skipping toolbase installation in docker context; expecting PATH/preinstalled tools.'
            )
            return

        env_file = self._resolve_tool_env_file()
        with FileLock('toolbase_installer'):
            tb_installer.install_tools(
                toolbase_requires,
                'cdg.de',
                env_file,
                append_to_env_file=True,
            )

        if not env_file.exists():
            msg = (
                f'Environment file {env_file} not found after installation. '
                'Check tool_requires configuration and TB_HOMEDIR environment variable.'
            )
            raise RuntimeError(msg)
        load_environment_variables_from_env_file(env_file)

    def _install_windows_choco(
        self,
        choco_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        if not choco_requires:
            return
        if context.is_docker:
            logger.info(
                'Skipping Chocolatey installation in docker context; expecting PATH/preinstalled tools.'
            )
            return

        env_file = self._resolve_tool_env_file()
        with FileLock('choco_installer'):
            choco_installer.install_tools(
                choco_requires,
                artifactories=self.config.get_artifactories(),
                env_file=env_file,
                append=True,
            )
        if env_file.exists():
            load_environment_variables_from_env_file(env_file)

    def _install_linux_packages(
        self,
        linux_package_requires: Dict[str, Any],
        context: Any,
    ) -> None:
        if not linux_package_requires:
            return
        if context.is_docker:
            logger.info(
                'Skipping Linux package installation in docker context; expecting PATH/preinstalled tools.'
            )
            return

        env_file = self._resolve_tool_env_file()
        with FileLock('linux_installer'):
            linux_installer.install_tools(
                linux_package_requires,
                env_file=env_file,
                append_to_env_file=True,
            )

        if not env_file.exists():
            msg = (
                f'Environment file {env_file} not found after installation. '
                'Check tool_requires configuration for linux_package type tools.'
            )
            raise RuntimeError(msg)
        load_environment_variables_from_env_file(env_file)

    def _install_artifact_tool_requires(
        self,
        artifact_tool_requires: Dict[str, Any],
    ) -> None:
        if not artifact_tool_requires:
            return

        env_file = self._resolve_tool_env_file()
        downloader = ArtifactoryInstaller(
            self.config.get_artifactories(),
            env_path=env_file,
            append=True,
        )
        with FileLock('jfrog_dependency_downloader'):
            downloader.download_dependencies_from_config(artifact_tool_requires)

        if env_file.exists():
            load_environment_variables_from_env_file(env_file)
            return
        logger.warning(
            f'Environment file {env_file} not found after artifact download'
        )

    def _write_tool_requirements_file(
        self, tool_reqs: List[Dict[str, Any]]
    ) -> None:
        tool_reqs_file = self.config.get_build_folder() / 'tool_reqs.json'
        tool_reqs_file.parent.mkdir(parents=True, exist_ok=True)
        tool_reqs_file.write_text(json.dumps(tool_reqs, indent=2))
        logger.debug(f'Tool requirements written to {tool_reqs_file}')
