import os
import random
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from git import Repo

from xc_ce_utils import logger
from xc_ce_utils.artifactory_utils.artifactory_uploader import (
    ArtifactoryUploader,
)
from xc_ce_utils.conf_file_loader.conf_file_loader import get_logs_root
from xc_ce_utils.core_engine.config.action_configuration import (
    UPLOAD_PATH_ENV,
    ActionConfiguration,
)
from xc_ce_utils.global_modules.aux_helper import zip_folder
from xc_ce_utils.utils.git_source_commit import describe_ref, short_commit, source_commit

HTTP_POSITIVE_RESPONSE_CODES = [200, 201, 202, 204]


@dataclass(frozen=True)
class _UploadRequest:
    """Parameters for uploading one prepared artifact to every artifactory alias."""

    artifactories: List[str]
    to_zip: bool
    is_folder: bool
    deploy_artifact_path: Path
    target_path: str
    artifact_name: str
    artifact_properties: Dict[str, Any]
    deployment_name: str


@dataclass(frozen=True)
class _PrCommentAttempt:
    """Parameters for a single create-or-update attempt of the PR comment."""

    comments_url: str
    api_url: str
    repo: str
    headers: Dict[str, str]
    action_name: str
    variant: str
    links: List[Tuple[str, str]]
    attempt: int
    max_retries: int


class Deployer:
    """
    Responsible for deploying build artifacts to Artifactory repositories.

    This class handles the deployment of various build artifacts (binaries, reports,
    documentation, etc.) to Artifactory repositories based on the build action type.
    It supports different deployment patterns for different CI environments (GitHub Actions,
    Jenkins) and determines the target paths based on branch, tag, or pull request information.

    .. uml:: _diagrams/artifactory_uploader.puml
        :align: center

    The deployer can handle various artifact types:
    - BUILD: Binary artifacts from the build process
    - SCA/SFA: Static code analysis reports
    - DOC: Documentation artifacts
    - OSS: Open Source Software artifacts
    - SIMPLE_DEPLOY: Custom artifacts from specified paths

    Attributes:
        repo_root (Path): Root directory of the repository
        repo (Repo): Git repository object
        build_conf (Dict[str, Any]): Build configuration dictionary
        artifactory_conf (Dict[str, Any]): Artifactory configuration from build_conf
        repo_name (str): Name of the repository derived from git
        branch_name (Optional[str]): Name of the current branch
        commit_hash (str): Short hash of the current commit
        pull_request (bool): Whether the build is from a pull request
        pull_request_id (Optional[str]): ID of the pull request if applicable
        tag (Optional[str]): Tag name if building from a tag
        upload_folder (str): Target folder path in Artifactory
        logs_folder (Path): Path to the logs directory
        deploy_folder (Path): Path to the deployment directory

    """

    def __init__(
        self,
        repo_root: Path,
        build_conf: ActionConfiguration,
        repo_name: Optional[str] = None,
        logs_folder: Optional[Path] = None,
        deploy_folder: Optional[Path] = None,
    ) -> None:
        """
        Initialize the Deployer with repository paths and configurations.

        Args:
            repo_root (Path): Root directory of the repository
            build_conf (Dict[str, Any]): Build configuration dictionary containing
                                       deployment settings and artifact information
            repo_name (Optional[str]): Repository name. If None, will be derived from git remote URL
            logs_folder (Optional[Path]): Logs folder path. If None, defaults to repo_root/log
            deploy_folder (Optional[Path]): Deploy folder path. If None, defaults to repo_root/deploy

        Raises:
            ValueError: If the repository is not a valid git repository

        Side Effects:
            - Initializes git repository object
            - Sets up target paths for deployment
            - Determines branch/tag/PR information from environment variables
        """
        self.repo_root = Path(repo_root)
        self.repo = Repo(self.repo_root)
        self.build_conf = build_conf
        self.artifactory_conf = build_conf.artifactories
        self.rb_version = self.build_conf.artifact_version

        self.repo_name = repo_name or self.repo.remotes.origin.url.split('/')[-1].replace(
            '.git', ''
        )
        self.branch_name = None
        # Always calculate hashes directly from repo, don't trust environment variables
        self.long_commit_hash = source_commit(self.repo_root)
        self.commit_hash = short_commit(self.repo_root, self.long_commit_hash, 8)

        # Debug logging to track hash calculation
        logger.info(' Deployer git hash calculation:')
        logger.info(f'   Short hash (calculated): {self.commit_hash}')
        logger.info(f'   Long hash (calculated): {self.long_commit_hash}')
        logger.info(f'   HEAD detached: {self.repo.head.is_detached}')
        logger.info(
            f'   Current ref: {self.repo.head.ref if not self.repo.head.is_detached else "DETACHED"}'
        )

        self.pull_request = False
        self.pull_request_id = None
        self.tag = None

        self.set_base_upload_path()
        self.upload_folder = os.environ.get(UPLOAD_PATH_ENV) or self.upload_folder

        self.logs_folder = logs_folder or get_logs_root(self.repo_root)
        # Variant path already uses underscore for filesystem compatibility
        self.deploy_folder = (
            deploy_folder or self.repo_root / '_deploy' / build_conf.variant.get_variant_path()
        )

    def deploy(self, deployments: Dict[str, Any]) -> None:
        """
        Deploy build artifacts to Artifactory based on the action type.

        This method coordinates the overall deployment process by:
        1. Setting up the Artifactory connection
        2. Configuring artifact properties
        3. Creating target folder paths
        4. Uploading files specified in the deployment configuration

        Args:
            deployments (Dict): dictionary containing deployments and their configuration

        Side Effects:
            - Uploads files to Artifactory
            - Logs deployment status and results
        """
        logger.log_phase_header('DEPLOY')

        temp_folder = self.deploy_folder / 'temp'
        action = self.build_conf.action.lower()
        comment_links: List[Tuple[str, str]] = []

        for deployment_name, deployment in deployments.items():
            self._remove_existing_deploy_folder()
            comment_links.extend(
                self._deploy_single_entry(
                    deployment_name=deployment_name,
                    deployment=deployment,
                    action=action,
                    temp_folder=temp_folder,
                )
            )

        if comment_links:
            self._post_github_pr_comment(comment_links)

        # Clean up temporary folder
        if temp_folder.exists():
            logger.debug(f'Removing temporary folder: {temp_folder}')
            shutil.rmtree(temp_folder)

        logger.log_phase_header('DEPLOY - END')

    def _remove_existing_deploy_folder(self) -> None:
        """Remove the deploy folder from a previous deployment entry, if any."""
        if self.deploy_folder.exists():
            logger.info(f'Removing existing deploy folder: {self.deploy_folder}')
            shutil.rmtree(self.deploy_folder)

    @staticmethod
    def _validate_deployment_params(
        deployment: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str], Dict[str, Any]]:
        """Validate one deployment entry and extract its core parameters.

        Returns ``(to_zip, deployment_path, repository_full_path, artifact_properties)``.
        Exits the process (``sys.exit(1)``) on any validation failure, matching the
        pre-refactor behavior exactly.
        """
        to_zip = deployment.get('zip', False)
        if 'path' not in deployment:
            logger.critical("'path' deployment parameter is mandatory")
            sys.exit(1)

        deployment_path = deployment['path']
        if to_zip and 'zip_name' not in deployment:
            logger.critical(
                "'zip_name' deployment parameter is mandatory when 'zip' parameter is active"
            )
            sys.exit(1)

        unsupported_params = [
            param for param in ('only_relative_path', 'upload_rel_path') if param in deployment
        ]
        if unsupported_params:
            logger.critical(
                'Unsupported deployment parameter(s): '
                f'{", ".join(unsupported_params)}. '
                "Use 'repository_full_path' for explicit path control."
            )
            sys.exit(1)

        repository_full_path = deployment.get('repository_full_path')
        artifact_properties = deployment.get('properties', {})

        if 'artifactory' not in deployment:
            logger.critical("'artifactory' deployment parameter is mandatory")
            sys.exit(1)

        if repository_full_path is not None:
            if not str(repository_full_path).strip():
                logger.critical("'repository_full_path' cannot be empty when provided")
                sys.exit(1)
            if str(repository_full_path).startswith('/'):
                logger.critical(
                    '\'repository_full_path\' must be repository-relative (must not start with "/")'
                )
                sys.exit(1)

        return (
            to_zip,
            deployment_path,
            repository_full_path,
            artifact_properties,
        )

    def _build_artifact_properties(
        self, artifact_properties: Dict[str, Any], action: str
    ) -> Dict[str, Any]:
        """Populate the standard XC-CE artifact properties on top of user-provided ones."""
        artifact_properties['commit_hash'] = self.commit_hash
        # Use the calculated long commit hash instead of environment variable
        artifact_properties['long_commit_hash'] = self.long_commit_hash.lower()
        artifact_properties['rb_artifact'] = os.environ.get(
            'XC_CE_UTILS_ARTIFACT', 'unknown'
        ).lower()
        artifact_properties['release_status'] = self._resolve_release_status(artifact_properties)
        artifact_properties['git_is_dirty'] = os.environ.get('GIT_COMMIT_IS_DIRTY', 'False').lower()
        artifact_properties['action'] = action
        variant_alias = os.environ.get('XC_CE_UTILS_VARIANT_ALIAS', '').strip()
        if variant_alias:
            artifact_properties['variant_alias'] = variant_alias
        artifact_properties['branch'] = os.environ.get(
            'XC_CE_UTILS_BRANCH_NAME', self.branch_name or 'unknown'
        ).strip()
        # pr_number is only meaningful for CI builds triggered by a pull_request event;
        # self.pull_request_id stays None otherwise (see set_base_upload_path).
        if self.pull_request and self.pull_request_id:
            artifact_properties['pr_number'] = self.pull_request_id
        # Only present when RB_VERSIONING is 'git-managed' (see git_version_resolver.py) -
        # absent entirely in static version.json mode, rather than a misleading default.
        commits_ahead = os.environ.get('RB_COMMITS_AHEAD')
        if commits_ahead is not None:
            artifact_properties['commits_ahead'] = commits_ahead
        full_version_tag = os.environ.get('RB_FULL_VERSION_TAG')
        if full_version_tag:
            artifact_properties['full_version_tag'] = full_version_tag
        return artifact_properties

    @staticmethod
    def _resolve_release_status(artifact_properties: Dict[str, Any]) -> str:
        """Resolve release status while preserving explicit release branch intent.

        Tag-push and pull-request uploads use the channel calculated from their
        GitHub context. A non-PR branch upload retains its configured release
        status only when ``release_status_override`` is explicitly ``True``.
        This supports release workflows that create a tag and upload in the
        same branch-push run without changing the default channel behavior.
        """
        channel_status = os.environ.get('XC_CE_UTILS_RELEASE_STATUS', 'local').lower()
        github_ref = os.getenv('GITHUB_REF', '')
        github_head_ref = os.getenv('GITHUB_HEAD_REF', '')
        configured_status = artifact_properties.get('release_status')
        release_status_override = artifact_properties.pop('release_status_override', False)

        if github_ref.startswith('refs/tags/') or github_head_ref:
            return channel_status

        if (
            release_status_override is True
            and isinstance(configured_status, str)
            and configured_status.strip()
        ):
            return configured_status.strip().lower()

        return channel_status

    def _resolve_glob_deployment_path(
        self, deployment_path: str, temp_folder: Path
    ) -> Optional[str]:
        """Resolve a glob-pattern deployment path into a staged temp folder.

        Returns the new ``deployment_path`` (the temp folder) or ``None`` when the
        glob matched no files (caller should ``continue`` to the next deployment).
        """
        temp_folder.mkdir(parents=True, exist_ok=True)

        deployment_paths = list(self.repo_root.glob(deployment_path))
        if not deployment_paths:
            logger.warning(f'No files found matching glob pattern: {deployment_path}')
            return None

        for path in deployment_paths:
            # Copying folders and files to the deploy folder
            if path.is_dir():
                resolved_deployment_path = str(path.resolve())
                deploy_artifact_path = f'{temp_folder!s}/{path.name}'
                shutil.copytree(
                    resolved_deployment_path,
                    deploy_artifact_path,
                    dirs_exist_ok=True,
                )
            elif path.is_file():
                deploy_artifact_path = f'{temp_folder!s}/{path.name}'
                shutil.copy2(path, deploy_artifact_path)

        return str(temp_folder)

    def _prepare_artifact_for_upload(
        self, deployment_path: str, *, to_zip: bool, deployment: Dict[str, Any]
    ) -> Tuple[Path, str, bool]:
        """Zip the staged content when requested; return upload metadata.

        Returns ``(deploy_artifact_path, artifact_name, is_folder)``.
        """
        if to_zip:
            self.deploy_folder.mkdir(parents=True, exist_ok=True)

            zip_file_name = deployment['zip_name']
            zip_folder(
                deployment_path,
                zip_file_name,
                self.deploy_folder,
                use7z=True,
            )

            deploy_artifact_path = self.deploy_folder / f'{zip_file_name}.zip'
            artifact_name = f'{zip_file_name}.zip'
            return deploy_artifact_path, artifact_name, False

        deploy_artifact_path = Path(deployment_path)
        is_folder = deploy_artifact_path.is_dir()
        artifact_name = deploy_artifact_path.name
        return deploy_artifact_path, artifact_name, is_folder

    def _upload_to_artifactories(self, request: _UploadRequest) -> List[Tuple[str, str]]:
        """Upload the prepared artifact to every requested artifactory alias.

        Returns the ``(label, url)`` comment-link entries collected for this
        deployment (always populated — matches the pre-refactor ``include_in_comment``
        flag, which was unconditionally ``True``).
        """
        comment_links: List[Tuple[str, str]] = []

        for artifactory in request.artifactories:
            artifactory_url = self.artifactory_conf[artifactory]['url']
            artifactory_repository = self.artifactory_conf[artifactory]['repository']
            logger.info(f" Uploading to artifactory '{artifactory}'")
            logger.info(f'   URL: {artifactory_url}')
            logger.info(f'   Repository: {artifactory_repository}')

            jfrog_deployer = ArtifactoryUploader(artifactory_url, artifactory_repository)

            if request.to_zip:
                jfrog_deployer.upload_file(
                    request.deploy_artifact_path,
                    f'{request.target_path}/{request.artifact_name}',
                    request.artifact_properties,
                )
            elif request.is_folder:
                jfrog_deployer.upload_folder(
                    request.deploy_artifact_path,
                    request.target_path,
                    request.artifact_properties,
                )
            else:
                jfrog_deployer.upload_file(
                    request.deploy_artifact_path,
                    request.target_path,
                    request.artifact_properties,
                )

            logger.success(f" Successfully uploaded to '{artifactory}'")

            link_target = (
                f'{request.target_path}/{request.artifact_name}'
                if request.to_zip
                else request.target_path
            )
            url = self._build_artifactory_ui_link(
                artifactory_url, artifactory_repository, link_target
            )
            label = f'{request.deployment_name} ({artifactory})'
            comment_links.append((label, url))

        return comment_links

    def _publish_docs_if_tagged(
        self,
        *,
        deployment: Dict[str, Any],
        deployment_path: str,
        artifactories: List[str],
    ) -> None:
        """Publish ``documentation.zip`` alongside the deployment for tag builds."""
        docs_publishing = deployment.get('docs_publishing')
        if not docs_publishing:
            return
        if not self.tag:
            logger.trace(' Docs publishing: skipped (runs only for tag-based PR merge builds)')
            return

        docs_target_path = f'{self.repo_name}/{docs_publishing}'
        self.deploy_folder.mkdir(parents=True, exist_ok=True)
        zip_folder(deployment_path, 'documentation', self.deploy_folder)
        docs_zip_path = self.deploy_folder / 'documentation.zip'

        logger.info(
            f' Docs publishing: uploading documentation.zip to {docs_target_path}/documentation.zip'
        )
        for artifactory in artifactories:
            artifactory_url = self.artifactory_conf[artifactory]['url']
            artifactory_repository = self.artifactory_conf[artifactory]['repository']
            docs_deployer = ArtifactoryUploader(artifactory_url, artifactory_repository)
            docs_deployer.upload_file(
                docs_zip_path,
                f'{docs_target_path}/documentation.zip',
                {},
            )
            logger.success(f" Docs publishing: uploaded to '{artifactory}'")

    def _deploy_single_entry(
        self,
        *,
        deployment_name: str,
        deployment: Dict[str, Any],
        action: str,
        temp_folder: Path,
    ) -> List[Tuple[str, str]]:
        """Validate, stage, upload, and (optionally) publish docs for one deployment entry."""
        (
            to_zip,
            deployment_path,
            repository_full_path,
            artifact_properties,
        ) = self._validate_deployment_params(deployment)

        artifactory_raw = deployment['artifactory']
        artifactories = [a.strip() for a in artifactory_raw.split(',')]

        logger.info(
            f' Deploying to {len(artifactories)} artifactory(ies): {", ".join(artifactories)}'
        )

        artifact_properties = self._build_artifact_properties(artifact_properties, action)

        target_path = (
            str(repository_full_path).strip().strip('/')
            if repository_full_path is not None
            else self.upload_folder
        )
        logger.info(f'TARGET_PATH = {target_path}')

        if '*' in deployment_path:
            resolved_path = self._resolve_glob_deployment_path(deployment_path, temp_folder)
            if resolved_path is None:
                return []
            deployment_path = resolved_path

        deploy_artifact_path, artifact_name, is_folder = self._prepare_artifact_for_upload(
            deployment_path, to_zip=to_zip, deployment=deployment
        )

        comment_links = self._upload_to_artifactories(
            _UploadRequest(
                artifactories=artifactories,
                to_zip=to_zip,
                is_folder=is_folder,
                deploy_artifact_path=deploy_artifact_path,
                target_path=target_path,
                artifact_name=artifact_name,
                artifact_properties=artifact_properties,
                deployment_name=deployment_name,
            )
        )

        self._publish_docs_if_tagged(
            deployment=deployment,
            deployment_path=deployment_path,
            artifactories=artifactories,
        )

        return comment_links

    @classmethod
    def compute_upload_path(
        cls, repo_root: Path, rb_version: str, repo_name: Optional[str] = None
    ) -> str:
        """Return the upload folder of the current CI run without a full Deployer.

        All jobs of one CI run resolve the same folder (same GITHUB_* context and commit),
        so a later job can download what an earlier job uploaded.
        """
        deployer = object.__new__(cls)
        deployer.repo_root = Path(repo_root)
        deployer.repo = Repo(deployer.repo_root)
        deployer.repo_name = repo_name or deployer.repo.remotes.origin.url.split('/')[-1].replace(
            '.git', ''
        )
        deployer.rb_version = rb_version
        deployer.branch_name = None
        deployer.pull_request = False
        deployer.pull_request_id = None
        deployer.tag = None
        deployer.set_base_upload_path()
        return deployer.upload_folder

    def set_base_upload_path(self) -> None:
        """
        Set the base upload path for artifacts based on CI environment.

        This method determines the appropriate upload path structure in Artifactory
        based on the detected CI environment (GitHub Actions, Jenkins, or local).
        It sets different path patterns based on whether the build is from a branch,
        a tag, or a pull request.

        The path includes repository name, branch/tag information, variant information,
        and timestamps or run identifiers depending on the environment.

        Raises:
            Exception: If unable to determine branch information or if
                      an unknown GitHub reference format is detected

        Side Effects:
            - Sets the self.upload_folder attribute with the determined path
            - May update self.branch_name, self.pull_request, self.pull_request_id,
              self.tag attributes based on environment detection
        """
        self.upload_folder = self.repo_name
        # GitHub Actions environments
        github_head_ref = os.getenv('GITHUB_HEAD_REF')
        github_ref = os.getenv('GITHUB_REF')
        scheduled = os.getenv('XC_CE_UTILS_SCHEDULED', '').strip()

        if github_head_ref:
            # GitHub Actions PR source branch
            self.pull_request = True
            self.pull_request_id = github_ref.split('/')[2] if github_ref else None
            run_number = os.getenv('GITHUB_RUN_NUMBER')
            if not run_number:
                error_msg = (
                    'Missing GITHUB_RUN_NUMBER for GitHub Actions PR build. '
                    'Ensure this is running in a GitHub Actions environment.'
                )
                raise Exception(error_msg)

            version_segment = self._build_version_folder_segment(self.rb_version)
            self.upload_folder = (
                f'{self.upload_folder}/PRs/{github_head_ref}/GH{run_number}/{version_segment}'
            )
        else:
            if scheduled and not (github_ref or '').startswith('refs/tags/'):
                run_number = os.getenv('GITHUB_RUN_NUMBER')
                if not run_number:
                    error_msg = (
                        'Missing GITHUB_RUN_NUMBER for GitHub Actions scheduled build. '
                        'Ensure this is running in a GitHub Actions environment.'
                    )
                    raise Exception(error_msg)

                if github_ref and github_ref.startswith('refs/heads/'):
                    self.branch_name = github_ref.replace('refs/heads/', '')
                version_segment = self._build_version_folder_segment(self.rb_version)
                self.upload_folder = (
                    f'{self.upload_folder}/{scheduled}/{version_segment}/GH{run_number}'
                )
                return

            if not github_ref:
                error_msg = (
                    'Missing GITHUB_REF for GitHub Actions build. '
                    'Ensure this is running in a GitHub Actions environment.'
                )
                raise Exception(error_msg)

            non_pr_tag = self._resolve_non_pr_tag(github_ref)
            if non_pr_tag:
                self.tag = non_pr_tag
                logger.info(f'TAG={self.tag}')
                branch_folder = self._commits_ahead_folder(github_ref, non_pr_tag)
                if branch_folder:
                    self.upload_folder = f'{self.upload_folder}/{branch_folder}'
                    return
                version_segment = self._build_version_folder_segment(
                    self.rb_version,
                    display_name=self.tag,
                )
                self.upload_folder = f'{self.upload_folder}/tags/{version_segment}'
                return

            # No reachable vX.Y.Z tag anywhere in history: fall back to a branch/run path
            # instead of failing the deploy.
            run_id = os.getenv('GITHUB_RUN_ID')
            if not run_id:
                error_msg = (
                    'Missing GITHUB_RUN_ID for GitHub Actions build. '
                    'Ensure this is running in a GitHub Actions environment.'
                )
                raise Exception(error_msg)

            if github_ref.startswith('refs/heads/'):
                self.branch_name = github_ref.replace('refs/heads/', '')
            version_segment = self._build_version_folder_segment(self.rb_version)
            self.upload_folder = (
                f'{self.upload_folder}/{self.branch_name}/{version_segment}_GH{run_id}'
            )

    # Glob (not regex) pattern accepted by `git tag --list` / `git describe --match`.
    _TAG_GLOB = 'v[0-9]*.[0-9]*.[0-9]*'
    # Matches the same shape in Python: vX.Y.Z with an optional -<suffix> (e.g. -dev, -rel).
    _TAG_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.]+))?$')

    def _commits_ahead_folder(self, github_ref: str, non_pr_tag: str) -> Optional[str]:
        """Return ``<branch>/<version>/<commits ahead>`` for a push ahead of the last tag, else None.

        Needs RB_COMMITS_AHEAD (git-managed versioning); without it, or on the tagged commit
        itself, the upload goes to the tags folder.
        """
        if github_ref.startswith('refs/tags/'):
            return None
        commits_ahead = os.environ.get('RB_COMMITS_AHEAD', '').strip()
        if not commits_ahead.isdigit() or int(commits_ahead) == 0:
            return None
        branch = os.environ.get('XC_CE_UTILS_BRANCH_NAME', '').strip()
        if not branch and github_ref.startswith('refs/heads/'):
            branch = github_ref.replace('refs/heads/', '')
        if not branch:
            return None
        self.branch_name = branch
        # git describe adds the count to the tag (v1.0.7-30); the folder keeps the plain tag
        base_tag = re.sub(rf'-{int(commits_ahead)}$', '', non_pr_tag)
        version_segment = self._build_version_folder_segment(self.rb_version, display_name=base_tag)
        return f'{branch}/{version_segment}/{int(commits_ahead)}'

    def _resolve_non_pr_tag(self, github_ref: Optional[str]) -> Optional[str]:
        """Resolve tag for non-PR uploads.

        Priority:
        1. Explicit tag event from GITHUB_REF (refs/tags/*), if it matches vX.Y.Z(-suffix)
        2. Highest-semver vX.Y.Z(-suffix) tag pointing at current HEAD
        3. Last reachable vX.Y.Z(-suffix) tag from current commit (git describe), with the
           trailing commit hash stripped (count kept, e.g. "v2.4.6-5")
        """
        if github_ref and github_ref.startswith('refs/tags/'):
            explicit_tag = github_ref.replace('refs/tags/', '')
            if self._parse_semver_tag(explicit_tag):
                return explicit_tag
            return None

        # git-managed versioning exports the (per-variant) tag glob, so each variant only sees its series
        tag_glob = os.environ.get('RB_VERSION_PATTERN', '').strip() or self._TAG_GLOB
        ref = describe_ref(self.repo_root)
        try:
            tags_at_head = (
                self.repo.git.tag('--points-at', ref, '--list', tag_glob).strip().splitlines()
            )
            tags_at_head = [tag.strip() for tag in tags_at_head if tag.strip()]
            best_tag = self._pick_highest_semver_tag(tags_at_head)
            if best_tag:
                return best_tag

            described = self.repo.git.describe(
                '--tags',
                '--long',
                '--match',
                tag_glob,
                *([ref] if ref != 'HEAD' else []),
            ).strip()
            return self._strip_commit_hash(described)
        except Exception:
            return None

    @classmethod
    def _parse_semver_tag(cls, tag: str) -> Optional[Tuple[int, int, int, str]]:
        """Parse a vX.Y.Z(-suffix) tag into (major, minor, patch, suffix), or None if it doesn't match."""
        match = cls._TAG_RE.fullmatch(tag)
        if not match:
            return None
        major, minor, patch, suffix = match.groups()
        return int(major), int(minor), int(patch), suffix or ''

    @classmethod
    def _pick_highest_semver_tag(cls, tags: List[str]) -> Optional[str]:
        """Pick the highest-semver vX.Y.Z(-suffix) tag from a list, ignoring non-matching entries.

        Ties on (major, minor, patch) prefer the bare tag (no suffix) over a suffixed one,
        then fall back to alphabetical order.
        """
        candidates = []
        for tag in tags:
            parsed = cls._parse_semver_tag(tag)
            if parsed:
                major, minor, patch, suffix = parsed
                # bare tags (no suffix) should win ties over suffixed ones
                candidates.append(((major, minor, patch, not suffix, suffix), tag))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    @staticmethod
    def _strip_commit_hash(described: str) -> Optional[str]:
        """Strip the trailing "-g<hash>" from a `git describe --long` result, keeping "<tag>-<count>"."""
        if not described:
            return None
        return re.sub(r'-g[0-9a-f]+$', '', described) or None

    @staticmethod
    def _build_version_folder_segment(version: str, display_name: Optional[str] = None) -> str:
        """Build a lexically sortable folder segment from semantic version."""
        cleaned = str(version).strip()
        sort_key = Deployer._build_semver_sort_key(cleaned)
        label_source = cleaned if display_name is None else str(display_name)
        readable = re.sub(r'[^0-9A-Za-z._-]+', '_', label_source.strip())
        return f'{sort_key}__{readable}'

    @staticmethod
    def _build_semver_sort_key(version: str) -> str:
        """Convert semantic version to sortable key with 4-digit components."""
        match = re.fullmatch(
            r'[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?',
            version,
        )
        if not match:
            error_msg = f'RB version must be semantic (got: {version!r})'
            raise ValueError(error_msg)

        major = int(match.group(1))
        minor = int(match.group(2) or 0)
        patch = int(match.group(3) or 0)
        return f'{major:04d}.{minor:04d}.{patch:04d}'

    @staticmethod
    def _build_artifactory_ui_link(artifactory_url: str, repository: str, target_path: str) -> str:
        base_url = artifactory_url.rstrip('/')
        if '/artifactory' in base_url:
            base_url = base_url.split('/artifactory')[0]

        return f'{base_url}/ui/repos/tree/General/{repository}/{target_path}'

    # Hidden HTML marker used to identify the consolidated deploy comment
    _COMMENT_MARKER = '<!-- xc-ce-deploy-artifacts -->'

    def _find_existing_deploy_comment(
        self, comments_url: str, headers: Dict[str, str]
    ) -> Tuple[Optional[int], Optional[str]]:
        """Search PR comments for an existing deploy-artifacts comment.

        Paginates through the issue comments (up to 10 pages of 100) looking
        for a comment whose body contains the hidden HTML marker.

        Args:
            comments_url: GitHub API URL for listing issue comments.
            headers: HTTP headers including authorization.

        Returns:
            A tuple of ``(comment_id, body)`` if found, otherwise ``(None, None)``.
        """

        url: Optional[str] = f'{comments_url}?per_page=100'
        for _ in range(10):  # safety cap on pagination
            if url is None:
                break
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code not in HTTP_POSITIVE_RESPONSE_CODES:
                    logger.warning(f'Failed to list PR comments ({resp.status_code})')
                    return None, None
                for comment in resp.json():
                    if self._COMMENT_MARKER in (comment.get('body') or ''):
                        return comment['id'], comment['body']
                # Follow pagination via Link header
                url = self._next_page_url(resp.headers.get('Link'))
            except requests.RequestException as exc:
                logger.warning(f'Failed to search PR comments: {exc}')
                return None, None
        return None, None

    @staticmethod
    def _next_page_url(link_header: Optional[str]) -> Optional[str]:
        """Extract the ``next`` page URL from a GitHub ``Link`` header."""
        if not link_header:
            return None
        for part in link_header.split(','):
            if 'rel="next"' in part:
                match = re.search(r'<([^>]+)>', part)
                if match:
                    return match.group(1)
        return None

    @staticmethod
    def _build_comment_body(
        existing_body: Optional[str],
        action_name: str,
        variant: str,
        links: List[Tuple[str, str]],
    ) -> str:
        """Build (or update) the consolidated PR comment body.

        Each action/variant combination gets its own section delimited by HTML
        markers.  If *existing_body* already contains a section for the given
        action+variant it is **replaced**; otherwise a new section is appended.

        Args:
            existing_body: Current comment body, or ``None`` for a fresh comment.
            action_name: Lowercase action name (e.g. ``build``).
            variant: Variant string (may be empty).
            links: List of ``(label, url)`` tuples for Artifactory UI links.

        Returns:
            The full markdown body ready to be posted/patched.
        """
        marker = Deployer._COMMENT_MARKER
        section_key = f'{action_name}:{variant}' if variant else action_name
        open_tag = f'<!-- section:{section_key} -->'
        close_tag = f'<!-- /section:{section_key} -->'

        # Build the section content
        run_number = os.getenv('GITHUB_RUN_NUMBER', '')
        heading = f'### `{action_name}`'
        if variant:
            heading += f' (variant `{variant}`)'
        if run_number:
            heading += f' -- PR Run #{run_number}'

        link_lines = '\n'.join(f'- [{label}]({url})' for label, url in links)
        section = f'{open_tag}\n{heading}\n{link_lines}\n{close_tag}'

        if existing_body and marker in existing_body:
            # Replace existing section or append new one
            pattern = re.compile(
                re.escape(open_tag) + r'.*?' + re.escape(close_tag),
                re.DOTALL,
            )
            if pattern.search(existing_body):
                return pattern.sub(section, existing_body)
            # Section for this action+variant doesn't exist yet — append
            return f'{existing_body}\n\n{section}'

        # Brand-new comment
        return f'{marker}\n## Artifactory Deploy Artifacts\n\n{section}'

    @staticmethod
    def _fetch_single_comment(
        api_url: str, repo: str, comment_id: int, headers: Dict[str, str]
    ) -> Optional[str]:
        """Fetch the current body of a single comment by its ID.

        This is cheaper than listing all comments and avoids pagination.
        Used to get the freshest body right before a PATCH.
        """

        url = f'{api_url}/repos/{repo}/issues/comments/{comment_id}'
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code in HTTP_POSITIVE_RESPONSE_CODES:
                return resp.json().get('body')
            logger.warning(f'Failed to fetch comment {comment_id} ({resp.status_code})')
        except requests.RequestException as exc:
            logger.warning(f'Failed to fetch comment {comment_id}: {exc}')
        return None

    def _post_github_pr_comment(self, links: List[Tuple[str, str]]) -> None:
        """Post or update a consolidated PR comment with Artifactory links.

        Instead of creating a new comment on every deploy call, this method
        searches for an existing comment (identified by a hidden HTML marker)
        and updates it.  Each action/variant combination is kept in its own
        section so parallel jobs can contribute to the same comment.

        To handle parallel CI jobs updating the same comment, the method uses
        a retry loop: on each attempt it re-fetches the latest comment body
        before merging in the new section and PATCHing.  A small random delay
        before the first attempt staggers concurrent jobs.
        """
        if not self.pull_request or not self.pull_request_id:
            return

        repo = os.getenv('GITHUB_REPOSITORY')
        token = os.getenv('GH_PAT') or os.getenv('GITHUB_TOKEN')
        if not repo or not token:
            logger.warning('Skipping PR comment: missing GITHUB_REPOSITORY or GH_PAT/GITHUB_TOKEN')
            return

        api_url = os.getenv('GITHUB_API_URL', 'https://api.github.com').rstrip('/')
        comments_url = f'{api_url}/repos/{repo}/issues/{self.pull_request_id}/comments'

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
        }

        action_name = self.build_conf.action.lower()
        variant = os.getenv('XC_CE_UTILS_VARIANT', '')

        # Random jitter (0-3s) to stagger parallel jobs hitting the API
        jitter = random.uniform(0, 3)
        logger.debug(f'PR comment jitter: {jitter:.1f}s')
        time.sleep(jitter)

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if self._attempt_post_pr_comment(
                _PrCommentAttempt(
                    comments_url=comments_url,
                    api_url=api_url,
                    repo=repo,
                    headers=headers,
                    action_name=action_name,
                    variant=variant,
                    links=links,
                    attempt=attempt,
                    max_retries=max_retries,
                )
            ):
                return

            if attempt < max_retries:
                backoff = attempt * 2 + random.uniform(0, 2)
                logger.info(f'Retrying PR comment in {backoff:.1f}s...')
                time.sleep(backoff)

        logger.warning('PR comment failed after all retries')

    def _attempt_post_pr_comment(self, ctx: _PrCommentAttempt) -> bool:
        """Run a single create-or-update attempt for the PR comment.

        Returns ``True`` on success (caller should stop retrying).
        """
        try:
            # Always fetch the latest state right before writing
            comment_id, existing_body = self._find_existing_deploy_comment(
                ctx.comments_url, ctx.headers
            )
            body = self._build_comment_body(existing_body, ctx.action_name, ctx.variant, ctx.links)

            if comment_id is not None:
                # Re-fetch the single comment for the freshest body to
                # minimise the race window between list and patch
                fresh_body = self._fetch_single_comment(
                    ctx.api_url, ctx.repo, comment_id, ctx.headers
                )
                if fresh_body is not None and fresh_body != existing_body:
                    body = self._build_comment_body(
                        fresh_body, ctx.action_name, ctx.variant, ctx.links
                    )

                patch_url = f'{ctx.api_url}/repos/{ctx.repo}/issues/comments/{comment_id}'
                response = requests.patch(
                    patch_url,
                    headers=ctx.headers,
                    json={'body': body},
                    timeout=30,
                )
            else:
                response = requests.post(
                    ctx.comments_url,
                    headers=ctx.headers,
                    json={'body': body},
                    timeout=30,
                )

            if response.status_code in HTTP_POSITIVE_RESPONSE_CODES:
                verb = 'Updated' if comment_id else 'Created'
                logger.success(f'{verb} PR comment with Artifactory links')
                return True

            logger.warning(
                f'PR comment attempt {ctx.attempt}/{ctx.max_retries} failed '
                f'({response.status_code}): {response.text}'
            )
        except requests.RequestException as exc:
            logger.warning(f'PR comment attempt {ctx.attempt}/{ctx.max_retries} failed: {exc}')

        return False
