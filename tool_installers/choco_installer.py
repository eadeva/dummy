"""Chocolatey-based tool installer for Windows.

Bootstraps a project-local Chocolatey instance and installs NuGet packages
from configured (typically Bosch Artifactory) NuGet sources. Designed as a
sibling of :mod:`xc_ce_utils.tool_installers.toolbase_installer` /
:mod:`xc_ce_utils.tool_installers.artifactory_installer` and consumed via
the generic ``type: choco`` ``tool_requires`` dispatch in
:meth:`xc_ce_utils.core_engine.application.orchestration.tool_requires_installer.ToolRequiresInstaller.install`.

Design choices (locked in plan.md):

* **Install root** defaults to ``D:\\tools\\choco`` when a D: drive exists,
  else ``C:\\tools\\choco``. For local escape-hatch scenarios it can be
  overridden with ``XC_CE_CHOCOLATEY_INSTALL``.
* **Default Chocolatey version** is ``1.4.0`` — matches the version already
  used by png-gen1 and is the latest line compatible with Bosch-internal
  Chocolatey packages. Bump :data:`CHOCOLATEY_DEFAULT_VERSION` (single point
  of change) when the Bosch ecosystem moves to 2.x.
* **Non-Windows**: every public method is a no-op with a single warning log.
  Linux/macOS variants of consuming projects simply skip choco-managed tools.
* **Source-resolution**: ``properties.artifactory`` on a ``type: choco``
  tool entry references a key in the project's artifactories dict
  (``config/artifactories/artifactory_conf.yml``). The matching ``url`` is
  registered as a Chocolatey source on first use.

``tool_requires`` entry shape (project-side YAML)::

    my-clang:
      type: choco
            version: "22.0.0-experimental"  # NuGet package version
      properties:
        artifactory: esw-ci-artifactory  # key in artifactories dict
                package: clang  # optional; defaults to entry name
      needed_for: [build]
"""

from __future__ import annotations

import os
import platform
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

from xc_ce_utils import logger
from xc_ce_utils.global_modules.aux_helper import export_to_github_env

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Single point of change. Bump when the Bosch package ecosystem catches up
#: to Chocolatey 2.x. png-gen1 references 1.4.0 today.
CHOCOLATEY_DEFAULT_VERSION = '1.4.0'

_CHOCO_INSTALL_SCRIPT_URL = 'https://community.chocolatey.org/install.ps1'

# Exit codes that Chocolatey treats as success-with-reboot-pending; we do too.
_CHOCO_SUCCESS_EXIT_CODES = {0, 1641, 3010}


def _resolve_install_root() -> Optional[Path]:
    """Return the Chocolatey install root for this host.

    Resolution order:

    1. ``XC_CE_CHOCOLATEY_INSTALL`` env var (escape hatch -- e.g. set to
       ``C:\\workspace\\_chocolatey`` to share png-gen1's install).
    2. ``D:\\tools\\choco`` when a D: drive exists, else ``C:\\tools\\choco``.

    Returns ``None`` on non-Windows platforms (no choco install).
    """
    if platform.system() != 'Windows':
        return None
    override = os.environ.get('XC_CE_CHOCOLATEY_INSTALL')
    if override:
        return Path(override)
    d_drive = Path('D:\\')
    base = d_drive if d_drive.exists() else Path('C:\\')
    return base / 'tools' / 'choco'


def _append_env_file(
    env_file: Path, name: str, value: str, append: bool
) -> None:
    """Persist a single ``NAME=VALUE`` line to the shared xc-ce-utils env file."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if append or env_file.exists() else 'w'
    with env_file.open(mode, encoding='utf-8') as fh:
        fh.write(f'{name}={value}\n')


# ---------------------------------------------------------------------------
# ChocoInstaller
# ---------------------------------------------------------------------------


class ChocoInstaller:
    """Bootstraps Chocolatey and installs NuGet packages from named sources.

    Args:
        artifactories: project artifactories dict (key -> {url, repository, ...});
            entries referenced by ``properties.artifactory`` on a choco
            ``tool_requires`` entry get registered as Chocolatey sources.
        env_file: optional path to the shared ``xc-ce-utils.env`` file. When
            provided, each installed package's lib directory is exported as
            ``CHOCO_<NAME>=<path>``.
        append: append to ``env_file`` instead of recreating it.
    """

    def __init__(
        self,
        artifactories: Optional[Dict[str, Any]] = None,
        env_file: Optional[Path] = None,
        append: bool = True,
    ):
        self.artifactories = artifactories or {}
        self.env_file = Path(env_file) if env_file else None
        self.append = append
        self.install_root = _resolve_install_root()
        self.choco_exe = (
            (self.install_root / 'choco.exe') if self.install_root else None
        )
        self._configured_sources: set[str] = set()

    # ------------------------------------------------------------------
    # Platform guard
    # ------------------------------------------------------------------
    def _is_windows(self) -> bool:
        if platform.system() == 'Windows':
            return True
        logger.warning(
            f'[CHOCO_INSTALLER] Chocolatey not supported on {platform.system()}; skipping'
        )
        return False

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        """Normalize bool-like values coming from YAML/tool config."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return bool(value)

    def _resolve_package_install_dir(
        self,
        name: str,
        version: Optional[str],
        side_by_side: bool,
    ) -> Path:
        """Resolve the package directory under ``<ChocolateyInstall>/lib``.

        Supports both layouts:
        - non-side-by-side: ``lib/<name>``
        - side-by-side: ``lib/<name>.<version>``
        """
        assert self.install_root is not None
        lib_dir = self.install_root / 'lib'
        candidates: list[Path] = []

        if side_by_side and version:
            candidates.append(lib_dir / f'{name}.{version}')
        candidates.append(lib_dir / name)
        if version:
            candidates.append(lib_dir / f'{name}.{version}')

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Last-resort fallback for package-specific naming nuances.
        if lib_dir.exists():
            matches = sorted(
                [p for p in lib_dir.glob(f'{name}*') if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                return matches[0]

        # Preserve historical behavior even if not materialized yet.
        return lib_dir / name

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def _locate_existing_chocolatey(self) -> Optional[Path]:
        """Find any working Chocolatey installation on the host.

        Search order (first hit wins):

        1. Our hard-coded ``install_root`` -- both ``<root>/choco.exe`` and
           the standard ``<root>/bin/choco.exe`` layouts.
        2. ``ChocolateyInstall`` env var (process > user > machine scope).
        3. ``choco`` on ``PATH`` (``shutil.which``).
        4. The conventional default ``C:\\ProgramData\\chocolatey``.

        Returns the resolved ``choco.exe`` path, or ``None`` when no
        existing install is found.
        """
        import shutil

        def _probe(root: Optional[Path]) -> Optional[Path]:
            if not root:
                return None
            for candidate in (root / 'choco.exe', root / 'bin' / 'choco.exe'):
                if candidate.is_file():
                    return candidate
            return None

        # 1) Hard-coded install_root
        hit = _probe(self.install_root)
        if hit:
            return hit

        # 2) Env-var-declared install roots (process / user / machine)
        for scope in ('Process', 'User', 'Machine'):
            try:
                # Process scope is just os.environ; user/machine are persisted scopes.
                if scope == 'Process':
                    value = os.environ.get('ChocolateyInstall')
                else:
                    # subprocess.check_output keeps us independent of pywin32.
                    value = subprocess.check_output(
                        [
                            'powershell.exe',
                            '-NoProfile',
                            '-Command',
                            f"[Environment]::GetEnvironmentVariable('ChocolateyInstall','{scope}')",
                        ],
                        text=True,
                    ).strip()
            except Exception:
                value = None
            hit = _probe(Path(value)) if value else None
            if hit:
                return hit

        # 3) choco on PATH
        on_path = shutil.which('choco')
        if on_path:
            return Path(on_path)

        # 4) Conventional default
        return _probe(Path(r'C:\ProgramData\chocolatey'))

    # ------------------------------------------------------------------
    def ensure_chocolatey_installed(
        self, chocolatey_version: Optional[str] = None
    ) -> Optional[Path]:
        """Install Chocolatey into :attr:`install_root` if not already present.

        Idempotent. Returns the path to ``choco.exe`` on success, ``None`` on
        non-Windows (no-op).
        """
        if not self._is_windows():
            return None
        assert (
            self.install_root is not None and self.choco_exe is not None
        )  # for mypy

        # Adopt any pre-existing Chocolatey install (our path OR png-gen1's
        # OR a system-wide one). The upstream install.ps1 refuses to lay down
        # a second instance, so duplicating is both impossible and pointless.
        existing = self._locate_existing_chocolatey()
        if existing is not None:
            # bin/choco.exe -> install_root is parent of parent; root/choco.exe -> parent.
            resolved_root = (
                existing.parent.parent
                if existing.parent.name == 'bin'
                else existing.parent
            )
            if resolved_root != self.install_root:
                logger.info(
                    f'[CHOCO_INSTALLER] Adopting existing Chocolatey at {resolved_root} '
                    f'(skipping bootstrap into hard-coded {self.install_root})'
                )
                self.install_root = resolved_root
            else:
                logger.debug(
                    f'[CHOCO_INSTALLER] Chocolatey present at {self.install_root}'
                )
            self.choco_exe = existing
            self._export_choco_env()
            return self.choco_exe

        version = chocolatey_version or CHOCOLATEY_DEFAULT_VERSION

        # install.ps1 refuses to install if the target directory already
        # exists -- regardless of whether it contains a working choco.exe.
        # Stale empty/partial dirs (e.g. from a prior failed bootstrap or
        # a User-scoped ChocolateyInstall env var pointing nowhere) must
        # therefore be removed before invoking the bootstrap script.
        if self.install_root.exists():
            has_choco = (self.install_root / 'choco.exe').is_file() or (
                self.install_root / 'bin' / 'choco.exe'
            ).is_file()
            if not has_choco:
                logger.info(
                    f'[CHOCO_INSTALLER] Removing stale Chocolatey directory at '
                    f'{self.install_root} (no choco.exe present) before bootstrap'
                )
                import shutil as _shutil

                _shutil.rmtree(self.install_root, ignore_errors=True)

        # NOTE: do NOT pre-create install_root (or anything under it) here --
        # install.ps1 refuses to run if its target directory already exists
        # (even empty). Let the upstream script create it. Chocolatey will
        # also create the tools dir lazily on first package install.
        self.install_root.parent.mkdir(parents=True, exist_ok=True)
        tools_dir = self.install_root / 'tools'
        logger.log_phase_header(f'CHOCOLATEY BOOTSTRAP ({version})')
        logger.info(
            f'[CHOCO_INSTALLER] Installing Chocolatey {version} into {self.install_root}'
        )

        ps_script = textwrap.dedent(
            f"""
            $ErrorActionPreference = 'Stop'
            [System.Environment]::SetEnvironmentVariable(
                'ChocolateyInstall','{self.install_root}',
                [System.EnvironmentVariableTarget]::User)
            [System.Environment]::SetEnvironmentVariable(
                'ChocolateyToolsLocation','{tools_dir}',
                [System.EnvironmentVariableTarget]::User)
            $env:ChocolateyInstall    = '{self.install_root}'
            $env:ChocolateyToolsLocation = '{tools_dir}'
            $env:chocolateyVersion    = '{version}'
            # Best-effort: corporate Group Policy may already pin the
            # ExecutionPolicy (e.g. 'Unrestricted'); the outer powershell.exe
            # was already invoked with -ExecutionPolicy Bypass so this call
            # is purely defensive. Swallow the SecurityException raised when
            # a higher-scope policy overrides the process scope.
            try {{
                Set-ExecutionPolicy Bypass -Scope Process -Force -ErrorAction Stop
            }} catch [System.Security.SecurityException] {{
                Write-Host "[CHOCO_INSTALLER] Set-ExecutionPolicy overridden by higher-scope policy (effective: $(Get-ExecutionPolicy)) -- continuing."
            }}
            [Net.WebRequest]::DefaultWebProxy.Credentials = [Net.CredentialCache]::DefaultCredentials
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('{_CHOCO_INSTALL_SCRIPT_URL}'))
            """
        ).strip()

        result = subprocess.run(
            [
                'powershell.exe',
                '-NoProfile',
                '-ExecutionPolicy',
                'Bypass',
                '-Command',
                ps_script,
            ],
            check=False,
        )
        if result.returncode != 0 or not self.choco_exe.exists():
            # install.ps1 may have written choco.exe to <root>/bin/choco.exe
            # instead of <root>/choco.exe; re-probe before declaring failure.
            bin_layout = self.install_root / 'bin' / 'choco.exe'
            if bin_layout.is_file():
                self.choco_exe = bin_layout
            else:
                msg = (
                    f'[CHOCO_INSTALLER] Chocolatey bootstrap failed '
                    f'(rc={result.returncode}, choco.exe present={self.choco_exe.exists()})'
                )
                raise RuntimeError(msg)

        logger.success(
            f'[CHOCO_INSTALLER] Chocolatey {version} ready at {self.install_root}'
        )
        self._export_choco_env()
        logger.log_phase_header('CHOCOLATEY BOOTSTRAP - END')
        return self.choco_exe

    def _export_choco_env(self) -> None:
        """Wire ChocolateyInstall + PATH into the current process and CI env."""
        if not self.install_root:
            return
        root = str(self.install_root)
        os.environ['CHOCOLATEYINSTALL'] = root
        os.environ['CHOCOLATEYTOOLSLOCATION'] = str(self.install_root / 'tools')
        current_path = os.environ.get('PATH', '')
        if root not in current_path:
            os.environ['PATH'] = f'{root};{current_path}'
        export_to_github_env('ChocolateyInstall', root)
        export_to_github_env('PATH', os.environ['PATH'])

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------
    def _resolve_credentials(
        self, url: str
    ) -> Optional[tuple[Optional[str], Optional[str]]]:
        """Look up artifactory credentials via the central RB credentials manager.

        Delegates to :class:`xc_ce_utils.auth.RBCredentialsManager` which
        handles CI env-vars, system keyring, and interactive prompts
        uniformly. Returns ``None`` on any import/lookup failure so callers
        fall back to anonymous source registration.
        """
        try:
            from xc_ce_utils.auth import get_credentials_manager

            return get_credentials_manager().get_credentials(url)
        except Exception as exc:
            logger.debug(
                f'[CHOCO_INSTALLER] credentials lookup failed for {url}: {exc}'
            )
            return None

    def configure_source(self, name: str, url: str) -> None:
        """Register (or refresh) a Chocolatey source by name.

        Uses ``choco source add`` which is itself idempotent (it upserts).
        Credentials are resolved via env vars or Windows Credential Manager
        (see :func:`_resolve_artifactory_credentials`) and persisted on the
        source so subsequent ``choco install`` calls don't prompt.
        """
        if not self._is_windows():
            return
        if not self.choco_exe or not self.choco_exe.exists():
            msg = '[CHOCO_INSTALLER] ensure_chocolatey_installed() must be called first'
            raise RuntimeError(msg)
        if name in self._configured_sources:
            return
        cmd = [
            str(self.choco_exe),
            'source',
            'add',
            '-n',
            name,
            '-s',
            url,
            '-y',
        ]
        creds = self._resolve_credentials(url)
        if creds and creds[0] and creds[1]:
            user, password = creds
            cmd += ['-u', user, '-p', password]
            logger.debug(
                f'[CHOCO_INSTALLER] source add -n {name} -s {url} -u {user} -p ***'
            )
        else:
            logger.debug(f'[CHOCO_INSTALLER] source add -n {name} -s {url}')
            logger.warning(
                f'[CHOCO_INSTALLER] No credentials resolved for {url}; '
                f'choco may prompt interactively or fail.'
            )
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            msg = (
                f"[CHOCO_INSTALLER] Failed to register source '{name}' "
                f'(rc={result.returncode})'
            )
            raise RuntimeError(msg)
        self._configured_sources.add(name)

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------
    def install_package(
        self,
        name: str,
        version: Optional[str] = None,
        source: Optional[str] = None,
        side_by_side: bool = False,
    ) -> Optional[Path]:
        """Install a single NuGet package via ``choco install``.

        Returns the resolved package lib directory under ``<install_root>/lib``
        (supports both ``<name>`` and ``<name>.<version>`` layouts) or
        ``None`` on non-Windows.
        """
        if not self._is_windows():
            return None
        if not self.choco_exe or not self.choco_exe.exists():
            msg = '[CHOCO_INSTALLER] ensure_chocolatey_installed() must be called first'
            raise RuntimeError(msg)
        assert self.install_root is not None  # for mypy

        cmd = [
            str(self.choco_exe),
            'install',
            name,
            '-y',
            '--no-progress',
        ]
        if version:
            cmd += ['--version', version]
        if source:
            cmd += ['-s', source]
        if side_by_side:
            cmd += ['--sidebyside']

        version_str = f' v{version}' if version else ''
        source_str = f' from {source}' if source else ''
        sbs_str = ' (side-by-side)' if side_by_side else ''
        logger.info(
            f'[CHOCO_INSTALLER] install {name}{version_str}{source_str}{sbs_str}'
        )
        result = subprocess.run(cmd, check=False)
        if result.returncode not in _CHOCO_SUCCESS_EXIT_CODES:
            msg = f'[CHOCO_INSTALLER] choco install {name} failed (rc={result.returncode})'
            raise RuntimeError(msg)
        install_dir = self._resolve_package_install_dir(
            name, version, side_by_side
        )
        logger.debug(f'[CHOCO_INSTALLER] resolved package dir: {install_dir}')
        return install_dir

    # ------------------------------------------------------------------
    # Generic dispatcher (called from execution_engine)
    # ------------------------------------------------------------------
    def install_tools(self, choco_requires: Dict[str, Any]) -> None:
        """Install every entry in *choco_requires* (already type-filtered).

        Steps:

        1. Bootstrap Chocolatey if missing.
        2. Walk the entries, register each referenced artifactory as a
           Chocolatey source (de-duplicated).
        3. Install each package; on success, export
           ``CHOCO_<NAME>=<install_root>/lib/<package>`` into the env file
           and the current process (so downstream build phases can find it).
        """
        if not choco_requires:
            return
        if not self._is_windows():
            logger.warning(
                f'[CHOCO_INSTALLER] Skipping {sorted(choco_requires)} on {platform.system()}'
            )
            return

        self.ensure_chocolatey_installed()

        # Pass 1: register all referenced sources up front so a multi-package
        # install only pays for source resolution once.
        for tool_name, conf in choco_requires.items():
            props = (conf or {}).get('properties') or {}
            art_key = props.get('artifactory')
            if not art_key:
                continue
            art = self.artifactories.get(art_key)
            if not art or 'url' not in art:
                msg = (
                    f"[CHOCO_INSTALLER] tool '{tool_name}' references unknown "
                    f"artifactory '{art_key}'"
                )
                raise RuntimeError(msg)
            self.configure_source(art_key, art['url'])

        # Pass 2: install + env wiring
        for tool_name, conf in choco_requires.items():
            props = (conf or {}).get('properties') or {}
            package = props.get('package', tool_name)
            version = conf.get('version') or props.get('rb_version')
            source = props.get('artifactory')
            side_by_side = self._coerce_bool(
                (conf or {}).get(
                    'side_by_side', props.get('side_by_side', False)
                )
            )
            install_dir = self.install_package(
                package,
                version=version,
                source=source,
                side_by_side=side_by_side,
            )
            if install_dir is None:
                continue
            env_name = (
                f"CHOCO_{tool_name.upper().replace('-', '_').replace('.', '_')}"
            )
            os.environ[env_name] = str(install_dir)
            export_to_github_env(env_name, str(install_dir))
            if self.env_file is not None:
                _append_env_file(
                    self.env_file,
                    env_name,
                    str(install_dir),
                    append=self.append,
                )


# ---------------------------------------------------------------------------
# Module-level convenience (mirrors toolbase_installer.install_tools signature)
# ---------------------------------------------------------------------------


def install_tools(
    choco_requires: Dict[str, Any],
    artifactories: Optional[Dict[str, Any]] = None,
    env_file: Optional[Path] = None,
    append: bool = True,
) -> None:
    """Functional wrapper for one-off invocations (e.g. from setup phases)."""
    installer = ChocoInstaller(
        artifactories=artifactories, env_file=env_file, append=append
    )
    installer.install_tools(choco_requires)
