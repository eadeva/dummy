"""Retired extensions fail as configuration errors; installed entry points are inert."""

import importlib.metadata
import json

import pytest
import yaml

from ptk.application.use_cases.project import ExportSchema
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


@pytest.mark.parametrize(
    "change",
    [
        {"plugins": []},
        {"plugins": ["company-extension"]},
        {"tools": {"sdk": {"installers": {"company": {}}}}},
        {"credentials": {"service": {"providers": ["company"]}}},
        {"report_formats": ["company"]},
        {"jobs": {"go": {"steps": {"custom": {"uses": "company.check"}}}}},
        {"jobs": {"go": {"steps": {"custom": {"generators": ["company.config"]}}}}},
    ],
)
def test_removed_extensions_are_editable_validation_errors(tmp_path, change):
    entry = tmp_path / ".main.ptk.yml"
    model = {
        "project": {"name": "example"},
        "jobs": {"go": {"steps": {"hello": {"uses": "echo"}}}},
        **change,
    }
    write_project(entry, yaml.safe_dump(model))
    runner = CliRunner()
    invalid = runner.invoke(cli, ["validate"], cwd=tmp_path)
    assert invalid.exit_code != 0, invalid.output
    inventory = runner.invoke(
        cli, ["describe", "--json", "--configuration"], cwd=tmp_path
    )
    assert inventory.exit_code == 0, inventory.output
    current = json.loads(inventory.output)["projects"][0]
    assert current["error"] and current["configuration"]["bindings"]
    assert not (tmp_path / "_builds").exists()


def test_installed_ptk_entry_points_are_never_discovered(tmp_path, monkeypatch):
    dist = tmp_path / "retired_extension-1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: retired-extension\nVersion: 1.0\n"
    )
    groups = [
        "steps",
        "generators",
        "reporters",
        "report_contributors",
        "secret_providers",
        "installers",
    ]
    (dist / "entry_points.txt").write_text(
        "\n".join(f"[ptk.{g}]\ncustom = retired_extension:run\n" for g in groups)
    )
    (tmp_path / "retired_extension.py").write_text(
        "raise AssertionError('PTK imported a removed extension')"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    original = importlib.metadata.entry_points

    def entries(**kwargs):
        assert not kwargs.get("group", "").startswith("ptk."), (
            "PTK scanned removed plugin entry points"
        )
        return original(**kwargs)

    monkeypatch.setattr(importlib.metadata, "entry_points", entries)
    write_project(
        tmp_path / ".main.ptk.yml",
        yaml.safe_dump(
            {
                "project": {"name": "example"},
                "jobs": {"go": {"steps": {"hello": {"uses": "echo"}}}},
            }
        ),
    )
    runner = CliRunner()
    for args in [["--help"], ["describe", "--json"], ["go"]]:
        result = runner.invoke(cli, args, cwd=tmp_path)
        assert result.exit_code == 0, result.output


def test_schema_offers_only_shipped_operations_and_generators():
    from ptk.domain.variants.generators import GENERATORS

    schema = ExportSchema().execute()
    assert "plugins" not in schema["properties"]
    assert "installers" not in schema["$defs"]["ToolSpec"]["properties"]
    choices = schema["$defs"]["StepSpec"]["properties"]["generators"]["items"]["enum"]
    assert set(choices) == set(GENERATORS)
