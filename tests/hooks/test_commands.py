"""Exercise the built-ins against real Git and a local pre-commit hook."""

import json
import shlex
import sys

import pytest
import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.test_command_access import snapshot

from .conftest import git, invoke, repository
from .test_installation import hook_path


def test_help_inventory_and_status_have_no_side_effects(tmp_path, offline_engine):
    root = repository(tmp_path / "repo")
    before = snapshot(root)
    commands = {"run", "check", "install", "uninstall", "status", "validate"}
    for args in [[], ["--help"], *[[name, "--help"] for name in commands]]:
        result = invoke(root, "pre-commit", *args)
        assert result.exit_code == 0, result.output
    inventory = invoke(root, "describe", "--json")
    tree = json.loads(inventory.output)["projects"][0]["commands"]
    group = next(c for c in tree if c["name"] == "pre-commit")
    assert {c["name"] for c in group["children"]} == commands
    result = invoke(root, "pre-commit", "status")
    assert result.exit_code == 1 and "missing or unusable" in result.output
    assert snapshot(root) == before
    assert offline_engine == []


def test_install_uninstall_restores_legacy_and_all_configured_types(tmp_path):
    root = repository(tmp_path / "repo", output="config/commit checks.yaml")
    config = root / "config/commit checks.yaml"
    data = yaml.safe_load(config.read_text())
    data["default_install_hook_types"] = ["pre-commit", "pre-push"]
    config.write_text(yaml.safe_dump(data))
    before = config.read_bytes()
    previous = "#!/bin/sh\necho legacy-check\n"
    hook = hook_path(root)
    hook.write_text(previous)
    hook.chmod(0o755)
    result = invoke(root, "pre-commit", "install")
    assert result.exit_code == 0, result.output
    assert hook_path(root, "pre-push").is_file()
    assert invoke(root, "pre-commit", "status").exit_code == 0
    result = invoke(root, "pre-commit", "uninstall")
    assert result.exit_code == 0, result.output
    assert "next local job" in result.output
    assert hook.read_text() == previous
    assert not hook_path(root, "pre-push").exists()
    assert not hook.with_name("pre-commit.legacy").exists()
    assert config.read_bytes() == before
    assert not (root / "hook-ran").exists()
    assert not (root / "job-ran").exists()
    # An unrelated hook remains untouched on repeated uninstall.
    assert invoke(root, "pre-commit", "uninstall").exit_code == 0
    assert hook.read_text() == previous


def test_run_selects_staged_all_explicit_files_and_refs(tmp_path):
    root = repository(tmp_path / "repo with spaces")
    config = root / ".pre-commit-config.yaml"
    data = yaml.safe_load(config.read_text())
    hook = data["repos"][0]["hooks"][0]
    hook.update(always_run=False, pass_filenames=True, files=r"\.txt$")
    hook["entry"] = shlex.join(
        [
            sys.executable,
            "-c",
            "import json, sys; from pathlib import Path; Path('selected.json').write_text(json.dumps(sys.argv[1:]))",
        ]
    )
    config.write_text(yaml.safe_dump(data))
    for name in ("staged.txt", "other name.txt", "-dash.txt"):
        (root / name).write_text("before\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    initial = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "staged.txt").write_text("staged change\n")
    git(root, "add", "staged.txt")
    (root / "other name.txt").write_text("unstaged change\n")

    def selected(*args):
        result = invoke(root, "pre-commit", *args)
        assert result.exit_code == 0, result.output
        return set(json.loads((root / "selected.json").read_text()))

    assert selected("run", "proof") == {"staged.txt"}
    assert (root / "other name.txt").read_text() == "unstaged change\n"
    assert selected("check") == {"staged.txt", "other name.txt", "-dash.txt"}
    assert selected("run", "proof", "--file", "other name.txt", "--file=-dash.txt") == {
        "other name.txt",
        "-dash.txt",
    }
    git(root, "commit", "-m", "staged change")
    assert selected("run", "--from-ref", initial, "--to-ref", "HEAD") == {"staged.txt"}
    assert not hook_path(root).exists()
    assert not (root / "job-ran").exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--all-files", "--file", "file.txt"],
        ["--from-ref", "HEAD"],
        ["--to-ref", "HEAD"],
        ["--all-files", "--from-ref", "HEAD", "--to-ref", "HEAD"],
        ["--file", "../outside.txt"],
    ],
)
def test_invalid_selections_fail_before_runtime_setup(tmp_path, offline_engine, args):
    root = repository(tmp_path / "repo")
    before = snapshot(root)
    result = invoke(root, "pre-commit", "run", *args)
    assert result.exit_code == 2, result.output
    assert not offline_engine
    assert snapshot(root) == before


def test_failed_hooks_return_their_exit_code_without_running_a_job(tmp_path):
    root = repository(tmp_path / "repo")
    (root / "block-commit").touch()
    result = invoke(root, "pre-commit", "check", "proof")
    assert result.exit_code == 1, result.output
    assert "Failed" in result.output
    assert (root / "hook-ran").exists()
    assert not (root / "job-ran").exists()
    assert not hook_path(root).exists()


def test_validate_uses_framework_schema_without_running_hooks(tmp_path):
    root = repository(tmp_path / "repo")
    result = invoke(root, "pre-commit", "validate")
    assert result.exit_code == 0, result.output
    assert "configuration is valid" in result.output
    config = root / ".pre-commit-config.yaml"
    data = yaml.safe_load(config.read_text())
    del data["repos"][0]["hooks"][0]["entry"]
    config.write_text(yaml.safe_dump(data))
    before = config.read_bytes()
    result = invoke(root, "pre-commit", "validate")
    assert result.exit_code != 0 and "entry" in result.output
    assert config.read_bytes() == before
    assert not hook_path(root).exists()
    assert not (root / "hook-ran").exists()


@pytest.mark.parametrize("mode", ["disabled", "unmanaged", "ci"])
def test_explicit_checks_work_without_automatic_installation(tmp_path, mode):
    root = repository(tmp_path / "repo", enabled=False)
    if mode == "unmanaged":
        path = root / "config/project.ptk.yml"
        data = yaml.safe_load(path.read_text())
        del data["configs"]
        path.write_text(yaml.safe_dump(data))
    if mode == "ci":
        result = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
            cli, ["-c", str(root / ".main.ptk.yml"), "pre-commit", "check"]
        )
    else:
        result = invoke(root, "pre-commit", "check")
    assert result.exit_code == 0, result.output
    assert not hook_path(root).exists()
    assert (root / "hook-ran").exists()


def test_custom_hooks_path_allows_checks_but_blocks_hook_mutations(tmp_path):
    root = repository(tmp_path / "repo")
    custom = root / "custom-hooks"
    custom.mkdir()
    original = custom / "pre-commit"
    original.write_text("custom hook\n")
    git(root, "config", "core.hooksPath", str(custom))
    assert invoke(root, "pre-commit", "check").exit_code == 0
    for action in ("install", "uninstall"):
        result = invoke(root, "pre-commit", action)
        assert result.exit_code == 2 and "core.hooksPath" in result.output
    assert original.read_text() == "custom hook\n"


def test_group_policy_hides_commands_and_refuses_mutations(tmp_path, offline_engine):
    root = repository(tmp_path / "repo")
    config = root / "config/project.ptk.yml"
    data = yaml.safe_load(config.read_text())
    data["command_audience"] = {"pre-commit": "maintainer"}
    config.write_text(yaml.safe_dump(data))
    before = snapshot(root)
    for action in ("install", "uninstall", "run", "check", "validate", "status"):
        result = invoke(root, "pre-commit", action)
        assert result.exit_code == 2 and "maintainer-only" in result.output
    doc = json.loads(invoke(root, "describe", "--json").output)
    assert "pre-commit" not in {c["name"] for c in doc["projects"][0]["commands"]}
    assert snapshot(root) == before
    assert not offline_engine


def test_vmr_commands_use_only_the_selected_member(tmp_path, monkeypatch):
    a = repository(tmp_path / "a", alias="alpha")
    b = repository(tmp_path / "b", alias="beta")
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [a, b]\n")
    monkeypatch.chdir(tmp_path)
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli, ["alpha", "pre-commit", "check"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert (a / "hook-ran").exists() and not (b / "hook-ran").exists()
    assert not hook_path(a).exists() and not hook_path(b).exists()


def test_worktree_checks_use_its_files_and_uninstall_shared_hooks(tmp_path):
    root = repository(tmp_path / "original")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    linked = tmp_path / "linked"
    git(root, "worktree", "add", "-b", "linked", str(linked))
    assert invoke(root, "pre-commit", "install").exit_code == 0
    result = invoke(linked, "pre-commit", "check")
    assert result.exit_code == 0, result.output
    assert (linked / "hook-ran").exists() and not (root / "hook-ran").exists()
    result = invoke(linked, "pre-commit", "uninstall")
    assert result.exit_code == 0, result.output
    assert not hook_path(root).exists()
