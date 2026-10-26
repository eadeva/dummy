import json
import shutil

import pytest
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.conftest import DEMO

CONFIG = ["--config", str(DEMO / ".main.ptk.yml")]


def run(*args):
    return CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*CONFIG, *args], catch_exceptions=False
    )


def test_config_validate_and_show():
    result = run("config", "validate")
    assert result.exit_code == 0, result.output
    assert "configuration is valid" in result.output
    show = run("config", "show", "jobs.build.params.jobs", "--format", "json")
    assert json.loads(show.output) == {
        "type": "int",
        "default": 8,
        "env": "PTK_JOBS",
        "help": "Parallel jobs",
    }
    sources = run("config", "show", "project", "--sources")
    assert ".main.ptk.yml:7" in sources.output


def test_set_override():
    result = run(
        "--set",
        "jobs.build.params.jobs.default=3",
        "config",
        "show",
        "jobs.build.params.jobs.default",
    )
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
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*CONFIG, "variant", "show", "nope"]
    )
    assert result.exit_code == 2
    assert "unknown variant 'nope'" in result.output


@pytest.mark.parametrize("existing_logs", [False, True])
def test_dry_run_of_demo_shows_plan_without_executing(tmp_path, existing_logs):
    demo = tmp_path / "demo"
    shutil.copytree(
        DEMO,
        demo,
        ignore=shutil.ignore_patterns("_logs", "_reports", "_builds", "_bin", ".ptk"),
    )
    if existing_logs:
        logs = demo / "_logs"
        logs.mkdir()
        (logs / "previous.log").write_text("Preserve the previous run.\n")

    def snapshot():
        return {
            path.relative_to(demo): path.read_bytes() if path.is_file() else None
            for path in demo.rglob("*")
        }

    before = snapshot()
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli,
        [
            "--config",
            str(demo / ".main.ptk.yml"),
            "-V",
            "b_us",
            "dry-run",
            "build",
            "--jobs",
            "3",
            "--env",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "dry run" in result.output and "-j 3" in result.output
    assert "camera-selftest: skipped (condition is false" in result.output
    assert "VH_VARIANT=customer_b_us" in result.output
    assert snapshot() == before


def test_run_errors_are_clean():
    assert "did you mean 'build'" in run("dry-run", "biuld").output
    bad = run("run", "build", "-p", "jobs=lots")
    assert bad.exit_code == 2 and "parameter 'jobs'" in bad.output
    typed = run("dry-run", "build", "--jobs", "lots")
    assert typed.exit_code == 2 and "not a valid integer" in typed.output
    assert "no selected step" in run("dry-run", "build", "--", "-x").output


def test_run_executes_and_returns_exit_code(write):
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: t}
        jobs:
          ok: {steps: [{hi: "echo hi-there"}]}
          bad: {steps: [{fail: "exit 4"}]}
        """
        }
    )
    config = ["--config", str(root / ".main.ptk.yml")]
    ok = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*config, "run", "ok"], catch_exceptions=False
    )
    assert ok.exit_code == 0 and "hi-there" in ok.output
    bad = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*config, "run", "bad"], catch_exceptions=False
    )
    assert bad.exit_code == 1 and "exit code 4" in bad.output
