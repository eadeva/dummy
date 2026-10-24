"""Importer that computes build context metadata for report headers."""

import json
import os
import platform
import subprocess
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class BuildContextImporter:
    """Populate report.metadata.build_context from canonical/environment inputs."""

    name = 'build-context'

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == '.json'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        metadata = report.metadata if isinstance(report.metadata, dict) else {}
        build_context = metadata.get('build_context', {})
        if not isinstance(build_context, dict):
            build_context = {}

        repo_root = str(metadata.get('repo_root', '') or '').strip()
        repo_root_path = Path(repo_root) if repo_root else None

        xc_ce_utils_version = (
            str(
                build_context.get('xc_ce_utils_version', '')
                or metadata.get('xc_ce_utils_version', 'unknown')
                or 'unknown'
            ).strip()
            or 'unknown'
        )
        build_context['xc_ce_utils_version'] = xc_ce_utils_version

        if not str(build_context.get('rb_version', '') or '').strip():
            build_context['rb_version'] = os.environ.get(
                'RB_VERSION', ''
            ).strip() or self._resolve_rb_version(repo_root_path)

        variant_alias = str(metadata.get('variant', '') or '').strip()
        if not str(build_context.get('variant_long_name', '') or '').strip():
            build_context['variant_long_name'] = self._resolve_variant_long_name(
                repo_root_path,
                variant_alias,
            )

        if not str(build_context.get('short_commit_hash', '') or '').strip():
            build_context['short_commit_hash'] = self._resolve_short_commit_hash(
                metadata,
                repo_root_path,
            )

        current_os_name = str(build_context.get('os_name', '') or '').strip().lower()
        if current_os_name in {'', 'unknown'}:
            os_name = self._resolve_os_name_from_metadata(metadata)
            if not os_name:
                os_name = self._resolve_os_name_from_execution_step(file_path)
            if not os_name:
                os_name = str(platform.system() or 'unknown').lower()
            build_context['os_name'] = os_name

        if 'docker_enabled' not in build_context:
            build_context['docker_enabled'] = self._resolve_docker_enabled(metadata)

        if 'git_is_dirty' not in build_context:
            build_context['git_is_dirty'] = self._resolve_git_is_dirty(repo_root_path)

        metadata['build_context'] = build_context
        report.metadata = metadata

    def _resolve_rb_version(self, repo_root_path: Path | None) -> str:
        if repo_root_path is None:
            return 'unknown'

        from xc_ce_utils.conf_file_loader.conf_file_loader import resolve_entry_conf_path

        main_conf = resolve_entry_conf_path(repo_root_path)
        if main_conf is None or not main_conf.exists():
            return 'unknown'

        rb_version_rel = ''
        try:
            lines = main_conf.read_text(encoding='utf-8-sig').splitlines()
            for raw_line in lines:
                line = str(raw_line).strip()
                if not line or line.startswith('#'):
                    continue
                if not line.startswith('RB_VERSIONING:'):
                    continue
                _, _, value = line.partition(':')
                rb_version_rel = str(value or '').strip()
                break
        except Exception:
            return 'unknown'

        if not rb_version_rel:
            return 'unknown'

        rb_version_file = Path(rb_version_rel)
        if not rb_version_file.is_absolute():
            rb_version_file = main_conf.parent / rb_version_file
        if not rb_version_file.exists():
            return 'unknown'

        try:
            version_data = json.loads(rb_version_file.read_text(encoding='utf-8-sig'))
        except Exception:
            return 'unknown'
        if not isinstance(version_data, dict):
            return 'unknown'

        major = str(version_data.get('MAJOR_VERSION', '')).strip()
        minor = str(version_data.get('MINOR_VERSION', '')).strip()
        bugfix = str(version_data.get('BUGFIX_VERSION', '')).strip()
        if major and minor and bugfix:
            return f'{major}.{minor}.{bugfix}'
        return 'unknown'

    def _resolve_variant_long_name(self, repo_root_path: Path | None, variant_alias: str) -> str:
        alias = str(variant_alias or '').strip()
        if not alias:
            return 'unknown'
        if repo_root_path is None:
            return alias

        setup_cfg = repo_root_path / '_builds' / 'xc-ce-utils-setup' / 'configuration.json'
        if not setup_cfg.exists():
            return alias

        try:
            setup_data = json.loads(setup_cfg.read_text(encoding='utf-8-sig'))
        except Exception:
            return alias

        setup_root = setup_data or {}
        project_cfg = setup_root.get('PROJECT_CONFIG', {})
        if not isinstance(project_cfg, dict):
            project_cfg = {}
        variants_root = project_cfg.get('variants', {})
        if not isinstance(variants_root, dict):
            legacy_project_root = setup_root.get('PROJECT', {})
            if isinstance(legacy_project_root, dict):
                variants_root = legacy_project_root.get('variants', {})
        if not isinstance(variants_root, dict):
            return alias

        for hw_variant in variants_root.values():
            if not isinstance(hw_variant, dict):
                continue
            for variant_key, variant_cfg in hw_variant.items():
                if not isinstance(variant_cfg, dict):
                    continue
                variant_alias_value = str(variant_cfg.get('alias', '')).strip()
                if str(variant_key).strip() == alias or variant_alias_value == alias:
                    description = str(variant_cfg.get('description', '')).strip()
                    return description or alias
        return alias

    def _resolve_short_commit_hash(self, metadata: dict, repo_root_path: Path | None) -> str:
        for key in [
            'git_short_commit_hash',
            'short_commit_hash',
            'commit_hash',
            'commit',
        ]:
            value = str(metadata.get(key, '') or '').strip()
            if value:
                return value[:12]

        if repo_root_path is None:
            return 'unknown'

        try:
            output = subprocess.check_output(
                [
                    'git',
                    '-C',
                    str(repo_root_path),
                    'rev-parse',
                    '--short',
                    'HEAD',
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
            resolved = str(output or '').strip()
            return resolved or 'unknown'
        except Exception:
            return 'unknown'

    def _resolve_os_name_from_metadata(self, metadata: dict) -> str:
        for key in ['os', 'xc_ce_utils_os', 'target_os']:
            value = str(metadata.get(key, '') or '').strip().lower()
            if value:
                return value
        return ''

    def _resolve_os_name_from_execution_step(self, file_path: Path) -> str:
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return ''

        if data.get('report_kind') != 'execution-step':
            return ''

        params = data.get('params', data.get('parameters', {})) or {}
        if not isinstance(params, dict):
            return ''

        target = str(params.get('target', '') or '').strip().lower()
        if target.endswith('_windows'):
            return 'windows'
        if target.endswith('_linux'):
            return 'linux'
        return ''

    def _resolve_docker_enabled(self, metadata: dict) -> bool:
        for key in ['is_docker', 'docker', 'in_docker']:
            value = metadata.get(key)
            if isinstance(value, bool):
                return value
            text = str(value or '').strip().lower()
            if text in {'1', 'true', 'yes', 'on'}:
                return True
            if text in {'0', 'false', 'no', 'off'}:
                return False

        for key in [
            'XC_CE_UTILS_DOCKER',
            'IS_DOCKER',
            'RUNNING_IN_DOCKER',
            'DOCKER',
        ]:
            text = str((os.environ.get(key, '') or '')).strip().lower()
            if text in {'1', 'true', 'yes', 'on'}:
                return True
        return Path('/.dockerenv').exists()

    def _resolve_git_is_dirty(self, repo_root_path: Path | None) -> str:
        """Resolve git dirty state from environment or GitPython."""
        env_val = os.environ.get('GIT_COMMIT_IS_DIRTY')
        if env_val:
            return 'true' if str(env_val).strip().lower() in {'1', 'true', 'yes', 'on'} else 'false'

        if repo_root_path is None:
            return 'false'

        try:
            import git

            repo = git.Repo(repo_root_path, search_parent_directories=True)
            return 'true' if repo.is_dirty() else 'false'
        except Exception:
            return 'false'
