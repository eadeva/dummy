"""Clang setup mixin for :class:`EnvironmentSetup`.

Provides :meth:`ClangSetupMixin._setup_clang` -- a single entry point
that, when the project opts in via ``main_conf.yml::CLANG_CONFIG`` *and*
the host is Windows, performs the full clang environment bring-up:

1. Install the clang toolchain. Default source is Artifactory (downloads
   a pre-built zip and extracts it to ``C:/tools/clang/<version>``);
   ``source: choco`` selects the legacy Chocolatey fallback instead.
2. Deploy the layered ``.clang-format`` / ``.clang-tidy`` / ``.clangd``
   templates into ``<repo>/config/`` and regenerate the root + per-directory
   files.
3. Optionally render the MemMap VFS overlay (when ``vfs_overlay: true``).
4. Patch ``.vscode/settings.json`` to point ``clangd.path`` at the just-
   installed binary so VS Code picks it up without manual configuration.

The mixin is host-aware: on Linux / non-Windows it short-circuits to a
no-op so the same project config can be shared across platforms.
"""

from __future__ import annotations

import json
import os
import platform
import re
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from xc_ce_utils.clang import (
    CLANG_ARTIFACTORY_DEFAULT_REL_PATH,
    CLANG_ARTIFACTORY_DEFAULT_VERSION,
    CLANG_CHOCO_DEFAULT_VERSION,
    CLANG_CHOCO_PACKAGE,
    CLANG_CHOCO_SOURCE_NAME,
    CLANG_CHOCO_SOURCE_URL,
)
from xc_ce_utils.clang.config_layer import (
    deploy_clang_configs,
    generate_clang_format_root,
    generate_clang_tidy_targets,
    generate_clangd_root,
)
from xc_ce_utils.clang.config_resolver import resolve_clang_config
from xc_ce_utils.rb_logger import logger


class ClangSetupMixin:
    """Mixin providing :meth:`_setup_clang` on :class:`EnvironmentSetup`."""

    def _setup_clang_local_toolchain(self, config: Dict[str, Any]) -> bool:
        """Install/refresh local clang toolchain without repository writes.

        This path is for developer machines where clang binaries and env vars
        must be available locally, while clang config generation is maintained
        by maintainers and shared via git.
        """
        try:
            if os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true':
                logger.debug('Skipping local clang toolchain setup in CI environment')
                return True

            if platform.system() != 'Windows':
                logger.debug('Skipping local clang toolchain setup on non-Windows host')
                return True

            repo_path: Path = self.repo_path  # type: ignore[attr-defined]
            clang_cfg = resolve_clang_config(config, repo_path)
            if clang_cfg is None:
                logger.debug(
                    'No CLANG_CONFIG set in main_conf.yml; skipping local clang toolchain setup'
                )
                return True
            if not clang_cfg.get('enabled', False):
                logger.debug(
                    'Clang feature disabled in project clang_conf.yml; skipping local clang toolchain setup'
                )
                return True

            logger.info('Setting up local clang toolchain (Windows, no repo writes)...')
            self._install_clang(clang_cfg, config)
            logger.success(' Local clang toolchain ready')
            return True

        except Exception as exc:
            logger.error(f'Failed to setup local clang toolchain: {exc}')
            logger.error(traceback.format_exc())
            return False

    def _setup_clang(self, config: Dict[str, Any]) -> bool:
        """Install + configure clang for this project.

        Args:
            config: Loaded ``main_conf.yml`` mapping. The clang feature is
                opt-in: when ``CLANG_CONFIG`` is absent or the resolved
                config has ``enabled: false``, this method returns ``True``
                immediately (success / nothing to do).

        Returns:
            ``True`` on success or no-op, ``False`` on a hard failure that
            the caller should surface.
        """
        try:
            # Skip in CI environments (matches GitHooksSetupMixin behaviour).
            if os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true':
                logger.debug('Skipping clang setup in CI environment')
                return True

            if platform.system() != 'Windows':
                logger.debug('Skipping clang setup on non-Windows host')
                return True

            repo_path: Path = self.repo_path  # type: ignore[attr-defined]
            clang_cfg = resolve_clang_config(config, repo_path)
            if clang_cfg is None:
                logger.debug('No CLANG_CONFIG set in main_conf.yml; skipping clang setup')
                return True
            if not clang_cfg.get('enabled', False):
                logger.debug('Clang feature disabled in project clang_conf.yml; skipping')
                return True

            logger.info('Setting up clang toolchain (Windows)...')

            # ---- 1) clang toolchain install ---------------------------
            install_root = self._install_clang(clang_cfg, config)

            # ---- 2) Layered config deployment + generation ----------------
            deployments = (clang_cfg.get('clang_tidy', {}) or {}).get('deployments', {}) or {}
            deploy_clang_configs(repo_path, deployments=deployments)
            generate_clang_format_root(repo_path)
            generate_clang_tidy_targets(repo_path, deployments)
            generate_clangd_root(repo_path)

            # ---- 3) Optional MemMap VFS overlay ---------------------------
            if clang_cfg.get('vfs_overlay', False):
                self._render_clang_vfs_overlay(repo_path)

            # ---- 4) VS Code clangd binding --------------------------------
            if install_root is not None:
                self._update_vscode_clangd_path(repo_path, install_root)

            logger.success(' Clang setup complete')
            return True

        except Exception as exc:
            logger.error(f'Failed to setup clang: {exc}')
            logger.error(traceback.format_exc())
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _install_clang(self, clang_cfg: Dict[str, Any], config: Dict[str, Any]) -> Optional[Path]:
        """Install clang via the configured ``source``; return install root.

        Defaults to the Artifactory download when ``source`` is unset or
        set to ``artifactory``; ``source: choco`` selects the legacy
        Chocolatey fallback.
        """
        source = str(clang_cfg.get('source') or 'artifactory').strip().lower()
        if source == 'choco':
            return self._install_clang_via_choco(clang_cfg)
        return self._install_clang_via_artifactory(clang_cfg, config)

    def _install_clang_via_artifactory(
        self, clang_cfg: Dict[str, Any], config: Dict[str, Any]
    ) -> Optional[Path]:
        """Download the pinned clang archive from Artifactory; return install root.

        Extracts to ``C:/tools/clang/<version>`` (flat layout: ``bin/``,
        ``include/``, ``lib/``, etc. directly under the version folder --
        matches the "legacy" branch already handled by
        :meth:`_resolve_clang_bin_dir`).
        """
        artifactory_section = clang_cfg.get('artifactory', {}) or {}
        alias = artifactory_section.get('alias')
        if not alias:
            logger.error(
                "clang source=artifactory requires 'artifactory.alias' in "
                'clang_conf.yml (a key into config/artifactories/artifactory_conf.yml)'
            )
            return None

        artifactories = config.get('ARTIFACTORIES', {}) or {}
        artifactory_conf = artifactories.get(alias)
        if not artifactory_conf:
            logger.error(f"Artifactory alias '{alias}' not found in ARTIFACTORIES config")
            return None

        clang_version = str(
            artifactory_section.get('version')
            or artifactory_section.get('rb_version')
            or CLANG_ARTIFACTORY_DEFAULT_VERSION
        ).strip()
        rel_path = str(
            artifactory_section.get('rel_path') or CLANG_ARTIFACTORY_DEFAULT_REL_PATH
        ).strip('/')

        install_root = Path('C:/tools/clang') / clang_version
        if self._resolve_clang_bin_dir(install_root) is not None:
            logger.info(f'clang already installed at {install_root}')
        else:
            from xc_ce_utils.artifactory_utils.artifactory_downloader import (  # noqa: PLC0415
                ArtifactoryDownloader,
            )
            from xc_ce_utils.global_modules.aux_helper import unzip_7z  # noqa: PLC0415

            install_root.mkdir(parents=True, exist_ok=True)
            downloader = ArtifactoryDownloader(
                artifactory_url=artifactory_conf['url'],
                repository=artifactory_conf['repository'],
            )
            logger.progress(
                'Starting clang toolchain download from Artifactory. '
                'Please note: downloading and extracting the toolchain (over 3 GB) '
                'may take several minutes depending on your network connection...'
            )
            candidate_patterns = [
                f'{rel_path}/clang_{clang_version}*',
                f'{rel_path}/{clang_version}/clang_{clang_version}*',
                f'{rel_path}/{clang_version}/clang.{clang_version}*',
                f'{rel_path}/clang.{clang_version}*',
            ]
            downloaded_files = []
            last_err = None
            for pattern in candidate_patterns:
                try:
                    logger.debug(
                        f"Trying to download clang from Artifactory with pattern: '{pattern}'"
                    )
                    downloaded_files = downloader.download_from_pattern(pattern, install_root)
                    if downloaded_files:
                        logger.info(
                            f"Successfully downloaded clang files using pattern: '{pattern}'"
                        )
                        break
                except Exception as e:
                    last_err = e
                    continue

            if not downloaded_files:
                raise last_err or Exception(
                    f"No clang archive matched any expected patterns under '{rel_path}' for version '{clang_version}'"
                )

            archive = next((p for p in downloaded_files if p.suffix in {'.zip', '.7z'}), None)
            if archive is None:
                logger.error(
                    f'No clang archive with suffix .zip or .7z matched in downloaded files: {downloaded_files}'
                )
                return None
            logger.progress(f'Unzipping clang {clang_version}...')
            unzip_7z(str(archive), str(install_root))
            archive.unlink(missing_ok=True)

        logger.info(f'clang installed at {install_root}')
        self._export_clang_env_vars(install_root)
        return install_root

    def _export_clang_env_vars(self, install_root: Path) -> None:
        """Export CHOCO_CLANG / CHOCO_CLANG_BIN / CLANGD_PATH; augment PATH.

        Shared by both install sources (Artifactory and Chocolatey) so
        downstream consumers (clangd, CMake runner, VS Code tasks) find the
        toolchain regardless of how it was installed. The clang setup runs
        during EnvironmentSetup -- before the action context exists -- so
        we cannot write to ``<build>/xc-ce-utils.env`` directly here;
        ``ActionConfiguration.dump_env_variables()`` picks up
        ``CHOCO_CLANG`` / ``CHOCO_CLANG_BIN`` from ``os.environ`` and
        persists them per action.
        """
        os.environ['CHOCO_CLANG'] = str(install_root)

        bin_dir = self._resolve_clang_bin_dir(install_root)
        if bin_dir is not None:
            os.environ['CHOCO_CLANG_BIN'] = str(bin_dir)
            current_path = os.environ.get('PATH', '')
            bin_str = str(bin_dir)
            # Avoid duplicating the entry on repeated invocations.
            path_entries = current_path.split(os.pathsep) if current_path else []
            if bin_str not in path_entries:
                os.environ['PATH'] = (
                    bin_str + os.pathsep + current_path if current_path else bin_str
                )

            clangd_name = 'clangd.exe' if os.name == 'nt' else 'clangd'
            clangd_exe = bin_dir / clangd_name
            if clangd_exe.is_file():
                # Highest-priority candidate checked by
                # generate_vscode_commands.py's detect_clangd_path(), so VS
                # Code settings regeneration works regardless of install source.
                os.environ['CLANGD_PATH'] = str(clangd_exe)
        else:
            logger.warning(
                f'clang installed at {install_root} but no clang(.exe) '
                f'binary was found under tools/bin or bin; CHOCO_CLANG_BIN '
                f'will not be exported and PATH will not be augmented.'
            )

        try:
            from xc_ce_utils.global_modules.aux_helper import (  # noqa: PLC0415
                export_to_github_env,
            )

            if os.environ.get('GITHUB_ACTIONS') == 'true':
                export_to_github_env('CHOCO_CLANG', str(install_root))
                if bin_dir is not None:
                    export_to_github_env('CHOCO_CLANG_BIN', str(bin_dir))
        except Exception as exc:  # pragma: no cover - best-effort export
            logger.debug(f'CHOCO_CLANG GitHub env export skipped: {exc}')

    def _install_clang_via_choco(self, clang_cfg: Dict[str, Any]) -> Optional[Path]:
        """Install Chocolatey + the Bosch clang package; return install root."""
        from xc_ce_utils.tool_installers.choco_installer import (  # noqa: PLC0415
            ChocoInstaller,
        )

        choco_section = clang_cfg.get('choco', {}) or {}
        clang_version = str(choco_section.get('version') or CLANG_CHOCO_DEFAULT_VERSION).strip()
        # Backward-compat: earlier project configs used plain semver
        # (e.g. "22.0.0") from an old package-id convention. The Bosch feed
        # currently exposes clang as prerelease-tagged versions
        # (e.g. "22.0.0-experimental").
        if CLANG_CHOCO_PACKAGE == 'clang' and re.fullmatch(r'\d+\.\d+\.\d+', clang_version):
            normalized = f'{clang_version}-experimental'
            logger.warning(
                f"clang choco.version '{clang_version}' looks like legacy plain semver; "
                f"using '{normalized}'"
            )
            clang_version = normalized
        chocolatey_version = choco_section.get('chocolatey_version')  # may be None
        side_by_side_raw = choco_section.get('side_by_side', False)
        if isinstance(side_by_side_raw, str):
            side_by_side = side_by_side_raw.strip().lower() in {
                '1',
                'true',
                'yes',
                'on',
            }
        else:
            side_by_side = bool(side_by_side_raw)

        # Minimal artifactory dict synthesised on the fly: ChocoInstaller's
        # configure_source() only needs (name, url); we don't go through the
        # tool_requires dispatch here since clang is an implicit, always-on
        # dependency of the clang feature itself.
        installer = ChocoInstaller(
            artifactories={
                CLANG_CHOCO_SOURCE_NAME: {
                    'url': CLANG_CHOCO_SOURCE_URL,
                    'repository': '',
                }
            },
            env_file=None,
            append=True,
        )
        installer.ensure_chocolatey_installed(chocolatey_version=chocolatey_version)
        installer.configure_source(CLANG_CHOCO_SOURCE_NAME, CLANG_CHOCO_SOURCE_URL)
        install_path = installer.install_package(
            CLANG_CHOCO_PACKAGE,
            version=clang_version,
            source=CLANG_CHOCO_SOURCE_NAME,
            side_by_side=side_by_side,
        )
        logger.info(f'clang installed at {install_path}')

        if install_path:
            install_root = Path(install_path)
            self._export_clang_env_vars(install_root)

        return Path(install_path) if install_path else None

    @staticmethod
    def _resolve_clang_bin_dir(install_root: Path) -> Optional[Path]:
        """Find the bin directory under *install_root* containing ``clang(.exe)``.

        The Bosch chocolatey ``clang`` package uses ``<root>/tools/bin``;
        legacy / upstream LLVM packages use ``<root>/bin``. Returns
        ``None`` when neither candidate exists.
        """
        clang_name = 'clang.exe' if os.name == 'nt' else 'clang'
        for sub in ('tools/bin', 'bin'):
            cand = install_root / sub
            if (cand / clang_name).is_file():
                return cand
        return None

    @staticmethod
    def _render_clang_vfs_overlay(_repo_path: Path) -> None:
        """Render the MemMap VFS overlay (best-effort; warn on failure)."""
        vfs_script = (
            Path(__file__).resolve().parent.parent.parent
            / 'clang'
            / 'templates'
            / 'vfs'
            / 'generate_vfs.py'
        )
        if not vfs_script.exists():
            logger.warning(
                'vfs_overlay enabled but generator script not shipped; '
                'skipping VFS overlay generation'
            )
            return
        import runpy  # noqa: PLC0415

        try:
            runpy.run_path(str(vfs_script), run_name='__main__')
            logger.info('MemMap VFS overlay generated')
        except Exception as exc:
            logger.warning(f'VFS overlay generation failed (non-fatal): {exc}')

    @staticmethod
    def _update_vscode_clangd_path(repo_path: Path, install_root: Path) -> None:
        """Point ``clangd.path`` in ``.vscode/settings.json`` at the clang install."""
        # Supported package layouts:
        # 0) bin/clangd.exe                       (Artifactory download, flat layout)
        # 1) tools/bin/clangd.exe                 (choco, current png-gen1 style)
        # 2) tools/LLVM/bin/clangd.exe            (choco, older LLVM-bundled layout)
        # 3) tools/clangd.exe                     (choco, flat legacy layout)
        candidates = [
            install_root / 'bin' / 'clangd.exe',
            install_root / 'tools' / 'bin' / 'clangd.exe',
            install_root / 'tools' / 'LLVM' / 'bin' / 'clangd.exe',
            install_root / 'tools' / 'clangd.exe',
        ]
        clangd_exe = next((p for p in candidates if p.exists()), None)
        if clangd_exe is None:
            logger.debug(
                f'clangd.exe not located under {install_root}; leaving '
                f'.vscode/settings.json untouched'
            )
            return

        settings_path = repo_path / '.vscode' / 'settings.json'
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    msg = 'settings.json root must be an object'
                    raise ValueError(msg)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(f'Could not parse {settings_path}; leaving untouched ({exc})')
                return
        else:
            data = {}

        new_path = str(clangd_exe).replace('\\', '/')
        if data.get('clangd.path') == new_path:
            return  # already up-to-date
        data['clangd.path'] = new_path
        settings_path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        logger.info(f'Updated {settings_path.relative_to(repo_path)} -> clangd.path={new_path}')
