"""Maintainer command visibility and denial through real CLI entry points."""

import re

import pytest
import yaml
from click.shell_completion import BashComplete
from click.testing import CliRunner
from rich.text import Text

from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer
from tests.test_workspace import workspace

MUTATIONS = [
    ["setup", "configs", "sync"],
    ["configs", "sync", "--diff"],
    ["setup", "self"],
    ["self-setup"],
    ["setup", "vscode"],
    ["vscode", "tasks"],
    ["setup", "vscode", "skills", "--check"],
    ["variant", "new", "other"],
    ["variant", "set", "default"],
    ["variant", "gui"],
]


def project(root, **extra):
    path = root / ".main.ptk.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "access"},
                "configs": {"ruff": {}},
                "variants": {"variants": {"default": {}}},
                **extra,
            }
        )
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
        tmp_path, command_audience={"setup.vscode": "all", "variant": "all"}
    )
    before = snapshot(tmp_path)
    result = CliRunner(env={"PTK_ROLE": forced}).invoke(cli, ["-c", str(config), *args])
    assert result.exit_code != 0 and "maintainer-only" in result.output, result.output
    assert snapshot(tmp_path) == before


def test_normal_help_html_and_completion_exclude_mutations(tmp_path):
    config = project(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    base = ["-c", str(config)]
    for group, hidden, shown in [
        (["setup"], ["vscode", "self"], ["install", "creds", "config", "doctor"]),
        (["setup", "configs"], ["sync"], ["check"]),
        (["variant"], ["set", "new", "gui"], ["list", "show", "check"]),
    ]:
        result = runner.invoke(cli, [*base, *group, "--help"])
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
    result = runner.invoke(cli, [*base, "help", "--no-open", "-o", str(out)])
    assert result.exit_code == 0, result.output
    html = out.read_text()
    for command in (
        "setup configs sync",
        "setup self",
        "setup vscode",
        "variant new",
        "variant set",
        "variant gui",
    ):
        assert f"ptk {command}" not in html
    for args in MUTATIONS:
        result = runner.invoke(cli, [*base, *args, "--help"])
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
            base = ["-c", str(tmp_path / ".main.ptk.yml")]
        for args in (
            ["setup", "self"],
            ["vscode", "--help"],
            ["variant", "new", "other"],
        ):
            result = runner.invoke(cli, [*base, *args])
            assert result.exit_code != 0 and "maintainer-only" in result.output, (
                result.output
            )
        help_result = runner.invoke(cli, [*base, "setup", "--help"])
        assert help_result.exit_code == 0, help_result.output
        assert "vscode" not in help_result.output


def test_listed_user_can_edit_but_downgrade_cannot(tmp_path):
    config = project(tmp_path)
    grant_maintainer(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": ""})
    base = ["-c", str(config)]
    assert "vscode" in runner.invoke(cli, [*base, "setup", "--help"]).output
    result = runner.invoke(cli, [*base, "setup", "configs", "sync"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "ruff-base.toml").exists()
    before = snapshot(tmp_path)
    result = runner.invoke(
        cli, [*base, "variant", "set", "default"], env={"PTK_ROLE": "user"}
    )
    assert result.exit_code != 0 and "maintainer-only" in result.output
    assert snapshot(tmp_path) == before


def test_explicit_policy_still_protects_aliases_and_legacy_setup_dispatch(tmp_path):
    config = project(
        tmp_path,
        command_audience={"setup.creds": "maintainer", "setup.install": "maintainer"},
    )
    runner = CliRunner(env={"PTK_ROLE": "user"})
    base = ["-c", str(config)]
    for args in (
        ["setup", "creds", "list"],
        ["creds", "list"],
        ["setup", "--dry-run"],
        ["setup", "install", "--dry-run"],
    ):
        result = runner.invoke(cli, [*base, *args])
        assert result.exit_code != 0 and "maintainer-only" in result.output
    assert "creds" not in runner.invoke(cli, [*base, "setup", "--help"]).output
    grant_maintainer(tmp_path)
    assert (
        runner.invoke(cli, [*base, "creds", "list"], env={"PTK_ROLE": ""}).exit_code
        == 0
    )


def test_developer_installation_credentials_and_read_commands_remain_available(
    tmp_path,
):
    config = project(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    for args in (
        ["setup", "install", "--allow-system", "--dry-run"],
        ["setup", "--dry-run"],
        ["setup", "creds", "list"],
        ["setup", "config", "validate"],
        ["variant", "show"],
    ):
        result = runner.invoke(cli, ["-c", str(config), *args])
        assert result.exit_code == 0, result.output


def test_vmr_roles_do_not_leak_between_members_or_to_workspace(tmp_path, monkeypatch):
    a, b = workspace(tmp_path)
    grant_maintainer(a.parent)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": ""})
    before = snapshot(tmp_path)
    for prefix in ([], ["bootloader"]):
        assert "vscode" not in runner.invoke(cli, [*prefix, "setup", "--help"]).output
        result = runner.invoke(cli, [*prefix, "setup", "vscode"])
        assert result.exit_code != 0 and "maintainer-only" in result.output
    assert snapshot(tmp_path) == before
    result = runner.invoke(cli, ["firmware", "setup", "vscode", "tasks"])
    assert result.exit_code == 0, result.output
    assert (a.parent / ".vscode/tasks.json").exists()
    assert not (b.parent / ".vscode").exists()
    grant_maintainer(tmp_path)
    before = snapshot(tmp_path)
    result = runner.invoke(cli, ["setup", "vscode"])
    assert result.exit_code != 0 and "bootloader" in result.output, result.output
    assert (
        snapshot(tmp_path) == before
    )  # preflight before writing even permitted members
    grant_maintainer(b.parent)
    result = runner.invoke(cli, ["setup", "vscode", "tasks"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".vscode/tasks.json").exists()


def test_vmr_workspace_workflow_needs_its_own_list_and_member_roles(
    tmp_path, monkeypatch
):
    a, _ = workspace(tmp_path)
    fragment = a.parent / "config/jobs.ptk.yml"
    data = yaml.safe_load(fragment.read_text())
    data["jobs"]["build"]["audience"] = "maintainer"
    fragment.write_text(yaml.safe_dump(data))
    entry = yaml.safe_load(a.read_text())
    entry["project"].pop("default_job")
    a.write_text(yaml.safe_dump(entry))
    (tmp_path / "workflow.ptk.yml").write_text(
        "workflows:\n  restricted:\n    audience: maintainer\n    steps:\n      - build: {repo: firmware, job: build}\n"
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    assert "restricted" not in runner.invoke(cli, ["--help"]).output
    result = runner.invoke(cli, ["restricted", "--help"])
    assert result.exit_code != 0 and "maintainer-only" in result.output
    grant_maintainer(tmp_path)
    assert "restricted" in runner.invoke(cli, ["--help"]).output
    result = runner.invoke(cli, ["workflow", "dry-run", "restricted"])
    assert result.exit_code != 0 and "maintainer-only" in result.output, result.output
    grant_maintainer(a.parent)
    result = runner.invoke(cli, ["workflow", "dry-run", "restricted"])
    assert result.exit_code == 0, result.output
