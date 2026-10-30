"""Project-aware suggestions use PTK's commands and never resolve run-time values."""

import json

import pytest
from click.shell_completion import BashComplete

from ptk.adapters.git_metadata import GitMetadata
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project
from tests.test_command_access import snapshot
from tests.test_workspace import workspace


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PTK_ROLE", "user")
    monkeypatch.setenv("PTK_CI", "0")
    write_project(
        tmp_path / ".main.ptk.yml",
        {
            "repository": {"alias": "demo", "config_path": "."},
            "project": {"name": "Demo", "default_job": "build"},
            "variants": {
                "default": "debug",
                "components": {
                    "core": {
                        "features": {
                            "MODE": {
                                "type": "enum",
                                "values": ["fast", "safe"],
                                "help": "Compilation mode",
                            },
                            "TRACE": {"type": "bool", "help": "Enable tracing"},
                        }
                    }
                },
                "variants": {
                    "base": {"abstract": True},
                    "debug": {"aliases": ["dev"], "description": "Development build"},
                    "release": {},
                },
            },
            "jobs": {
                "build": {
                    "params": {"branch": {"default": "${git.branch}"}},
                    "steps": {
                        "z_configure": {
                            "run": "echo configure",
                            "title": "Prepare build files",
                        },
                        "compile": {
                            "run": "echo compile",
                            "passthrough": True,
                            "needs": ["z_configure"],
                        },
                        "package": {"run": "echo package", "needs": ["compile"]},
                    },
                }
            },
            "workflows": {
                "verify": {
                    "help": "Build and verify",
                    "jobs": {"make": {"job": "build"}},
                }
            },
        },
    )
    return tmp_path


def test_help_inventory_and_completion_share_read_only_suggestions(
    project, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Suggestions must not resolve Git metadata")

    monkeypatch.setattr(GitMetadata, "discover", forbidden)
    before = snapshot(project)
    runner = CliRunner()
    for args, expected in [
        (["--help"], ["debug", "dev", "release"]),
        (["build", "--help"], ["z_configure", "compile", "package"]),
        (["run", "build", "--help"], ["z_configure", "compile", "package"]),
    ]:
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
        assert "Possible values:" in result.output
        assert all(name in result.output for name in expected)
        assert "--config " not in result.output
    result = runner.invoke(cli, ["describe", "--json"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    info = doc["projects"][0]
    assert info["invocation"] == {"cwd": str(project), "prefix": []}
    options = {param["name"]: param for param in info["jobs"][0]["run_options"]}
    assert options["only_step"]["choices"] == ["z_configure", "compile", "package"]
    assert options["end"]["choices"] == options["only_step"]["choices"]
    assert options["only_step"]["suggestions"][0]["help"] == "Prepare build files"
    assert options["args_for"]["choices"] == []
    assert options["args_for"]["suggestions"][0]["value"] == "compile="
    assert info["workflows"][0]["run_options"] == []
    complete = BashComplete(cli, {}, "ptk", "_PTK_COMPLETE")
    values = lambda args, partial: {
        i.value for i in complete.get_completions(args, partial)
    }
    assert values(["--variant"], "") == {"debug", "dev", "release"}
    assert values(["build", "--feature"], "MODE=") == {"MODE=fast", "MODE=safe"}
    assert values(["build", "--feature"], "TRACE=") == {"TRACE=true", "TRACE=false"}
    assert values(["build", "--feature"], "COMPONENT_CORE=") == {
        "COMPONENT_CORE=true",
        "COMPONENT_CORE=false",
    }
    assert values(["build", "--args-for"], "") == {"compile="}
    assert snapshot(project) == before


@pytest.mark.parametrize("option", ["--config", "-C"])
def test_config_option_is_removed_and_nested_cwd_finds_project(
    project, option, monkeypatch
):
    runner = CliRunner()
    result = runner.invoke(cli, [option, str(project / ".main.ptk.yml"), "validate"])
    assert result.exit_code == 2 and "No such option" in result.output
    nested = project / "source" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    result = runner.invoke(cli, ["validate"])
    assert result.exit_code == 0, result.output


def test_inventory_routes_members_through_workspace_aliases(tmp_path, monkeypatch):
    workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"})
    result = runner.invoke(cli, ["describe", "--json"])
    assert result.exit_code == 0, result.output
    projects = json.loads(result.output)["projects"]
    for project in projects:
        route = project["invocation"]
        assert route == {"cwd": str(tmp_path), "prefix": [project["alias"]]}
        child = runner.invoke(
            cli, [*route["prefix"], "describe", "--json"], cwd=route["cwd"]
        )
        assert child.exit_code == 0, child.output
        assert json.loads(child.output)["projects"][0]["invocation"] == route
