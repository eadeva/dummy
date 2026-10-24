"""Commit a checkout was built from, also when CI checked out a GitHub pull request merge commit.

For pull requests GitHub creates a temporary merge commit (``refs/pull/<n>/merge``, message
``Merge <head sha> into <base sha>``) that is on no branch; the PR branch commit is reported instead.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, Union

_PR_MERGE_REF = re.compile(r'(^|/)pull/\d+/merge$')
_PR_MERGE_MESSAGE = re.compile(r'^Merge (?P<head>[0-9a-f]{40}) into [0-9a-f]{40}\s*$')


def _git(root: Union[str, Path], *args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ['git', '-C', str(root), *args],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def pr_merge_head(root: Union[str, Path]) -> Optional[str]:
    """PR branch commit if HEAD is a GitHub pull request merge commit, else None."""
    refs = _git(root, 'for-each-ref', '--points-at', 'HEAD', '--format=%(refname)') or ''
    if not any(_PR_MERGE_REF.search(ref) for ref in refs.splitlines()):
        return None
    match = _PR_MERGE_MESSAGE.match(_git(root, 'log', '-1', '--format=%B', 'HEAD') or '')
    return match.group('head') if match else None


def source_commit(root: Union[str, Path]) -> str:
    """Full hash of HEAD, or of the PR branch commit if HEAD is a GitHub PR merge commit."""
    head = pr_merge_head(root)
    if head:
        return head
    commit = _git(root, 'rev-parse', 'HEAD')
    if not commit:
        raise RuntimeError(f'git rev-parse HEAD failed in {root}')
    return commit


def short_commit(root: Union[str, Path], commit: str, length: Optional[int] = None) -> str:
    """Abbreviated ``commit`` (unique in the repository if its object is available locally)."""
    option = f'--short={length}' if length else '--short'
    return _git(root, 'rev-parse', option, commit) or commit[: length or 7]


def describe_ref(root: Union[str, Path]) -> str:
    """Revision for ``git describe``/``rev-list``: the PR branch commit if available locally, else HEAD."""
    head = pr_merge_head(root)
    if head and _git(root, 'cat-file', '-e', f'{head}^{{commit}}') is not None:
        return head
    return 'HEAD'
