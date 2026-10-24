import json

from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.conftest import DEMO

CONFIG = ["--config", str(DEMO / "main.ptk.yml"), "--no-ci"]


def run(*args):
    return CliRunner().invoke(cli, [*CONFIG, *args], catch_exceptions=False)


def test_config_validate_and_show():
    result = run("config", "validate")
    assert result.exit_code == 0, result.output
    assert "configuration is valid" in result.output
    show = run("config", "show", "actions.build.params.jobs", "--format", "json")
    assert json.loads(show.output) == {"type": "int", "default": 8, "help": "Parallel jobs"}
    sources = run("config", "show", "project", "--sources")
    assert "main.ptk.yml:7" in sources.output


def test_set_override():
    result = run("--set", "actions.build.params.jobs.default=3", "config", "show", "actions.build.params.jobs.default")
    assert result.output.strip().startswith("3")


def test_schema_contains_step_entry():
    schema = json.loads(run("config", "schema").output)
    assert "StepEntry" in schema["$defs"] and "StepSpec" not in schema["$defs"]


def test_variant_commands():
    listing = run("variant", "list", "--names")
    assert listing.output.split() == ["customer_a_high", "customer_b_us"]
    show = run("variant", "show", "b_us")
    assert show.exit_code == 0 and "MAP_REGION" in show.output
    explain = run("variant", "explain", "2", "NAV_3D")
    assert "NOT satisfied" in explain.output
    assert run("variant", "check").exit_code == 0


def test_errors_exit_2():
    result = CliRunner().invoke(cli, [*CONFIG, "variant", "show", "nope"])
    assert result.exit_code == 2
    assert "unknown variant 'nope'" in result.output
