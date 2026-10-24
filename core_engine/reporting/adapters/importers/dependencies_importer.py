"""Importer that enriches canonical dependency metadata from execution-step artifacts."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class DependenciesImporter:
    """Populate canonical requirements/artifactory_downloads metadata."""

    name = 'dependencies'

    def __init__(self) -> None:
        self._downloader_setups_by_report = {}

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False
        return data.get('report_kind') == 'execution-step'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        step = data.get('step', {}) or {}
        step_name = str(step.get('name', '') or '').strip()
        step_type = str(step.get('step_type', '') or '').strip().lower()
        parameters = data.get('params', data.get('parameters', {})) or {}
        artifacts = data.get('artifacts', {}) or {}
        results = [str(item) for item in data.get('results', [])]

        metadata = report.metadata if isinstance(report.metadata, dict) else {}
        requirements = self._normalize_dependency_items(
            metadata.get('requirements', [])
        )
        artifactory_downloads = self._normalize_dependency_items(
            metadata.get('artifactory_downloads', [])
        )

        runtime_req = self._extract_runtime_tool_requirement(
            step_type=step_type,
            step_name=step_name,
            parameters=parameters,
            results=results,
        )
        if runtime_req is not None:
            requirements.append(runtime_req)

        requirements.extend(
            self._collect_cmake_fetch_requirements(
                report=report,
                action=str(data.get('action', '') or '').strip(),
                variant=str(data.get('variant', '') or '').strip(),
                step_type=step_type,
                step_name=step_name,
                step_parameters=parameters,
                step_artifacts=artifacts,
            )
        )

        setups = self._load_downloader_setups(report)
        self._maybe_capture_downloader_setup(step_type, parameters, setups)

        runtime_download = self._extract_runtime_download(
            report=report,
            step_type=step_type,
            step_name=step_name,
            step_parameters=parameters,
            step_results=results,
            setups=setups,
        )
        if runtime_download is not None:
            artifactory_downloads.append(runtime_download)

        for item in artifactory_downloads:
            repository_name, repository_type = self._extract_repository_info(
                item
            )
            item['repository'] = repository_name
            item['repository_type'] = repository_type

        requirements = self._finalize_requirements(requirements)
        artifactory_downloads = self._finalize_downloads(artifactory_downloads)

        metadata['requirements'] = requirements
        metadata['artifactory_downloads'] = artifactory_downloads
        self._save_downloader_setups(report, setups)
        report.metadata = metadata

    def _normalize_dependency_items(self, items):
        normalized = []
        if not isinstance(items, list):
            return normalized
        for item in items:
            if not isinstance(item, dict):
                continue
            properties = {
                str(k): str(v)
                for k, v in (item.get('properties', {}) or {}).items()
            }
            normalized.append(
                {
                    'name': str(item.get('name', '')).strip(),
                    'type': str(item.get('type', '')).strip(),
                    'version': str(item.get('version', '')).strip(),
                    'properties': properties,
                    'repository': str(item.get('repository', '')).strip(),
                    'repository_type': str(
                        item.get('repository_type', '')
                    ).strip(),
                    'source': str(item.get('source', '')).strip(),
                }
            )
        return normalized

    def _extract_runtime_tool_requirement(
        self,
        step_type: str,
        step_name: str,
        parameters: dict,
        results: list[str],
    ):
        lowered = str(step_type or '').strip().lower()
        tool_name = ''
        if 'gcovr' in lowered:
            tool_name = 'gcovr'
        elif 'qac' in lowered or lowered in {'sca', 'sfa'}:
            tool_name = 'swq_sca_tools'

        if not tool_name:
            return None

        params = parameters if isinstance(parameters, dict) else {}
        version = ''
        version_keys = [
            'version',
            'tool_version',
            'qac_version',
            'gcovr_version',
        ]
        if tool_name == 'swq_sca_tools':
            version_keys.insert(0, 'swq_sca_tools_version')

        for key in version_keys:
            value = params.get(key)
            if value is not None and str(value).strip():
                version = str(value).strip()
                break

        if not version:
            for result_line in results or []:
                match = re.search(
                    r'(?:version\s*[=:]\s*|version\s+)([A-Za-z0-9._-]+)',
                    str(result_line),
                    re.IGNORECASE,
                )
                if match:
                    version = match.group(1)
                    break

        return {
            'name': tool_name,
            'type': 'step-runtime',
            'version': version or 'unknown',
            'properties': {
                'step': str(step_name or ''),
            },
            'source': 'execution_steps',
        }

    def _resolve_step_build_folder(
        self,
        report: CanonicalReport,
        step_parameters: dict,
        step_artifacts: dict,
    ):
        raw_path = str(
            (step_artifacts or {}).get('step_build_folder', '')
            or (step_parameters or {}).get('build_folder', '')
            or (step_parameters or {}).get('build_dir', '')
        ).strip()
        if not raw_path:
            return None

        try:
            candidate = Path(raw_path)
        except Exception:
            return None

        if candidate.is_absolute():
            return candidate

        repo_root = str(
            (report.metadata or {}).get('repo_root', '') or ''
        ).strip()
        if not repo_root:
            return None

        try:
            return Path(repo_root) / candidate
        except Exception:
            return None

    def _parse_fetchcontent_meta(self, fetch_dir: Path, dep_name: str):
        version = 'unknown'
        properties = {
            'origin': 'cmake-fetchcontent',
        }

        clone_script = fetch_dir / f'{dep_name}-gitclone.cmake'
        if not clone_script.exists():
            return version, properties

        try:
            script_text = clone_script.read_text(
                encoding='utf-8', errors='ignore'
            )
        except Exception:
            return version, properties

        url_match = re.search(
            r'clone\b[^\n]*?"((?:ssh|https?)://[^"]+|git@[^"]+)"',
            script_text,
            re.IGNORECASE,
        )
        if url_match:
            properties['url'] = str(url_match.group(1)).strip()

        ref_match = re.search(
            r'checkout\s+"([^"]+)"\s+--',
            script_text,
            re.IGNORECASE,
        )
        if ref_match:
            raw_ref = str(ref_match.group(1)).strip()
            properties['ref'] = raw_ref
            normalized_ref = raw_ref
            if normalized_ref.lower().startswith('refs/tags/'):
                normalized_ref = normalized_ref[10:]
            elif normalized_ref.lower().startswith('refs/heads/'):
                normalized_ref = normalized_ref[11:]
            version = normalized_ref or 'unknown'

        return version, properties

    def _collect_cmake_fetch_requirements(
        self,
        report: CanonicalReport,
        action: str,
        variant: str,
        step_type: str,
        step_name: str,
        step_parameters: dict,
        step_artifacts: dict,
    ) -> list[dict]:
        lowered_type = str(step_type or '').strip().lower()
        lowered_name = str(step_name or '').strip().lower()
        if 'cmake' not in lowered_type and 'cmake' not in lowered_name:
            return []
        if (
            'set-up' not in lowered_type
            and 'setup' not in lowered_type
            and 'set-up' not in lowered_name
            and 'setup' not in lowered_name
        ):
            return []

        build_folder = self._resolve_step_build_folder(
            report, step_parameters, step_artifacts
        )

        dependencies = []
        seen_names = set()

        candidate_roots = self._cmake_fetch_roots(
            report=report,
            action=action,
            variant=variant,
            build_folder=build_folder,
        )
        if not candidate_roots:
            return []

        for candidate_root in candidate_roots:
            fetch_root = candidate_root / 'CMakeFiles' / 'fc-tmp'
            if fetch_root.exists() and fetch_root.is_dir():
                for item in sorted(fetch_root.iterdir()):
                    if not item.is_dir():
                        continue
                    dep_name = str(item.name or '').strip()
                    if not dep_name or dep_name.lower() in seen_names:
                        continue
                    version, properties = self._parse_fetchcontent_meta(
                        item, dep_name
                    )
                    properties['step'] = str(step_name or '')
                    dependencies.append(
                        {
                            'name': dep_name,
                            'type': 'cmake-fetch',
                            'version': version,
                            'properties': properties,
                            'source': 'execution_steps',
                        }
                    )
                    seen_names.add(dep_name.lower())

            deps_root = candidate_root / '_deps'
            if deps_root.exists() and deps_root.is_dir():
                for src_dir in sorted(deps_root.glob('*-src')):
                    if not src_dir.is_dir():
                        continue
                    dep_name = str(src_dir.name[:-4]).strip()
                    if not dep_name or dep_name.lower() in seen_names:
                        continue
                    dependencies.append(
                        {
                            'name': dep_name,
                            'type': 'cmake-fetch',
                            'version': 'unknown',
                            'properties': {
                                'origin': 'cmake-fetchcontent',
                                'step': str(step_name or ''),
                            },
                            'source': 'execution_steps',
                        }
                    )
                    seen_names.add(dep_name.lower())

        return dependencies

    def _cmake_fetch_roots(
        self,
        report: CanonicalReport,
        action: str,
        variant: str,
        build_folder: Path | None,
    ) -> list[Path]:
        candidates = []

        for base_dir in self._fetchcontent_base_dirs_from_cmake_cache(
            report=report,
            action=action,
            variant=variant,
        ):
            # Most projects set FETCHCONTENT_BASE_DIR to <build_root>/_deps.
            # Map this back to build root so fc-tmp and _deps are both discoverable.
            if str(base_dir.name or '').strip().lower() == '_deps':
                candidates.append(base_dir.parent)
            candidates.append(base_dir)

        if build_folder is not None and build_folder.exists():
            candidates.append(build_folder)

        # Some actions use per-step folders (for example build/configure) while
        # CMake fetch artifacts are emitted in the action root one level above.
        if build_folder is not None and build_folder.exists():
            current = build_folder
            for _ in range(2):
                parent = current.parent
                if parent == current:
                    break
                candidates.append(parent)
                current = parent

        roots = []
        seen = set()
        for candidate in candidates:
            try:
                normalized = str(candidate.resolve()).strip().lower()
            except Exception:
                normalized = str(candidate).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            has_markers = (candidate / 'CMakeFiles' / 'fc-tmp').exists() or (
                candidate / '_deps'
            ).exists()
            if has_markers:
                roots.append(candidate)

        return roots

    def _fetchcontent_base_dirs_from_cmake_cache(
        self,
        report: CanonicalReport,
        action: str,
        variant: str,
    ) -> list[Path]:
        repo_root = str(
            (report.metadata or {}).get('repo_root', '') or ''
        ).strip()
        action_name = str(
            action or (report.metadata or {}).get('action', '') or ''
        ).strip()
        variant_alias = str(
            variant or (report.metadata or {}).get('variant', '') or ''
        ).strip()
        if not repo_root or not action_name or not variant_alias:
            return []

        action_root = Path(repo_root) / '_builds' / variant_alias / action_name
        if not action_root.exists() or not action_root.is_dir():
            return []

        cmake_caches = []
        try:
            cmake_caches = sorted(action_root.rglob('CMakeCache.txt'))
        except Exception:
            return []

        base_dirs = []
        seen = set()
        for cache_file in cmake_caches:
            cache_dir = cache_file.parent
            fetch_dir = self._read_fetchcontent_base_dir(cache_file, cache_dir)
            if fetch_dir is None:
                continue
            try:
                normalized = str(fetch_dir.resolve()).strip().lower()
            except Exception:
                normalized = str(fetch_dir).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            base_dirs.append(fetch_dir)

        return base_dirs

    def _read_fetchcontent_base_dir(self, cache_file: Path, cache_dir: Path):
        try:
            lines = cache_file.read_text(
                encoding='utf-8', errors='ignore'
            ).splitlines()
        except Exception:
            return None

        for raw_line in lines:
            line = str(raw_line or '').strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue

            match = re.match(
                r'^FETCHCONTENT_BASE_DIR(?::[A-Za-z_]+)?=(.+)$', line
            )
            if not match:
                continue

            raw_value = str(match.group(1) or '').strip()
            if not raw_value:
                return None

            try:
                candidate = Path(raw_value)
            except Exception:
                return None

            if not candidate.is_absolute():
                candidate = cache_dir / candidate

            return candidate

        return None

    def _load_downloader_setups(self, report: CanonicalReport) -> dict:
        key = id(report)
        cached = self._downloader_setups_by_report.get(key, {})
        if not isinstance(cached, dict):
            return {}
        return {
            str(downloader_id): {
                'base_url': str(
                    (value or {}).get('base_url', '') or ''
                ).strip(),
                'repository': str(
                    (value or {}).get('repository', '') or ''
                ).strip(),
            }
            for downloader_id, value in cached.items()
            if isinstance(value, dict)
        }

    def _save_downloader_setups(
        self, report: CanonicalReport, setups: dict
    ) -> None:
        self._downloader_setups_by_report[id(report)] = dict(setups)

    def _maybe_capture_downloader_setup(
        self, step_type: str, params: dict, setups: dict
    ) -> None:
        if str(step_type or '').strip().lower() != 'art_downloader_setup':
            return
        if not isinstance(params, dict):
            return
        downloader_id = str(params.get('id', '') or '').strip()
        if not downloader_id:
            return
        setups[downloader_id] = {
            'base_url': str(params.get('base_url', '') or '').strip(),
            'repository': str(params.get('repository', '') or '').strip(),
        }

    def _extract_repository_from_download_url(self, download_url: str):
        if not download_url:
            return '', ''
        try:
            parsed = urlparse(str(download_url).strip())
        except Exception:
            return '', ''
        if not parsed.scheme or not parsed.netloc:
            return '', ''

        path_parts = [part for part in parsed.path.split('/') if part]
        lowered_parts = [part.lower() for part in path_parts]
        repository_name = ''
        if 'artifactory' in lowered_parts:
            idx = lowered_parts.index('artifactory')
            if idx + 1 < len(path_parts):
                repository_name = path_parts[idx + 1].strip()

        base_url = f'{parsed.scheme}://{parsed.netloc}'
        return repository_name, base_url

    def _resolve_download_folder(
        self, report: CanonicalReport, step_results: list[str]
    ):
        for result_line in step_results or []:
            match = re.search(
                r'Artifact downloaded successfully:\s*(.+)$',
                str(result_line),
            )
            if not match:
                continue
            raw_path = str(match.group(1) or '').strip()
            if not raw_path:
                continue
            try:
                candidate = Path(raw_path)
            except Exception:
                continue
            if candidate.is_absolute():
                return candidate

            repo_root = str(
                (report.metadata or {}).get('repo_root', '') or ''
            ).strip()
            if repo_root:
                return Path(repo_root) / candidate
        return None

    def _extract_runtime_download(
        self,
        report: CanonicalReport,
        step_type: str,
        step_name: str,
        step_parameters: dict,
        step_results: list[str],
        setups: dict,
    ):
        lowered_type = str(step_type or '').strip().lower()
        if lowered_type not in {'art_download', 'art_download_central'}:
            return None

        params = step_parameters if isinstance(step_parameters, dict) else {}

        raw_properties = params.get('properties', {})
        properties = {}
        if isinstance(raw_properties, dict):
            properties = {str(k): str(v) for k, v in raw_properties.items()}

        art_rel_path = (
            str(params.get('art_rel_path', '') or '').strip().strip('/')
        )
        download_name = str(params.get('download_id', '') or '').strip()
        if not download_name and art_rel_path:
            download_name = art_rel_path.split('/')[-1].strip()
        if not download_name:
            download_name = str(step_name or '').strip()

        downloader_id = str(params.get('downloader_id', '') or '').strip()
        setup = setups.get(downloader_id, {})
        base_url = str(
            params.get('base_url', '') or setup.get('base_url', '')
        ).strip()
        repository = str(
            params.get('repository', '') or setup.get('repository', '')
        ).strip()

        version = str(
            params.get('version', '')
            or properties.get('rb_version', '')
            or properties.get('version', '')
        ).strip()

        if params.get('latest', False):
            download_folder = self._resolve_download_folder(
                report, step_results
            )
            if download_folder is not None:
                artifact_meta = download_folder / '.artifact_meta.json'
                if artifact_meta.exists():
                    try:
                        meta = json.loads(
                            artifact_meta.read_text(encoding='utf-8-sig')
                        )
                    except Exception:
                        meta = {}

                    if isinstance(meta, dict):
                        meta_properties = meta.get('properties', {})
                        if isinstance(meta_properties, dict):
                            meta_rb_version = str(
                                meta_properties.get('rb_version', '')
                            ).strip()
                            if meta_rb_version:
                                version = meta_rb_version
                                properties.setdefault(
                                    'rb_version', meta_rb_version
                                )

                        meta_download_url = str(
                            meta.get('download_url', '')
                        ).strip()
                        if meta_download_url:
                            meta_repository, meta_base_url = (
                                self._extract_repository_from_download_url(
                                    meta_download_url
                                )
                            )
                            if not repository and meta_repository:
                                repository = meta_repository
                            if not base_url and meta_base_url:
                                base_url = meta_base_url

        return {
            'name': download_name,
            'type': str(params.get('type', '') or 'artifact').strip(),
            'version': version,
            'properties': properties,
            'repository': repository,
            'repository_type': self._repository_type_from_url(base_url),
            'source': 'runtime',
        }

    def _repository_type_from_url(self, url: str) -> str:
        host = ''
        if url:
            try:
                host = (urlparse(str(url)).hostname or '').strip().lower()
            except Exception:
                host = ''
        if host == 'rb-artifactory.bosch.com':
            return 'RB'
        if host == 'artifactory.boschdevcloud.com':
            return 'BDC'
        return 'OTHER'

    def _extract_repository_info(self, item: dict):
        properties = item.get('properties', {}) or {}
        repository_name = str(
            item.get('repository', '')
            or properties.get('repository', '')
            or properties.get('repo', '')
            or properties.get('repo_name', '')
            or properties.get('artifactory_repository', '')
            or properties.get('artifactory_repo', '')
            or properties.get('artifactory', '')
        ).strip()

        repository_type = (
            str(
                item.get('repository_type', '')
                or properties.get('repository_type', '')
                or properties.get('artifactory_type', '')
            )
            .strip()
            .upper()
        )

        url_candidates = [
            item.get('url', ''),
            properties.get('url', ''),
            properties.get('download_url', ''),
            properties.get('artifact_url', ''),
            properties.get('repository_url', ''),
            properties.get('artifactory_url', ''),
        ]
        parsed_url = None
        for candidate in url_candidates:
            candidate_text = str(candidate or '').strip()
            if not candidate_text:
                continue
            try:
                maybe_parsed = urlparse(candidate_text)
                if maybe_parsed.scheme and maybe_parsed.netloc:
                    parsed_url = maybe_parsed
                    break
            except Exception:
                continue

        if not repository_name and parsed_url:
            path_parts = [part for part in parsed_url.path.split('/') if part]
            lowered_parts = [part.lower() for part in path_parts]
            if 'artifactory' in lowered_parts:
                idx = lowered_parts.index('artifactory')
                if idx + 1 < len(path_parts):
                    repository_name = path_parts[idx + 1].strip()

        if repository_type not in {'RB', 'BDC', 'OTHER'}:
            url_for_type = parsed_url.geturl() if parsed_url else ''
            repository_type = self._repository_type_from_url(url_for_type)

        return repository_name, repository_type

    def _finalize_requirements(self, requirements: list[dict]) -> list[dict]:
        filtered = []
        for item in requirements:
            if not isinstance(item, dict):
                continue
            if str(item.get('type', '')).strip().lower() == 'artifact':
                continue
            filtered.append(item)

        deduped = []
        seen = set()
        for item in filtered:
            key = (
                str(item.get('name', '') or '').strip().lower(),
                str(item.get('type', '') or '').strip().lower(),
                str(item.get('version', '') or '').strip(),
                ';'.join(
                    f'{k}={v}'
                    for k, v in sorted(
                        (item.get('properties', {}) or {}).items()
                    )
                ),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        deduped.sort(
            key=lambda item: (
                str(item.get('name', '') or '').strip().lower(),
                str(item.get('type', '') or '').strip().lower(),
                str(item.get('version', '') or '').strip(),
            )
        )
        return deduped

    def _finalize_downloads(self, downloads: list[dict]) -> list[dict]:
        source_priority = {
            'tool_requires': 0,
            'build_artifact_dependencies': 1,
            'requirements': 2,
            'execution_steps': 3,
            '': 4,
        }

        sorted_items = sorted(
            downloads,
            key=lambda item: (
                source_priority.get(
                    str(item.get('source', '')).strip().lower(), 99
                ),
                str(item.get('name', '')).strip().lower(),
                str(item.get('version', '')).strip(),
            ),
        )

        deduped = []
        seen = set()
        for item in sorted_items:
            key = (
                str(item.get('name', '') or '').strip().lower(),
                str(item.get('type', '') or '').strip().lower(),
                str(item.get('version', '') or '').strip(),
                str(item.get('repository', '') or '').strip().lower(),
                str(item.get('repository_type', '') or '').strip().upper(),
                ';'.join(
                    f'{k}={v}'
                    for k, v in sorted(
                        (item.get('properties', {}) or {}).items()
                    )
                ),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return deduped
