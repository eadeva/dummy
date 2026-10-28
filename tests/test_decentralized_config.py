"""CLI and editor share repository discovery, strict composition and provenance."""

import json

import pytest
from click.testing import CliRunner

from ptk.application.use_cases.project import ExportSchema
from ptk.domain.artifacts import EventRoute
from ptk.domain.errors import ConfigError
from ptk.drivers.cli.main import cli


def test_discovers_outside_config_folder_and_stops_at_project_boundaries(write, load):
    root = write(
        {
            ".main.ptk.yml": "repository: {alias: demo, config_path: config}\n",
            "config/project.ptk.yml": "project: {name: demo}\n",
            "src/compile/job.ptk.yml": "jobs: {build: {steps: [{hello: {run: echo hi}}]}}",
            "elsewhere/params.ptk.yaml": "jobs: {build: {params: {count: {type: int, default: 2}}}}",
            "nested/.main.ptk.yml": "repository: {alias: nested, config_path: .}\nproject: {name: nested}",
            "nested/broken.ptk.yml": "invalid: [",
            ".ptk/generated.ptk.yml": "invalid: [",
            ".github/ptk/examples/broken.ptk.yml": "invalid: [",
            "other/.git/HEAD": "ref: refs/heads/main",
            "other/broken.ptk.yml": "invalid: [",
            "config/.gen.version.ptk.yml": "invalid: [",
        }
    )
    project = load(root)
    assert project.config.jobs["build"].params["count"].default == 2
    assert len(project.files) == 4
    assert (
        project.location(("jobs", "build", "params", "count", "default")).file
        == "elsewhere/params.ptk.yaml"
    )


@pytest.mark.parametrize(
    "first, second",
    [
        ("vars: {count: 1}", "vars: {count: 2}"),
        ("vars: {count: 1}", "vars: {count: 1}"),
        ("plugins: []", "plugins: []"),
        ("vars: {count: {a: 1}}", "vars: {count: null}"),
    ],
)
def test_conflicts_report_both_sources_even_for_identical_values(
    write, load, first, second
):
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\n",
            "a.ptk.yml": first,
            "z.ptk.yml": second,
        }
    )
    with pytest.raises(ConfigError) as error:
        load(root)
    assert all(
        text in str(error.value)
        for text in ("a.ptk.yml:1", "z.ptk.yml:1", "overwriting is not allowed")
    )


def test_cli_editor_contract_uses_installed_schema_and_keeps_invalid_project(write):
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\n",
            "events.ptk.yml": "artifactory: {url: 'https://example.invalid', repository: packages, events: {push: {path: branches}}}",
        }
    )
    args = ["-C", str(root / ".main.ptk.yml"), "describe", "--json", "--configuration"]
    runner = CliRunner()
    valid = runner.invoke(cli, args)
    assert valid.exit_code == 0, valid.output
    config = json.loads(valid.output)["projects"][0]["configuration"]
    assert config["schema"] == ExportSchema().execute()
    assert config["value"]["artifactory"]["events"]["push"] == {"path": "branches"}
    (root / "events.ptk.yml").write_text(
        "artifactory: {events: {push: {step: {run: bad}}}}"
    )
    invalid = runner.invoke(cli, args)
    assert invalid.exit_code == 0, invalid.output
    project = json.loads(invalid.output)["projects"][0]
    assert project["error"] and project["diagnostics"]
    assert project["configuration"]["value"]["artifactory"]
    assert any(
        item["file"] == str(root / "events.ptk.yml") for item in project["diagnostics"]
    )
    assert runner.invoke(cli, args[:2] + ["setup", "config", "validate"]).exit_code != 0


def test_initial_malformed_marker_is_reported_as_project_not_missing(
    tmp_path, monkeypatch
):
    (tmp_path / ".main.ptk.yml").write_text("repository: [")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["describe", "--json", "--configuration"])
    assert result.exit_code == 0, result.output
    project = json.loads(result.output)["projects"][0]
    assert project["entry_file"] == str(tmp_path / ".main.ptk.yml")
    assert "invalid YAML" in project["error"]


def test_absent_project_is_an_empty_inventory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["describe", "--json", "--configuration"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["projects"] == []


def test_event_form_default_is_a_route_and_validation_is_always_accessible(write):
    assert (
        EventRoute.model_validate(
            ExportSchema().execute()["$defs"]["EventRoute"]["default"]
        ).path
        == ""
    )
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\ncommand_audience: {setup: maintainer}\n"
        }
    )
    result = CliRunner(env={"PTK_ROLE": "user"}).invoke(
        cli, ["-C", str(root / ".main.ptk.yml"), "setup", "config", "validate"]
    )
    assert result.exit_code == 0, result.output


def test_editor_json_preserves_unsupported_scalar_types_as_locked_values(write):
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\nvars: {big: 9007199254740993, date: 2024-01-01}\n"
        }
    )
    result = CliRunner().invoke(
        cli,
        ["-C", str(root / ".main.ptk.yml"), "describe", "--json", "--configuration"],
    )
    assert result.exit_code == 0, result.output
    config = json.loads(result.output)["projects"][0]["configuration"]
    assert config["value"]["vars"]["big"] == "9007199254740993"
    assert ["vars", "big"] in config["locked"]
    assert ["vars", "date"] in config["locked"]


@pytest.mark.parametrize(
    "snippet, message",
    [
        ("include: [missing.ptk.yml]", "unknown key 'include'"),
        ("variants: variants.ptk.yml", "variants"),
        ("tools: !include tools.ptk.yml", "unknown tag !include"),
        ("vars: !append [one]", "unknown tag !append"),
        ("vars: !replace {a: 1}", "unknown tag !replace"),
    ],
)
def test_configuration_uses_normal_schema_and_yaml_validation(
    write, load, snippet, message
):
    root = write(
        {".main.ptk.yml": "project: {name: demo}\n", "fragment.ptk.yml": snippet}
    )
    with pytest.raises(ConfigError, match=message):
        load(root)
