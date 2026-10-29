"""Root option permissions and variant selection through real CLI routing."""

import json
from pathlib import Path

import pytest
import yaml
from click.shell_completion import BashComplete

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project
from tests.test_variant_commands import setup
from tests.test_workspace import workspace


@pytest.mark.parametrize("mode", ["--ci", "--no-ci"])
def test_ci_switch_hidden_and_denied_for_user(tmp_path, mode):
    config = setup(tmp_path)
    base = []
    grant_maintainer(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"})
    help_result = runner.invoke(cli, [*base, "--help"], cwd=Path(config).parent)
    assert help_result.exit_code == 0, help_result.output
    assert "--ci" not in help_result.output and "--no-ci" not in help_result.output
    complete = BashComplete(cli, {}, "ptk", "_PTK_COMPLETE")
    with runner.isolation(env={"PTK_ROLE": "user"}):
        values = {i.value for i in complete.get_completions(base, "--")}
    assert not values.intersection({"--ci", "--no-ci"})
    for args in (["go"], ["--help"], ["go", "--help"], ["describe", "--json"]):
        result = runner.invoke(cli, [*base, mode, *args], cwd=Path(config).parent)
        assert result.exit_code != 0 and "maintainer-only option" in result.output
    assert not (tmp_path / "_logs").exists()
    output = tmp_path / "help.html"
    result = runner.invoke(
        cli, [*base, "help", "--no-open", "-o", str(output)], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    assert "--ci" not in output.read_text()


def test_maintainer_can_switch_and_visibility_does_not_leak(tmp_path):
    config = setup(tmp_path)
    grant_maintainer(tmp_path)
    base = []
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    assert (
        "--ci" in runner.invoke(cli, [*base, "--help"], cwd=Path(config).parent).output
    )
    for flag, expected in (("--ci", True), ("--no-ci", False)):
        result = runner.invoke(
            cli, [*base, flag, "describe", "--json"], cwd=Path(config).parent
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["ci"] is expected
    result = runner.invoke(
        cli, [*base, "--help"], env={"PTK_ROLE": "user"}, cwd=Path(config).parent
    )
    assert "--ci" not in result.output
    (tmp_path / "maintainers.ptk.yml").unlink()
    result = runner.invoke(
        cli,
        [*base, "--ci", "go"],
        env={"PTK_ROLE": "maintainer"},
        cwd=Path(config).parent,
    )
    assert result.exit_code == 2 and "maintainer-only" in result.output


def test_ci_detection_remains_available_to_everyone(tmp_path):
    config = setup(tmp_path)
    result = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
        cli, ["describe", "--json"], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["ci"] is True


@pytest.mark.parametrize(
    "command", [[], ["run", "go"], ["go"], ["run", "--dry-run"], ["go", "--dry-run"]]
)
def test_global_variant_reaches_default_generic_and_shortcut_jobs(tmp_path, command):
    config = setup(tmp_path)
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, ["-V", "large", *command], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    assert "8 world" in result.output


def test_global_variant_display_and_irrelevant_commands(tmp_path):
    config = setup(tmp_path)
    base = ["-V", "large"]
    runner = CliRunner(env={"PTK_CI": "0"})
    result = runner.invoke(
        cli, [*base, "variant", "show", "--json"], cwd=Path(config).parent
    )
    assert json.loads(result.output)["name"] == "large"
    result = runner.invoke(
        cli, [*base, "variant", "show", "small", "--json"], cwd=Path(config).parent
    )
    assert json.loads(result.output)["name"] == "small"
    result = runner.invoke(
        cli, ["-V", "irrelevant", "validate"], cwd=Path(config).parent
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        cli, [*base, "go", "--all-variants"], cwd=Path(config).parent
    )
    assert result.exit_code == 2 and "not both" in result.output
    result = runner.invoke(cli, ["go", "-V", "large"], cwd=Path(config).parent)
    assert result.exit_code == 2 and "No such option" in result.output


@pytest.mark.parametrize("command", ["set", "new", "gui"])
@pytest.mark.parametrize("role", ["user", ""])
def test_variant_mutations_removed_for_everyone(tmp_path, command, role):
    config = setup(tmp_path)
    grant_maintainer(tmp_path)
    result = CliRunner(env={"PTK_ROLE": role}).invoke(
        cli, ["variant", command, "--help"], cwd=Path(config).parent
    )
    assert result.exit_code == 2 and "No such command" in result.output
    assert not (tmp_path / "local.ptk.yml").exists()


def test_vmr_ci_switch_uses_selected_repository_role(tmp_path, monkeypatch):
    a, _b = workspace(tmp_path)
    grant_maintainer(a.parent)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "", "PTK_CI": "0"})
    result = runner.invoke(cli, ["--ci", "firmware", "validate"])
    assert result.exit_code == 0, result.output
    for args in (["bootloader", "validate"], ["repos"]):
        result = runner.invoke(cli, ["--ci", *args])
        assert result.exit_code != 0 and "maintainer-only" in result.output
    grant_maintainer(tmp_path)
    assert runner.invoke(cli, ["--ci", "repos"]).exit_code == 0
    result = runner.invoke(cli, ["--ci", "bootloader", "--help"])
    assert result.exit_code != 0 and "maintainer-only" in result.output


def test_global_variant_reaches_vmr_member(tmp_path, monkeypatch):
    a, _ = workspace(tmp_path)
    data = read_project(a)
    data["variants"] = {"default": "one", "variants": {"one": {}, "two": {}}}
    write_project(a, yaml.safe_dump(data))
    monkeypatch.chdir(tmp_path)
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, ["-V", "two", "firmware", "variant", "show", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["name"] == "two"
