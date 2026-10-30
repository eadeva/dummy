"""The editor consumes PTK's permissions/discovery, never a second YAML parser."""

import json
from pathlib import Path

import rich_click as click
import yaml

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project, write_workflows
from tests.test_command_access import snapshot
from tests.test_variant_commands import setup
from tests.test_workspace import workspace


def command_paths(commands):
    result = {}
    for command in commands:
        result[" ".join(command["path"])] = command
        result.update(command_paths(command["children"]))
    return result


def test_inventory_is_read_only_filters_roles_and_omits_secret_values(tmp_path):
    entry = setup(tmp_path)
    data = read_project(entry)
    data["jobs"]["secret-job"] = {
        "audience": "maintainer",
        "steps": {"echo": {"run": "echo private"}},
    }
    data["jobs"]["go"]["params"]["token"] = {"type": "secret", "env": "EXAMPLE_TOKEN"}
    data["workflows"] = {
        "verify": {"jobs": {"go": {"job": "go"}}},
        "release": {"audience": "maintainer", "jobs": {"go": {"job": "go"}}},
    }
    data["vars"] = {"internal": "PRIVATE_CONFIG_VALUE"}
    write_project(entry, yaml.safe_dump(data))
    grant_maintainer(tmp_path)
    before = snapshot(tmp_path)
    base = ["describe", "--json"]
    for role, expected in (("user", ["go"]), ("", ["go", "secret-job"])):
        result = CliRunner(
            env={"PTK_ROLE": role, "PTK_CI": "0", "EXAMPLE_TOKEN": "SECRET_VALUE"}
        ).invoke(cli, base, cwd=Path(entry).parent)
        assert result.exit_code == 0, result.output
        doc = json.loads(result.output)
        assert doc["schema_version"] == 4 and doc["mode"] == "repository"
        project = doc["projects"][0]
        commands = command_paths(project["commands"])
        assert {
            "help",
            "self-service",
            "self-service creds",
            "self-service creds set",
        } <= commands.keys()
        assert ("maintainer sync" in commands) is (role == "")
        if role == "":
            target = next(
                p
                for p in commands["maintainer sync"]["params"]
                if p["name"] == "target"
            )
            assert target["choices"] == ["configs", "tasks", "agent"]
        assert "creds" not in commands  # Obsolete alias is not registered.
        assert "go" not in commands  # Jobs have their own section.
        assert [j["name"] for j in project["jobs"]] == expected
        assert project["capabilities"]["maintenance"] is (role == "")
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
    data = read_project(entry)
    data["command_audience"] = {
        "variant": "maintainer",
        "report": "maintainer",
        "workflow": "maintainer",
        "maintainer.config": "maintainer",
    }
    data["workflows"] = {"verify": {"jobs": {"go": {"job": "go"}}}}
    write_project(entry, yaml.safe_dump(data))
    result = CliRunner(env={"PTK_ROLE": "user"}).invoke(
        cli, ["describe", "--json"], cwd=Path(entry).parent
    )
    project = json.loads(result.output)["projects"][0]
    assert project["variants"] == [] and project["workflows"] == []
    assert project["capabilities"]["validate"]
    assert not any(
        value for key, value in project["capabilities"].items() if key != "validate"
    )
    commands = command_paths(project["commands"])
    assert not any(
        path.startswith(("variant", "report", "workflow", "setup config "))
        and path != "validate"
        for path in commands
    )
    assert "validate" in commands
    assert "self-service creds list" in commands


def test_vmr_inventory_retains_healthy_members_when_one_is_invalid(
    tmp_path, monkeypatch
):
    _a, b = workspace(tmp_path)
    write_workflows(
        (tmp_path / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            "workflows:\n  verify:\n    jobs:\n      build:\n        job: firmware:build\n"
        )["workflows"],
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
    assert "repos" in command_paths(doc["commands"])
    for member in doc["projects"]:
        route = member["invocation"]
        assert route == {"cwd": str(tmp_path), "prefix": [member["alias"]]}
        child = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
            cli, [*route["prefix"], "describe", "--json"], cwd=route["cwd"]
        )
        assert child.exit_code == 0, child.output
        assert json.loads(child.output)["projects"][0]["invocation"] == route
    healthy = next(p for p in doc["projects"] if p["alias"] == "firmware")
    assert "repos" not in command_paths(healthy["commands"])
    assert "self-service creds set" in command_paths(healthy["commands"])
    result = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"}).invoke(
        cli, ["firmware", "describe", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "repository"


def test_command_metadata_does_not_resolve_defaults_or_invoke_callbacks(
    tmp_path, monkeypatch
):
    entry = setup(tmp_path)
    command = cli.commands["self-service"].commands["creds"].commands["set"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not resolve defaults or invoke commands")

    monkeypatch.setattr(command, "callback", forbidden)
    monkeypatch.setattr(command.params[0], "default", forbidden)
    monkeypatch.setattr(
        command,
        "params",
        [
            *command.params,
            click.Option(["--private"], hide_input=True, default="SECRET_DEFAULT"),
            click.Option(["--hidden"], hidden=True),
        ],
    )
    grant_maintainer(tmp_path)
    before = snapshot(tmp_path)
    result = CliRunner(env={"PTK_ROLE": ""}).invoke(
        cli, ["describe", "--json"], cwd=Path(entry).parent
    )
    assert result.exit_code == 0, result.output
    commands = command_paths(json.loads(result.output)["projects"][0]["commands"])
    params = {p["name"]: p for p in commands["self-service creds set"]["params"]}
    assert set(params) == {"name", "field", "store"}
    assert params["name"]["kind"] == "argument" and params["name"]["required"]
    assert params["store"]["option"] == "--store"
    assert "default" not in params["name"]
    fmt = next(
        p for p in commands["maintainer config show"]["params"] if p["name"] == "fmt"
    )
    assert fmt["choices"] == ["yaml", "json"]
    assert "SECRET_DEFAULT" not in result.output
    assert snapshot(tmp_path) == before


def test_parameter_forms_receive_authored_defaults_without_resolving_environment(
    tmp_path,
):
    entry = setup(tmp_path)
    data = read_project(entry)
    data["jobs"]["go"]["params"].update(
        {
            "dynamic": {
                "default": "${env:EXAMPLE_TOKEN}",
                "help": "Resolved at runtime",
            },
            "env_value": {"env": "EXAMPLE_TOKEN", "default": "fallback"},
            "flag": {"type": "bool", "default": False},
            "items": {"type": "list", "default": ["one", "two"]},
            "private": {"type": "secret", "env": "EXAMPLE_TOKEN"},
        }
    )
    write_project(entry, yaml.safe_dump(data))
    before = snapshot(tmp_path)
    result = CliRunner(env={"EXAMPLE_TOKEN": "NEVER_EXPOSE_THIS"}).invoke(
        cli, ["describe", "--json"], cwd=Path(entry).parent
    )
    assert result.exit_code == 0, result.output
    params = {
        param["name"]: param
        for param in json.loads(result.output)["projects"][0]["jobs"][0]["params"]
    }
    assert params["dynamic"]["default"] == "${env:EXAMPLE_TOKEN}"
    assert params["dynamic"]["default_is_template"] is True
    assert params["env_value"]["env"] == "EXAMPLE_TOKEN"
    assert params["env_value"]["default"] == "fallback"
    assert params["flag"]["default"] is False
    assert params["items"]["default"] == ["one", "two"]
    assert "private" not in params and "NEVER_EXPOSE_THIS" not in result.output
    assert snapshot(tmp_path) == before


def test_extension_form_schema_matches_canonical_model_schema():
    from pathlib import Path

    from ptk.application.use_cases.project import ExportSchema

    file = (
        Path(__file__).parents[1]
        / "extensions/project-toolkit/media/config-schema.json"
    )
    assert json.loads(file.read_text()) == ExportSchema().execute()


def test_exported_configuration_fields_have_model_owned_help():
    from ptk.application.use_cases.project import ExportSchema
    from ptk.domain.config.model import JobSpec, ParamSpec, StepSpec

    schema = ExportSchema().execute()
    for name, model in [("root", schema), *schema["$defs"].items()]:
        for field, spec in model.get("properties", {}).items():
            assert spec.get("description", "").strip(), f"{name}.{field} has no help"
    for definition, model, field in [
        ("JobSpec", JobSpec, "only_variants"),
        ("StepSpec", StepSpec, "only_variants"),
        ("ParamSpec", ParamSpec, "env"),
    ]:
        assert (
            schema["$defs"][definition]["properties"][field]["description"]
            == model.model_fields[field].description
        )
    assert "error" in JobSpec.model_fields["only_variants"].description
    assert "skip" in StepSpec.model_fields["only_variants"].description


def test_schema_field_order_survives_sorted_serialization():
    from ptk.application.use_cases.project import ExportSchema
    from ptk.domain.config.layout import Document, document_schema
    from ptk.domain.config.model import PtkConfig

    schema = json.loads(json.dumps(ExportSchema().execute(), sort_keys=True))
    order = schema["x-ptk-field-order"]
    assert order == PtkConfig.model_config["json_schema_extra"]["x-ptk-field-order"]
    assert order.index("project") < order.index("jobs") < order.index("artifactory")
    for model in schema["$defs"].values():
        if "properties" in model:
            assert set(model["x-ptk-field-order"]) == set(model["properties"])
    main = document_schema(
        schema,
        Document(
            Path(".main.ptk.yml"),
            fields={"repository": ("repository",), "ptk_version": ("ptk_version",)},
        ),
    )
    assert main["x-ptk-field-order"] == ["ptk_version", "repository"]
