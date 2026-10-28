"""Real local Git repositories, including GitHub's synthetic PR checkout."""

import json
import os
import subprocess

import pytest

from ptk.adapters.git_metadata import GitMetadata
from ptk.adapters.host import SystemHost
from ptk.adapters.process import SubprocessRunner
from ptk.application.use_cases.run import PrepareRun, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import ConfigError, PtkError
from tests.project_files import write_project


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repo(root):
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    (root / "source").write_text("initial\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Initial")
    return git(root, "rev-parse", "HEAD")


def metadata(root, env=None):
    return GitMetadata(
        SubprocessRunner(), SystemHost({**os.environ, **(env or {})})
    ).discover(root)


def pr(root, tmp_path):
    base = repo(root)
    git(root, "checkout", "-qb", "feature/example")
    (root / "head").write_text("PR head\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Head")
    head = git(root, "rev-parse", "HEAD")
    git(root, "tag", "head-tag")
    git(root, "checkout", "-q", "main")
    (root / "base").write_text("Base progress\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Base")
    target = git(root, "rev-parse", "HEAD")
    git(root, "merge", "--no-ff", "-qm", "Synthetic merge", "feature/example")
    merge = git(root, "rev-parse", "HEAD")
    git(root, "tag", "merge-only")
    git(root, "checkout", "--detach", "-q", merge)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"head": {"sha": head, "ref": "feature/example"}}})
    )
    env = {
        "GITHUB_WORKSPACE": str(root),
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_SHA": merge,
        "GITHUB_REF": "refs/pull/7/merge",
    }
    return env, head, merge, target, base


def test_local_branch_exact_tags_short_hash_and_dirty(tmp_path):
    commit = repo(tmp_path)
    first = metadata(tmp_path)
    assert first["commit"] == first["checkout_commit"] == commit
    assert first["short_commit"] == first["short_checkout_commit"] == commit[:12]
    assert first["branch"] == "main"
    assert first["tag"] == "" and first["tags"] == []
    (tmp_path / "untracked").write_text("not a tracked change")
    assert not metadata(tmp_path)["dirty"]
    git(tmp_path, "tag", "z-release")
    git(tmp_path, "tag", "-am", "Annotated", "a-release")
    tagged = metadata(tmp_path)
    assert tagged["tags"] == ["a-release", "z-release"]
    assert tagged["tag"] == "a-release"
    (tmp_path / "source").write_text("changed")
    assert metadata(tmp_path)["dirty"]
    git(tmp_path, "commit", "-qam", "Next")
    assert metadata(tmp_path)["tag"] == ""  # no ancestor-tag fallback
    git(tmp_path, "checkout", "--detach", "-q")
    assert metadata(tmp_path)["branch"] == ""


@pytest.mark.parametrize("event", ["pull_request", "pull_request_target"])
def test_pr_uses_head_identity_and_tags_not_merge_or_base(tmp_path, event):
    root = tmp_path / "repository"
    env, head, merge, target, _ = pr(root, tmp_path)
    if event == "pull_request_target":
        git(root, "checkout", "--detach", "-q", target)
        env.update(
            GITHUB_EVENT_NAME=event, GITHUB_SHA=target, GITHUB_REF="refs/heads/main"
        )
    result = metadata(root, env)
    assert result["commit"] == head
    assert result["short_commit"] == head[:12]
    assert result["checkout_commit"] == (target if event.endswith("target") else merge)
    assert result["branch"] == "feature/example"
    assert result["tag"] == "head-tag" and result["tags"] == ["head-tag"]


def test_pr_metadata_is_required_and_never_replaced_by_merge_sha(tmp_path):
    root = tmp_path / "repository"
    env, *_ = pr(root, tmp_path)
    (tmp_path / "event.json").write_text("{}")
    with pytest.raises(PtkError, match="refusing to substitute"):
        metadata(root, env)


def test_missing_pr_head_object_still_has_identity_without_fetching(tmp_path):
    root = tmp_path / "repository"
    env, *_ = pr(root, tmp_path)
    missing = "a" * 40
    (tmp_path / "event.json").write_text(
        json.dumps({"pull_request": {"head": {"sha": missing, "ref": "unfetched"}}})
    )
    result = metadata(root, env)
    assert result["commit"] == missing and result["short_commit"] == missing[:12]
    assert result["tag"] == "" and result["tags"] == []


def test_event_does_not_leak_into_other_vmr_repositories(tmp_path):
    root = tmp_path / "repository"
    env, *_ = pr(root, tmp_path)
    other = tmp_path / "other"
    commit = repo(other)
    assert metadata(other, env)["commit"] == commit
    assert metadata(other, env)["branch"] == "main"


def test_tag_event_prefers_triggering_tag_and_detached_branch(tmp_path):
    commit = repo(tmp_path)
    git(tmp_path, "tag", "a")
    git(tmp_path, "tag", "z")
    result = metadata(
        tmp_path,
        {
            "GITHUB_WORKSPACE": str(tmp_path),
            "GITHUB_SHA": commit,
            "GITHUB_REF_TYPE": "tag",
            "GITHUB_REF_NAME": "z",
        },
    )
    assert result["tag"] == "z" and result["tags"] == ["a", "z"]
    assert result["branch"] == ""


def test_git_is_lazy_and_cached_across_defaults_vars_environment_and_steps(tmp_path):
    entry = tmp_path / ".main.ptk.yml"
    write_project(
        entry,
        {
            "project": {"name": "demo"},
            "jobs": {"go": {"steps": [{"one": "echo plain"}]}},
        },
    )
    app = create_app(environ={})
    calls = []

    class Reader:
        def discover(self, root):
            calls.append(root)
            return {"commit": "a" * 40, "short_commit": "a" * 12, "tag": ""}

    prepare = PrepareRun(app.host, git=Reader())
    project = app.load_project.execute(config_file=entry)
    prepare.execute(project, RunRequest(job="go", dry_run=True))
    assert calls == []
    write_project(
        entry,
        {
            "project": {"name": "demo"},
            "vars": {"sha": "${git.short_commit}"},
            "environment": {"set": {"SHA": "${git.commit}"}},
            "jobs": {
                "go": {
                    "params": {"sha": {"default": "${git.short_commit}"}},
                    "env": {"TAG": "${git.tag}"},
                    "steps": [
                        {"one": "echo ${git.commit} ${vars.sha}"},
                        {
                            "two": {
                                "uses": "echo",
                                "with": {"message": "${git.short_commit}"},
                            }
                        },
                    ],
                }
            },
        },
    )
    project = app.load_project.execute(config_file=entry)
    plan = prepare.execute(project, RunRequest(job="go", dry_run=True)).plan
    assert calls == [tmp_path]
    assert plan.params["sha"] == "a" * 12
    assert plan.base_env["SHA"] == "a" * 40 and plan.base_env["TAG"] == ""
    assert plan.steps[1].with_["message"] == "a" * 12
    prepare.execute(project, RunRequest(job="go", dry_run=True))
    assert len(calls) == 2  # fresh per run, never stale across invocations


def test_invalid_git_variable_is_rejected_at_load(tmp_path):
    entry = tmp_path / ".main.ptk.yml"
    write_project(entry, {"project": {"name": "demo"}, "vars": {"bad": "${git.comit}"}})
    with pytest.raises(ConfigError, match="unknown name 'git.comit'"):
        create_app(environ={}).load_project.execute(config_file=entry)


def test_commit_only_does_not_scan_worktree_or_tags_and_optional_checks_are_cached(
    tmp_path,
):
    commit = repo(tmp_path)
    commands = []
    actual = SubprocessRunner()

    class RecordingRunner:
        def run(self, command, output):
            commands.append(command.argv)
            return actual.run(command, output)

    values = GitMetadata(RecordingRunner(), SystemHost(dict(os.environ))).discover(
        tmp_path
    )
    assert values["commit"] == commit and values["short_commit"] == commit[:12]
    assert not any(command[1] in {"status", "tag", "cat-file"} for command in commands)
    assert values["tag"] == "" and values["tags"] == [] and values["tag"] == ""
    assert not values["dirty"] and not values["dirty"]
    assert sum(command[1] == "status" for command in commands) == 1
    assert sum(command[1] == "tag" for command in commands) == 1
    assert not any(command[1] in {"fetch", "pull", "ls-remote"} for command in commands)


def test_real_cli_preparation_and_artifact_destinations_resolve_git_without_versioning(
    tmp_path,
):
    commit = repo(tmp_path)
    entry = tmp_path / ".main.ptk.yml"
    write_project(
        entry,
        {
            "project": {"name": "demo"},
            "jobs": {"go": {"steps": [{"one": "echo ${git.short_commit}"}]}},
            "artifactory": {
                "url": "https://example.invalid/artifactory",
                "repository": "builds",
                "events": {"push": {"path": "${git.branch}/${git.short_commit}"}},
            },
        },
    )
    app = create_app(environ=dict(os.environ))
    project = app.load_project.execute(config_file=entry)
    plan = (
        app.prepare_run(project)
        .execute(project, RunRequest(job="go", dry_run=True))
        .plan
    )
    assert plan.steps[0].run == f"echo {commit[:12]}"
    target = app.artifacts().execute(project, job="go", event="push")
    assert target["path"] == f"main/{commit[:12]}"
