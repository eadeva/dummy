"""Read source and checkout identities without fetching or changing Git state."""

import json
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from ..domain.errors import PtkError
from ..domain.execution.model import CommandSpec


class _Facts(Mapping):
    """Keep expensive optional checks lazy even when commit identity is used."""

    def __init__(self, values, deferred):
        self._values, self._deferred = values, deferred

    def __getitem__(self, key):
        if key not in self._values:
            self._values[key] = self._deferred[key]()
        return self._values[key]

    def __iter__(self):
        return iter(self._values.keys() | self._deferred.keys())

    def __len__(self):
        return len(self._values.keys() | self._deferred.keys())


class GitMetadata:
    def __init__(self, runner, host):
        self.runner, self.host = runner, host

    def discover(self, root):
        env = {**self.host.variables, "GIT_OPTIONAL_LOCKS": "0"}

        def git(*args, cwd=root, optional=False):
            output = []
            result = self.runner.run(
                CommandSpec(argv=["git", *args], cwd=str(cwd), env=env, timeout=10),
                output.append,
            )
            if result.exit_code:
                if optional:
                    return None
                raise PtkError(
                    "Git variables require a readable Git checkout with a commit "
                    f"(git {args[0]} failed)."
                )
            return "\n".join(output).strip()

        checkout = git("rev-parse", "--verify", "HEAD")
        top = Path(git("rev-parse", "--show-toplevel")).resolve()
        # GitHub event metadata belongs to the workflow repository, not every
        # other repository in a VMR or an explicitly selected checkout.
        workspace = env.get("GITHUB_WORKSPACE")
        workspace_top = (
            git("rev-parse", "--show-toplevel", cwd=workspace, optional=True)
            if workspace
            else None
        )
        github_repo = bool(workspace_top and Path(workspace_top).resolve() == top)
        if not github_repo and env.get("GITHUB_REPOSITORY"):
            remote = git("config", "--get", "remote.origin.url", optional=True) or ""
            match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
            github_repo = bool(
                match and match[1].lower() == env["GITHUB_REPOSITORY"].lower()
            )
        is_pr = github_repo and (
            env.get("GITHUB_EVENT_NAME", "").startswith("pull_request")
            or env.get("GITHUB_REF", "").startswith("refs/pull/")
        )
        commit = checkout
        branch = git("symbolic-ref", "--quiet", "--short", "HEAD", optional=True) or ""
        if is_pr:
            try:
                payload = json.loads(
                    Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
                )
                head = payload["pull_request"]["head"]
                commit, branch = head["sha"], head["ref"]
                if not isinstance(commit, str) or not re.fullmatch(
                    r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit
                ):
                    raise ValueError("invalid head SHA")
                if (
                    not isinstance(branch, str)
                    or not branch
                    or any(ord(c) < 32 for c in branch)
                ):
                    raise ValueError("invalid head branch")
                commit = commit.lower()
            except (OSError, KeyError, TypeError, ValueError) as exc:
                raise PtkError(
                    "Cannot read pull request head identity from GITHUB_EVENT_PATH; "
                    "refusing to substitute the synthetic merge/base commit."
                ) from exc
        elif github_repo and env.get("GITHUB_SHA", "").lower() == checkout.lower():
            if env.get("GITHUB_REF_TYPE") == "branch":
                branch = env.get("GITHUB_REF_NAME", branch)
            elif env.get("GITHUB_REF_TYPE") == "tag":
                branch = ""

        @cache
        def exact_tags():
            # A PR head can be absent in a shallow merge-only checkout. Its
            # identity still comes from the event; never fetch or invent tags.
            available = (
                git("cat-file", "-e", f"{commit}^{{commit}}", optional=True) is not None
            )
            tags = (
                sorted(filter(None, git("tag", "--points-at", commit).splitlines()))
                if available
                else []
            )
            trigger_tag = ""
            if (
                not is_pr
                and github_repo
                and env.get("GITHUB_REF_TYPE") == "tag"
                and env.get("GITHUB_SHA", "").lower() == commit.lower()
            ):
                trigger_tag = env.get("GITHUB_REF_NAME", "")
                if trigger_tag and trigger_tag not in tags:
                    tags = sorted([*tags, trigger_tag])
            return trigger_tag or next(iter(tags), ""), tags

        return _Facts(
            {
                "branch": branch,
                "commit": commit,
                "short_commit": commit[:12],
                "checkout_commit": checkout,
                "short_checkout_commit": checkout[:12],
            },
            {
                "tag": lambda: exact_tags()[0],
                "tags": lambda: exact_tags()[1],
                "dirty": lambda: bool(
                    git("status", "--porcelain", "--untracked-files=no")
                ),
            },
        )
