"""Git-tag-driven ("git-managed") version resolution for RB_VERSIONING.

When ``main_conf.yml``'s ``RB_VERSIONING`` field is the literal string
``git-managed`` (instead of a path to a ``version.json`` file), the project's
MAJOR/MINOR/BUGFIX version is derived from the nearest reachable git tag
matching ``vMAJOR.MINOR.BUGFIX`` (lightweight tags), instead of a manually
maintained static file.

``git-managed:<glob>`` uses a custom tag pattern (``git describe --match``).
``variant-git-managed[:<glob>]`` resolves the version per variant: the variant's
``version`` value is its tag pattern (the glob after the colon, or the default
pattern, is used for variants without ``version``).
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from xc_ce_utils.utils.git_source_commit import describe_ref

RB_VERSIONING_GIT_MANAGED_SENTINEL = 'git-managed'
RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL = 'variant-git-managed'
DEFAULT_TAG_PATTERN = 'v[0-9]*.[0-9]*.[0-9]*'
RB_VERSION_PATTERN_ENV = 'RB_VERSION_PATTERN'

_DESCRIBE_RE = re.compile(r'^(?P<tag>.+)-(?P<ahead>\d+)-g(?P<hash>[0-9a-fA-F]+)$')
_VERSION_IN_TAG_RE = re.compile(r'(\d+)\.(\d+)\.(\d+)')


class GitManagedVersionError(RuntimeError):
    """Raised when git-managed versioning cannot resolve a version."""


def parse_git_managed_versioning(rb_versioning: Any) -> Optional[Tuple[str, str]]:
    """Return ``(mode, tag_pattern)`` for git-managed ``RB_VERSIONING`` values, else None.

    ``mode`` is :data:`RB_VERSIONING_GIT_MANAGED_SENTINEL` or
    :data:`RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL`.
    """
    if not isinstance(rb_versioning, str):
        return None
    mode, _, pattern = rb_versioning.strip().partition(':')
    mode = mode.strip().lower()
    if mode not in {
        RB_VERSIONING_GIT_MANAGED_SENTINEL,
        RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL,
    }:
        return None
    return mode, pattern.strip() or DEFAULT_TAG_PATTERN


def is_git_managed_versioning(rb_versioning: Any) -> bool:
    """Return True if *rb_versioning* selects project-wide git-managed mode.

    ``rb_versioning`` is the raw ``RB_VERSIONING`` config value. It stays an
    unresolved string here specifically because ``git-managed`` doesn't end
    in ``.yml``/``.yaml``/``.json``, so ``ConfigLoader`` never tries to load
    it as a file (unlike a real ``versioning/version.json`` path, which gets
    auto-inlined into a dict before this is ever checked).
    """
    parsed = parse_git_managed_versioning(rb_versioning)
    return parsed is not None and parsed[0] == RB_VERSIONING_GIT_MANAGED_SENTINEL


def is_variant_git_managed_versioning(rb_versioning: Any) -> bool:
    """Return True if *rb_versioning* selects per-variant git-managed mode."""
    parsed = parse_git_managed_versioning(rb_versioning)
    return parsed is not None and parsed[0] == RB_VERSIONING_VARIANT_GIT_MANAGED_SENTINEL


def resolve_git_managed_version(
    repo_root: Path, tag_pattern: str = DEFAULT_TAG_PATTERN
) -> Dict[str, Any]:
    """Compute MAJOR/MINOR/BUGFIX/COMMITS_AHEAD/COMMIT_HASH/IS_DIRTY/VERSION_TAG from git.

    Uses the nearest tag reachable from HEAD matching *tag_pattern* (glob, as
    ``git describe --match``); MAJOR.MINOR.BUGFIX is the first ``X.Y.Z`` in the
    tag name, so prefixed/suffixed tags (``cgw_cs/v1.0.8``) work too. Raises
    :class:`GitManagedVersionError` (with an actionable message) if no tag
    matches - callers should let this fail the build rather than silently
    defaulting to a guessed version.
    """
    ref = describe_ref(repo_root)
    try:
        describe_output = subprocess.run(
            ['git', 'describe', '--tags', '--long', '--match', tag_pattern]
            + ([ref] if ref != 'HEAD' else []),
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or '').strip()
        example_tag = (
            'v0.0.0' if tag_pattern == DEFAULT_TAG_PATTERN else '<tag matching the pattern>'
        )
        raise GitManagedVersionError(
            'RB_VERSIONING is git-managed but no version tag matching '
            f"'{tag_pattern}' was found reachable from HEAD in '{repo_root}'. "
            'Create an initial release tag first, e.g.: '
            f'git tag {example_tag} && git push origin {example_tag}'
            + (f' (git error: {stderr})' if stderr else '')
        ) from exc

    match = _DESCRIBE_RE.match(describe_output)
    version_match = _VERSION_IN_TAG_RE.search(match.group('tag')) if match else None
    if not match or not version_match:
        raise GitManagedVersionError(
            f"Could not parse git describe output '{describe_output}' as "
            '<tag with MAJOR.MINOR.BUGFIX>-COMMITS_AHEAD-gHASH'
        )

    major, minor, bugfix = version_match.groups()

    status_output = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    commit_hash = subprocess.run(
        ['git', 'rev-parse', '--short', ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return {
        'MAJOR_VERSION': int(major),
        'MINOR_VERSION': int(minor),
        'BUGFIX_VERSION': int(bugfix),
        'COMMITS_AHEAD': int(match.group('ahead')),
        'COMMIT_HASH': commit_hash,
        'IS_DIRTY': bool(status_output.strip()),
        'VERSION_TAG': match.group('tag'),
    }


def version_string(version_dict: Dict[str, Any]) -> str:
    """``MAJOR.MINOR.BUGFIX[PRE_RELEASE_SUFFIX]`` of a resolved version dict."""
    return (
        f"{version_dict['MAJOR_VERSION']}."
        f"{version_dict['MINOR_VERSION']}."
        f"{version_dict['BUGFIX_VERSION']}"
        f"{version_dict.get('PRE_RELEASE_SUFFIX', '')}"
    )


def export_git_managed_environment(version_dict: Dict[str, Any], tag_pattern: str) -> None:
    """Export RB_COMMITS_AHEAD/RB_COMMIT_HASH/RB_FULL_VERSION_TAG/RB_VERSION_PATTERN.

    RB_VERSION_PATTERN is also appended to GITHUB_ENV, so later workflow steps
    (e.g. a release job looking up the previous tag of the same series) can use it.
    """
    from xc_ce_utils.global_modules.aux_helper import export_to_github_env  # noqa: PLC0415

    os.environ['RB_COMMITS_AHEAD'] = str(version_dict['COMMITS_AHEAD'])
    os.environ['RB_COMMIT_HASH'] = version_dict['COMMIT_HASH']
    os.environ['RB_FULL_VERSION_TAG'] = (
        f"{version_dict['VERSION_TAG']}-{version_dict['COMMITS_AHEAD']}"
        f"-g{version_dict['COMMIT_HASH']}"
    )
    os.environ[RB_VERSION_PATTERN_ENV] = tag_pattern
    export_to_github_env(RB_VERSION_PATTERN_ENV, tag_pattern)
