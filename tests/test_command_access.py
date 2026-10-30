"""Maintainer command visibility and denial through real CLI entry points."""

import re
from pathlib import Path

import pytest
import yaml
from click.shell_completion import BashComplete
from rich.text import Text

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project, write_workflows
from tests.test_workspace import workspace

MUTATIONS = [
    ["maintainer", "sync", "configs"],
    ["maintainer", "sync", "configs", "--diff"],
    ["maintainer", "sync", "tasks"],
    ["maintainer", "sync", "agent", "--check"],
    ["maintainer", "config", "show"],
    ["maintainer", "version", "generate"],
    ["maintainer", "artifacts", "destination", "--job", "build"],
]


def project(root, **extra):
    path = root / ".main.ptk.yml"
    write_project(
        path,
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "access"},
                "configs": {"ruff": {}},
                "variants": {"variants": {"default": {}}},
                **extra,
            }
        ),
    )
    return path


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("args", MUTATIONS)
@pytest.mark.parametrize("forced", ["user", "maintainer"])
def test_mutation_commands_denied_before_side_effects(tmp_path, args, forced):
    config = project(
        tmp_path, command_audience={"maintainer.sync": "all", "variant": "all"}
    )
    before = snapshot(tmp_path)
    result = CliRunner(env={"PTK_ROLE": forced}).invoke(
        cli, [*args], cwd=Path(config).parent
    )
    assert result.exit_code != 0 and "maintainer-only" in result.output, result.output
    assert snapshot(tmp_path) == before


def test_normal_help_html_and_completion_exclude_mutations(tmp_path, monkeypatch):
    config = project(tmp_path)
    # Direct Click completion does not run inside CliRunner's cwd/env isolation.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PTK_ROLE", "user")
    monkeypatch.setenv("PTK_CI", "0")
    runner = CliRunner(env={"PTK_ROLE": "user"})
    base = []
    for group, hidden, shown in [
        ([], ["maintainer", "describe", "run"], ["self-service", "validate", "init"]),
        (
            ["self-service"],
            ["config", "sync", "init"],
            ["tools", "creds", "doctor", "hooks"],
        ),
        (["variant"], ["set", "new", "gui", "check"], ["list", "show", "explain"]),
    ]:
        result = runner.invoke(cli, [*base, *group, "--help"], cwd=Path(config).parent)
        assert result.exit_code == 0, result.output
        text = Text.from_ansi(result.output).plain
        for name in hidden:
            assert not re.search(rf"(?m)^\s*[│|]?\s*{name}\s{{2,}}", text), text
        for name in shown:
            assert name in text
        complete = BashComplete(cli, {}, "ptk", "_PTK_COMPLETE")
        values = {item.value for item in complete.get_completions([*base, *group], "")}
        assert not values.intersection(hidden)
        assert set(shown) <= values
    out = tmp_path / "help.html"
    result = runner.invoke(
        cli, [*base, "help", "--no-open", "-o", str(out)], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    html = out.read_text()
    for command in (
        "maintainer sync configs",
        "setup self",
        "setup vscode",
        "variant new",
        "variant set",
        "variant gui",
    ):
        assert f"ptk {command}" not in html
    for args in MUTATIONS:
        result = runner.invoke(cli, [*base, *args, "--help"], cwd=Path(config).parent)
        assert result.exit_code != 0 and "maintainer-only" in result.output


def test_missing_or_invalid_configuration_does_not_expose_mutations(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "maintainer"})
    for config in (
        None,
        "broken: config",
        "project: {name: test}\nrepository: {alias: test, config_path: .}",
    ):
        base = []
        if config:
            (tmp_path / ".main.ptk.yml").write_text(config)
            (tmp_path / "maintainers.ptk.yml").write_text(
                "maintainers: [{user: old-schema}]"
            )
            base = []
        for args in (
            ["maintainer", "sync", "configs"],
            ["maintainer", "--help"],
        ):
            result = runner.invoke(cli, [*base, *args], cwd=tmp_path)
            assert result.exit_code != 0, result.output
            assert (
                "maintainer-only" in result.output
                or "entry file requires" in result.output
            )
        help_result = runner.invoke(cli, [*base, "--help"], cwd=tmp_path)
        assert help_result.exit_code == 0, help_result.output
        assert "vscode" not in help_result.output


def test_listed_user_can_edit_but_downgrade_cannot(tmp_path):
    config = project(tmp_path)
    grant_maintainer(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": ""})
    base = []
    assert (
        "maintainer"
        in runner.invoke(cli, [*base, "--help"], cwd=Path(config).parent).output
    )
    result = runner.invoke(
        cli, [*base, "maintainer", "sync", "configs"], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "ruff-base.toml").exists()
    before = snapshot(tmp_path)
    result = runner.invoke(
        cli,
        [*base, "maintainer", "sync", "configs"],
        env={"PTK_ROLE": "user"},
        cwd=Path(config).parent,
    )
    assert result.exit_code != 0 and "maintainer-only" in result.output
    assert snapshot(tmp_path) == before


def test_explicit_policy_protects_self_service_operations(tmp_path):
    config = project(
        tmp_path,
        command_audience={
            "self-service.creds": "maintainer",
            "self-service.tools": "maintainer",
        },
    )
    runner = CliRunner(env={"PTK_ROLE": "user"})
    base = []
    for args in (
        ["self-service", "creds", "list"],
        ["self-service", "creds", "list"],
        ["self-service", "tools", "--dry-run"],
        ["self-service", "tools", "--dry-run"],
    ):
        result = runner.invoke(cli, [*base, *args], cwd=Path(config).parent)
        assert result.exit_code != 0 and "maintainer-only" in result.output
    assert (
        "creds"
        not in runner.invoke(
            cli, [*base, "self-service", "--help"], cwd=Path(config).parent
        ).output
    )
    grant_maintainer(tmp_path)
    assert (
        runner.invoke(
            cli,
            [*base, "self-service", "creds", "list"],
            env={"PTK_ROLE": ""},
            cwd=Path(config).parent,
        ).exit_code
        == 0
    )


def test_developer_installation_credentials_and_read_commands_remain_available(
    tmp_path,
):
    config = project(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    for args in (
        ["self-service", "tools", "--allow-system", "--dry-run"],
        ["self-service", "tools", "--dry-run"],
        ["self-service", "creds", "list"],
        ["validate"],
        ["variant", "show"],
    ):
        result = runner.invoke(cli, [*args], cwd=Path(config).parent)
        assert result.exit_code == 0, result.output


def test_vmr_roles_do_not_leak_between_members_or_to_workspace(tmp_path, monkeypatch):
    a, b = workspace(tmp_path)
    grant_maintainer(a.parent)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": ""})
    before = snapshot(tmp_path)
    for prefix in ([], ["bootloader"]):
        assert "maintainer" not in runner.invoke(cli, [*prefix, "--help"]).output
        result = runner.invoke(cli, [*prefix, "maintainer", "sync", "tasks"])
        assert result.exit_code != 0 and "maintainer-only" in result.output
    assert snapshot(tmp_path) == before
    result = runner.invoke(cli, ["firmware", "maintainer", "sync", "tasks"])
    assert result.exit_code == 0, result.output
    assert (a.parent / ".vscode/tasks.json").exists()
    assert not (b.parent / ".vscode").exists()
    grant_maintainer(tmp_path)
    before = snapshot(tmp_path)
    result = runner.invoke(cli, ["maintainer", "sync", "tasks"])
    assert result.exit_code != 0 and "bootloader" in result.output, result.output
    assert (
        snapshot(tmp_path) == before
    )  # preflight before writing even permitted members
    grant_maintainer(b.parent)
    result = runner.invoke(cli, ["maintainer", "sync", "tasks"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".vscode/tasks.json").exists()


def test_vmr_workspace_workflow_needs_its_own_list_and_member_roles(
    tmp_path, monkeypatch
):
    a, _ = workspace(tmp_path)
    fragment = a
    data = read_project(fragment)
    data["jobs"]["build"]["audience"] = "maintainer"
    data["project"].pop("default_job")
    write_project(fragment, data)
    write_workflows(
        (tmp_path / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            "workflows:\n  restricted:\n    audience: maintainer\n    jobs:\n      build:\n        job: firmware:build\n"
        )["workflows"],
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    assert "restricted" not in runner.invoke(cli, ["--help"]).output
    result = runner.invoke(cli, ["restricted", "--help"])
    assert result.exit_code != 0 and "maintainer-only" in result.output
    grant_maintainer(tmp_path)
    assert "restricted" in runner.invoke(cli, ["maintainer", "--help"]).output
    result = runner.invoke(
        cli, ["maintainer", "workflow", "run", "restricted", "--dry-run"]
    )
    assert result.exit_code != 0 and "maintainer-only" in result.output, result.output
    grant_maintainer(a.parent)
    result = runner.invoke(
        cli, ["maintainer", "workflow", "run", "restricted", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
