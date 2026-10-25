import copy

import pytest
import yaml
from click.testing import CliRunner

from ptk.domain.config.migration import migrate
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli

LEGACY = {
    "ACTIONS": {
        "build": {
            "DEFAULT_PARAMETERS": {"jobs": 2, "verbose": False},
            "PHASES": {
                "checks": {
                    "parallel": True,
                    "SETS": {
                        "compile": {
                            "shell_run_command": "echo $VAR{greeting}",
                            "game_stopper": False,
                            "non_blocking": True,
                        },
                    },
                }
            },
        }
    },
    "VARS": {"greeting": "hello"},
}


def test_conversion_is_valid_and_does_not_mutate():
    before = copy.deepcopy(LEGACY)
    result = migrate(LEGACY, "demo")
    assert before == LEGACY
    step = result["actions"]["build"]["steps"][0]["checks"]["steps"][0]["compile"]
    assert step == {
        "run": "echo ${vars.greeting}",
        "continue_on_error": True,
        "background": True,
    }
    assert result["actions"]["build"]["params"]["jobs"]["type"] == "int"


@pytest.mark.parametrize(
    "extra",
    [
        {"variant_overrides": {}},
        {"execute_if": {"OS": "windows"}},
        {"shell_run_command": "echo conflict"},
        {"game_stopper": "false"},
    ],
)
def test_unsupported_or_ambiguous_fields_fail(extra):
    raw = {"ACTIONS": {"go": {"steps": {"one": {"run": "echo hi", **extra}}}}}
    with pytest.raises(PtkError):
        migrate(raw, "demo")


def test_migration_cli_preview_alias_and_overwrite(tmp_path):
    source = tmp_path / "old.yml"
    source.write_text(yaml.safe_dump(LEGACY))
    target = tmp_path / "main.ptk.yml"
    runner = CliRunner()
    args = [str(source), "--output", str(target)]
    preview = runner.invoke(cli, ["setup", "migrate", *args, "--dry-run"])
    assert preview.exit_code == 0, preview.output
    assert not target.exists()
    assert yaml.safe_load(preview.output)["schema_version"] == 1
    actual = runner.invoke(cli, ["migrate", *args])
    assert actual.exit_code == 0, actual.output
    contents = target.read_text()
    again = runner.invoke(cli, ["setup", "migrate", *args])
    assert again.exit_code == 2
    assert target.read_text() == contents
    checked = runner.invoke(
        cli, ["--config", str(target), "setup", "config", "validate"]
    )
    assert checked.exit_code == 0, checked.output
