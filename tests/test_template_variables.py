import json
from pathlib import Path

from ptk.domain.config.template_variables import catalogue
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def test_catalogue_is_available_without_git_or_resolving_secret_environment(
    tmp_path, monkeypatch
):
    entry = tmp_path / ".main.ptk.yml"
    write_project(
        entry,
        {
            "project": {"name": "demo"},
            "vars": {"sha": "${git.commit}"},
            "jobs": {
                "go": {
                    "params": {
                        "token": {"type": "secret"},
                        "mode": {"default": "fast"},
                    },
                    "steps": {"echo": {"run": "echo ${git.short_commit}"}},
                }
            },
            "credentials": {"service": {"fields": ["token"]}},
        },
    )

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "The editor catalogue must not execute Git or other commands"
        )

    monkeypatch.setattr("ptk.adapters.process.SubprocessRunner.run", forbidden)
    result = CliRunner(env={"CATALOGUE_TOKEN": "NEVER_PREVIEW_SECRET"}).invoke(
        cli, ["describe", "--json", "--configuration"], cwd=Path(entry).parent
    )
    assert result.exit_code == 0, result.output
    entries = json.loads(result.output)["projects"][0]["configuration"]["variables"][
        "entries"
    ]
    by_name = {entry["reference"]: entry for entry in entries}
    assert "git.short_commit" in by_name
    assert "env:CATALOGUE_TOKEN" in by_name
    assert "NEVER_PREVIEW_SECRET" not in result.output
    assert by_name["params.mode"]["job"] == "go"
    assert by_name["params.token"]["contexts"] == ["secret"]
    assert by_name["secret:service.token"]["contexts"] == ["secret"]
    assert by_name["github.sha"]["contexts"] == ["destination"]
    assert "default" not in by_name["run.bin_dir"]["contexts"]


def test_catalogue_accepts_partial_configuration_and_only_publishes_names():
    value = {
        "vars": {"nested": {"path": "PRIVATE_VALUE"}},
        "jobs": {"broken": None},
        "versioning": {"project": {"source": "git"}},
        "variants": {
            "components": {"core": {"features": {"FAST": {}}}},
            "variants": {"debug": {"data": {"compiler": "PRIVATE_COMPILER"}}},
        },
    }
    data = catalogue(value)
    names = {entry["reference"] for entry in data["entries"]}
    assert {
        "vars.nested.path",
        "vh.features.FAST",
        "vh.components.core",
        "vh.data.compiler",
        "version.current.git.commit",
    } <= names
    assert "PRIVATE_" not in json.dumps(data)
