"""The CLI and editor consume one conventional file layout owned by PTK."""

import json
from pathlib import Path

import pytest

from ptk.application.use_cases.variants import VariantService
from ptk.domain.errors import ConfigError
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner


def files(**extra):
    return {
        ".main.ptk.yml": "repository: {alias: demo, config_path: config}\n",
        "config/project.ptk.yml": "name: demo\n",
        **extra,
    }


def test_only_known_documents_and_registered_components_are_loaded(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}",
                "config/jobs/build.ptk.yml": """\
steps:
  compile:
    run: make
""",
                "config/variants/debug.ptk.yml": "features: {TLS: true}",
                "config/project.variants.ptk.yml": "default: debug",
                "src/networking/component.variants.ptk.yml": "features: {TLS: {type: bool}}",
                "src/networking/CMakeLists.txt": "# component build",
                "src/networking/extra.ptk.yml": "invalid: [",
                "elsewhere/job.ptk.yml": "invalid: [",
                "nested/.main.ptk.yml": "repository: {alias: nested, config_path: .}",
            }
        )
    )
    project = load(root)
    assert list(project.config.jobs["build"].steps) == ["compile"]
    assert VariantService(project).resolve().values["TLS"] is True
    assert (
        project.location(
            ("variants", "components", "networking", "features", "TLS")
        ).file
        == "src/networking/component.variants.ptk.yml"
    )
    assert len(project.files) == 6


@pytest.mark.parametrize(
    "name",
    [
        "other.ptk.yml",
        "jobs.ptk.yml",
        "cx.ptk.yml",
        "local.ptk.yml",
        "project.ptk.yaml",
    ],
)
def test_unrecognized_configuration_names_are_errors(write, load, name):
    root = write(files(**{f"config/{name}": "{}"}))
    with pytest.raises(ConfigError, match="unexpected configuration filename"):
        load(root)


def test_unrecognized_filename_lists_the_conventional_names(write, load):
    root = write(files(**{"config/artifactory_structure.ptk.yml": "{}"}))
    with pytest.raises(ConfigError, match="expected one of: artifactory_paths.ptk.yml"):
        load(root)


@pytest.mark.parametrize(
    "name", ["jobs/nested/a.ptk.yml", "jobs/build.ptk.yaml", "jobs/1bad.ptk.yml"]
)
def test_entity_names_and_locations_are_checked(write, load, name):
    root = write(files(**{f"config/{name}": "{}"}))
    with pytest.raises(ConfigError):
        load(root)


def test_main_is_metadata_only_and_documents_are_section_scoped(write, load):
    root = write(
        files(
            **{
                "config/jobs/build.ptk.yml": """\
jobs:
  build:
    steps: {}
"""
            }
        )
    )
    with pytest.raises(ConfigError, match="unknown key"):
        load(root)
    (root / "config/jobs/build.ptk.yml").unlink()
    (root / ".main.ptk.yml").write_text(
        "repository: {alias: demo, config_path: config}\nproject: {name: demo}"
    )
    with pytest.raises(ConfigError, match="unknown key"):
        load(root)


@pytest.mark.parametrize(
    "snippet",
    ["include: [other.ptk.yml]", "vars: !include other.ptk.yml", "vars: !append [one]"],
)
def test_only_current_yaml_and_schema_are_accepted(write, load, snippet):
    root = write(files(**{"config/project.ptk.yml": "name: demo\n" + snippet}))
    with pytest.raises(ConfigError):
        load(root)


@pytest.mark.parametrize("component_path", ["../outside", "/tmp/outside"])
def test_component_directory_cannot_escape_repository(write, load, component_path):
    root = write(
        files(
            **{
                "config/project.ptk.yml": f"name: demo\ncomponents: {{networking: {{path: '{component_path}'}}}}"
            }
        )
    )
    with pytest.raises(ConfigError, match="within the repository"):
        load(root)


def test_component_directory_has_one_registration(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {one: {path: src}, two: {path: src}}"
            }
        )
    )
    with pytest.raises(ConfigError, match="already registered"):
        load(root)


def test_missing_optional_component_document_can_be_created_by_editor(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}"
            }
        )
    )
    project = load(root)
    assert project.config.variants.components["networking"].features == {}
    assert not (root / "src/networking/component.variants.ptk.yml").exists()


def test_component_constraints_apply_only_to_selected_components(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}",
                "src/networking/component.variants.ptk.yml": "features: {TLS: {type: bool}}\nconstraints: [{expr: TLS, message: Enable TLS}]",
                "config/variants/off.ptk.yml": "components: []",
                "config/variants/on.ptk.yml": "components: [networking]",
            }
        )
    )
    variants = VariantService(load(root))
    assert variants.resolve("off").ok
    assert variants.resolve("on").errors[0].message == "Enable TLS"


def test_component_cross_references_are_validated_after_composition(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}",
                "src/networking/component.variants.ptk.yml": "requires_components: [missing]",
            }
        )
    )
    with pytest.raises(ConfigError, match="unknown component 'missing'") as error:
        load(root)
    assert "component.variants.ptk.yml" in str(error.value)


def test_symlink_component_document_is_rejected(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}",
                "other.txt": "{}",
            }
        )
    )
    folder = root / "src/networking"
    folder.mkdir(parents=True)
    try:
        (folder / "component.variants.ptk.yml").symlink_to(root / "other.txt")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ConfigError, match="symbolic links"):
        load(root)


def test_editor_reports_file_schemas_ownership_fingerprints_and_errors(write):
    root = write(
        files(
            **{
                "config/artifactory_paths.ptk.yml": "url: https://example.invalid\nrepository: packages\nevents: {push: {path: branches}}"
            }
        )
    )
    args = ["describe", "--json", "--configuration"]
    runner = CliRunner()
    result = runner.invoke(cli, args, cwd=root)
    assert result.exit_code == 0, result.output
    config = json.loads(result.output)["projects"][0]["configuration"]
    assert config["version"] == 4
    binding = next(b for b in config["bindings"] if b["path"] == ["jobs", "*"])
    assert binding["file"] == str(root / "config/jobs/{name}.ptk.yml")
    assert binding["document_path"] == []
    project_doc = next(
        d for d in config["documents"] if Path(d["file"]).name == "project.ptk.yml"
    )
    assert "name" in project_doc["schema"]["properties"]
    assert "jobs" not in project_doc["schema"]["properties"]
    assert str(root / "config/artifactory_paths.ptk.yml") in config["fingerprints"]
    (root / "config/artifactory_paths.ptk.yml").write_text(
        "events: {push: {step: {run: bad}}}"
    )
    invalid = runner.invoke(cli, args, cwd=root)
    assert invalid.exit_code == 0, invalid.output
    project = json.loads(invalid.output)["projects"][0]
    assert project["error"] and project["diagnostics"]
    assert project["configuration"]["value"]["artifactory"]["events"]["push"][
        "step"
    ] == {"run": "bad"}
    assert any(
        d["file"].endswith("artifactory_paths.ptk.yml") for d in project["diagnostics"]
    )


def test_malformed_marker_is_not_reported_as_missing(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("repository: [")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["describe", "--json", "--configuration"])
    assert result.exit_code == 0, result.output
    assert "invalid YAML" in json.loads(result.output)["projects"][0]["error"]


def test_no_project_inventory_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["describe", "--json", "--configuration"])
    assert json.loads(result.output)["projects"] == []


def test_validate_stays_available_to_users(write):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncommand_audience: {self-service: maintainer}"
            }
        )
    )
    result = CliRunner(env={"PTK_ROLE": "user"}).invoke(cli, ["validate"], cwd=root)
    assert result.exit_code == 0, result.output


def test_explicit_cli_override_keeps_model_behavior(write, load):
    root = write(files(**{"config/project.ptk.yml": "name: demo\nvars: {count: 1}"}))
    assert load(root, overrides=["vars.count=2"]).config.vars["count"] == 2


def test_project_document_symlink_is_rejected_before_reading(write, load):
    root = write(files())
    project = root / "config/project.ptk.yml"
    project.unlink()
    target = root / "other.txt"
    target.write_text("name: other\n")
    try:
        project.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ConfigError, match="symbolic links"):
        load(root)


def test_component_directory_cannot_be_a_regular_file(write, load):
    root = write(
        files(
            **{
                "config/project.ptk.yml": "name: demo\ncomponents: {networking: {path: src/networking}}",
                "src/networking": "not a directory",
            }
        )
    )
    with pytest.raises(ConfigError, match="must be a directory"):
        load(root)
