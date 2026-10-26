"""The editor consumes PTK's permissions/discovery, never a second YAML parser."""

import json

import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer
from tests.test_command_access import snapshot
from tests.test_variant_commands import setup
from tests.test_workspace import workspace


def test_inventory_is_read_only_filters_roles_and_omits_secret_values(tmp_path):
    entry = setup(tmp_path)
    data = yaml.safe_load(entry.read_text())
    data["jobs"]["secret-job"] = {
        "audience": "maintainer",
        "steps": [{"echo": "echo private"}],
    }
    data["jobs"]["go"]["params"]["token"] = {"type": "secret", "env": "EXAMPLE_TOKEN"}
    data["workflows"] = {
        "verify": {"steps": [{"go": "go"}]},
        "release": {"audience": "maintainer", "steps": [{"go": "go"}]},
    }
    data["vars"] = {"internal": "PRIVATE_CONFIG_VALUE"}
    entry.write_text(yaml.safe_dump(data))
    grant_maintainer(tmp_path)
    before = snapshot(tmp_path)
    base = ["-c", str(entry), "describe", "--json"]
    for role, expected in (("user", ["go"]), ("", ["go", "secret-job"])):
        result = CliRunner(
            env={"PTK_ROLE": role, "PTK_CI": "0", "EXAMPLE_TOKEN": "SECRET_VALUE"}
        ).invoke(cli, base)
        assert result.exit_code == 0, result.output
        doc = json.loads(result.output)
        assert doc["schema_version"] == 1 and doc["mode"] == "repository"
        project = doc["projects"][0]
        assert [j["name"] for j in project["jobs"]] == expected
        assert project["capabilities"]["setup_vscode"] is (role == "")
        assert project["default_variant"] == "small"
        assert (
            "SECRET_VALUE" not in result.output
            and "PRIVATE_CONFIG_VALUE" not in result.output
        )
        assert "token" not in {p["name"] for p in project["jobs"][0]["params"]}
        assert {w["name"] for w in project["workflows"]} == (
            {"verify"} if role else {"verify", "release"}
        )
        assert snapshot(tmp_path) == before


def test_inventory_respects_group_policies(tmp_path):
    entry = setup(tmp_path)
    data = yaml.safe_load(entry.read_text())
    data["command_audience"] = {
        "variant": "maintainer",
        "report": "maintainer",
        "workflow": "maintainer",
        "setup.config": "maintainer",
    }
    data["workflows"] = {"verify": {"steps": [{"go": "go"}]}}
    entry.write_text(yaml.safe_dump(data))
    result = CliRunner(env={"PTK_ROLE": "user"}).invoke(
        cli, ["-c", str(entry), "describe", "--json"]
    )
    project = json.loads(result.output)["projects"][0]
    assert project["variants"] == [] and project["workflows"] == []
    assert not any(project["capabilities"].values())


def test_vmr_inventory_retains_healthy_members_when_one_is_invalid(
    tmp_path, monkeypatch
):
    _a, b = workspace(tmp_path)
    (tmp_path / "workflow.ptk.yml").write_text(
        "workflows: {verify: {steps: [{build: {repo: firmware, job: build}}]}}\n"
    )
    b.write_text(
        "not: a valid project\nrepository: {alias: bootloader, config_path: config}\n"
    )
    monkeypatch.chdir(tmp_path)
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli, ["describe", "--json"]
    )
    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert doc["mode"] == "workspace"
    assert {p["alias"] for p in doc["projects"]} == {"firmware", "bootloader"}
    assert [w["name"] for w in doc["workflows"]] == ["verify"]
    assert "error" in next(p for p in doc["projects"] if p["alias"] == "bootloader")
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli, ["firmware", "describe", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "repository"
