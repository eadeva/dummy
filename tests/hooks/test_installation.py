"""Installed hooks run in real Git, including relocated/shared metadata."""

import os
import shlex
import shutil
import venv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from ptk.adapters.hooks import GitHooks
from ptk.adapters.process import SubprocessRunner
from ptk.adapters.python_env import venv_python
from ptk.domain.errors import PtkError

from .conftest import git, invoke, repository


def service():
    return GitHooks(SubprocessRunner(), os.environ, uv="uv")


def hook_path(root, name="pre-commit"):
    return (
        Path(
            git(
                root, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).stdout.strip()
        )
        / "hooks"
        / name
    )


def test_job_installs_for_normal_user_and_git_enforces_hook(tmp_path, offline_engine):
    root = repository(tmp_path / "repo with spaces")
    result = invoke(root, "build")
    assert result.exit_code == 0, result.output
    assert (root / "job-ran").exists()
    assert len(offline_engine) == 1
    assert service().status(root, root / ".pre-commit-config.yaml").installed
    (root / "block-commit").touch()
    git(root, "add", ".main.ptk.yml", ".pre-commit-config.yaml")
    commit = git(root, "commit", "-m", "must be blocked", check=False)
    assert commit.returncode != 0
    assert (root / "hook-ran").exists(), commit.stdout + commit.stderr
    assert "proof" in commit.stdout + commit.stderr
    before = hook_path(root).read_bytes(), hook_path(root).stat().st_mtime_ns
    assert invoke(root, "build").exit_code == 0
    assert len(offline_engine) == 1
    assert before == (hook_path(root).read_bytes(), hook_path(root).stat().st_mtime_ns)


@pytest.mark.parametrize("form", ["gitfile", "symlink", "worktree"])
def test_metadata_forms_and_custom_config_output(tmp_path, form, offline_engine):
    root = repository(tmp_path / "original", output="config/commit hooks.yaml")
    if form == "worktree":
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        linked = tmp_path / "linked"
        git(root, "worktree", "add", "-b", "linked", str(linked))
        original = root
        root = linked
    else:
        metadata = tmp_path / ".repo" / "projects" / "app.git"
        metadata.parent.mkdir(parents=True)
        shutil.move(str(root / ".git"), metadata)
        if form == "gitfile":
            (root / ".git").write_text(
                "gitdir: " + os.path.relpath(metadata, root) + "\n"
            )
        else:
            try:
                (root / ".git").symlink_to(metadata, target_is_directory=True)
            except OSError:
                pytest.skip("directory symlinks unavailable")
    assert invoke(root, "build").exit_code == 0
    assert service().status(root, root / "config/commit hooks.yaml").installed
    if form == "worktree":
        assert (
            service().status(original, original / "config/commit hooks.yaml").installed
        )
    assert len(offline_engine) == 1


def test_repair_deleted_or_broken_interpreter(tmp_path, offline_engine):
    root = repository(tmp_path / "app")
    assert invoke(root, "build").exit_code == 0
    path = hook_path(root)
    text = path.read_text()
    text = (
        "\n".join(
            "INSTALL_PYTHON=/does/not/exist"
            if line.startswith("INSTALL_PYTHON=")
            else line
            for line in text.splitlines()
        )
        + "\n"
    )
    path.write_text(text)
    assert not service().status(root, root / ".pre-commit-config.yaml").installed
    assert invoke(root, "build").exit_code == 0
    path.unlink()
    assert invoke(root, "build").exit_code == 0
    assert len(offline_engine) == 3


def test_existing_python_without_pre_commit_is_repaired(tmp_path, offline_engine):
    root = repository(tmp_path / "app")
    assert invoke(root, "build").exit_code == 0
    empty = tmp_path / "empty-python"
    venv.EnvBuilder(with_pip=False).create(empty)
    hook = hook_path(root)
    hook.write_text(
        "\n".join(
            "INSTALL_PYTHON=" + shlex.quote(str(venv_python(empty)))
            if line.startswith("INSTALL_PYTHON=")
            else line
            for line in hook.read_text().splitlines()
        )
        + "\n"
    )
    assert not service().status(root, root / ".pre-commit-config.yaml").installed
    assert invoke(root, "build").exit_code == 0
    assert len(offline_engine) == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable permissions")
def test_non_executable_hook_is_repaired(tmp_path):
    root = repository(tmp_path / "app")
    assert invoke(root, "build").exit_code == 0
    hook_path(root).chmod(0o644)
    assert not service().status(root, root / ".pre-commit-config.yaml").installed
    assert invoke(root, "build").exit_code == 0
    assert os.access(hook_path(root), os.X_OK)


def test_preserve_existing_hook_and_refuse_backup_collision(tmp_path):
    root = repository(tmp_path / "app")
    hook = hook_path(root)
    old = "#!/bin/sh\necho existing-hook\n"
    hook.write_text(old)
    hook.chmod(0o755)
    assert invoke(root, "build").exit_code == 0
    legacy = hook.with_name("pre-commit.legacy")
    assert legacy.read_text() == old
    hook.write_text("#!/bin/sh\necho another-hook\n")
    (root / "job-ran").unlink()
    result = invoke(root, "build")
    assert result.exit_code == 2 and "conflict" in result.output
    assert not (root / "job-ran").exists()
    assert legacy.read_text() == old
    assert "another-hook" in hook.read_text()


def test_custom_hook_path_is_not_overwritten(tmp_path):
    root = repository(tmp_path / "app")
    custom = root / "custom-hooks"
    custom.mkdir()
    (custom / "pre-commit").write_text("existing")
    git(root, "config", "core.hooksPath", str(custom))
    result = invoke(root, "build")
    assert result.exit_code == 2 and "core.hooksPath" in result.output
    assert (custom / "pre-commit").read_text() == "existing"
    assert not (root / "job-ran").exists()


def test_all_configured_hook_types_are_installed(tmp_path):
    root = repository(tmp_path / "app")
    config = root / ".pre-commit-config.yaml"
    data = yaml.safe_load(config.read_text())
    data["default_install_hook_types"] = ["pre-commit", "pre-push"]
    config.write_text(yaml.safe_dump(data))
    assert invoke(root, "build").exit_code == 0
    assert hook_path(root, "pre-push").is_file()
    hook_path(root, "pre-push").unlink()
    assert not service().status(root, config).installed
    assert invoke(root, "build").exit_code == 0
    assert service().status(root, config).installed


def test_concurrent_installs_share_git_lock(tmp_path, offline_engine):
    root = repository(tmp_path / "app")

    def ensure():
        service().ensure(root, root / ".pre-commit-config.yaml", lambda _: None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(ensure) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)
    assert len(offline_engine) == 1


def test_inherited_git_directory_does_not_redirect_member(tmp_path, monkeypatch):
    other = repository(tmp_path / "other")
    root = repository(tmp_path / "app")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert invoke(root, "build").exit_code == 0
    assert hook_path(root).exists() and not hook_path(other).exists()


def test_non_git_project_fails_without_using_parent_repo(tmp_path):
    root = repository(tmp_path / "parent")
    child = repository(root / "child")
    shutil.rmtree(child / ".git")
    with pytest.raises(PtkError, match="rooted at"):
        service().ensure(child, child / ".pre-commit-config.yaml", lambda _: None)
    assert not hook_path(root).exists()
