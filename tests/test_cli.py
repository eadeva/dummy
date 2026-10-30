import json
import shutil

import pytest

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import DEMO, grant_maintainer
from tests.project_files import project_files

CONFIG = []


@pytest.fixture(autouse=True)
def demo_checkout(tmp_path, monkeypatch):
    demo = tmp_path / "cli-demo"
    shutil.copytree(
        DEMO,
        demo,
        ignore=shutil.ignore_patterns("_logs", "_reports", "_builds", "_bin", ".ptk"),
    )
    grant_maintainer(demo)
    monkeypatch.setitem(globals(), "DEMO", demo)
    monkeypatch.delenv("PTK_ROLE", raising=False)


def run(*args):
    return CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*CONFIG, *args], catch_exceptions=False, cwd=DEMO
    )


def test_config_validate_and_show():
    result = run("validate")
    assert result.exit_code == 0, result.output
    assert "configuration is valid" in result.output
    show = run(
        "maintainer", "config", "show", "jobs.build.params.jobs", "--format", "json"
    )
    assert json.loads(show.output) == {
        "type": "int",
        "default": 8,
        "env": "PTK_JOBS",
        "help": "Parallel jobs",
    }
    sources = run("maintainer", "config", "show", "project", "--sources")
    assert "config/ptk/project.ptk.yml:2" in sources.output


def test_set_override():
    result = run(
        "--set",
        "jobs.build.params.jobs.default=3",
        "maintainer",
        "config",
        "show",
        "jobs.build.params.jobs.default",
    )
    assert result.output.strip().startswith("3")


def test_schema_contains_step_entry():
    schema = json.loads(run("maintainer", "config", "schema").output)
    assert "StepSpec" in schema["$defs"] and "StepEntry" not in schema["$defs"]


def test_variant_commands():
    listing = run("variant", "list", "--names")
    assert listing.output.split() == ["customer_a_high", "customer_b_us"]
    show = run("variant", "show", "b_us")
    assert show.exit_code == 0 and "MAP_REGION" in show.output
    explain = run("variant", "explain", "2", "NAV_3D")
    assert "NOT satisfied" in explain.output
    assert run("validate", "--variants").exit_code == 0


def test_errors_exit_2():
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*CONFIG, "variant", "show", "nope"], cwd=DEMO
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
            "-V",
            "b_us",
            "build",
            "--dry-run",
            "--jobs",
            "3",
            "--env",
        ],
        catch_exceptions=False,
        cwd=demo,
    )
    assert result.exit_code == 0, result.output
    assert "dry run" in result.output and "-j 3" in result.output
    assert "camera-selftest: skipped (condition is false" in result.output
    assert "VH_VARIANT=customer_b_us" in result.output
    assert {
        path: data for path, data in snapshot().items() if path.parts[0] != ".ptk"
    } == {path: data for path, data in before.items() if path.parts[0] != ".ptk"}
    assert (demo / ".ptk/graphs/job-build-customer_b_us.html").is_file()


def test_run_errors_are_clean():
    assert "did you mean 'build'" in run("biuld", "--dry-run").output
    bad = run("run", "build", "-p", "jobs=lots")
    assert bad.exit_code == 2 and "parameter 'jobs'" in bad.output
    typed = run("build", "--dry-run", "--jobs", "lots")
    assert typed.exit_code == 2 and "not a valid integer" in typed.output
    assert "no selected step" in run("build", "--dry-run", "--", "-x").output


def test_run_executes_and_returns_exit_code(write):
    root = write(
        project_files(
            """\
project:
  name: t
jobs:
  ok:
    steps:
      hi:
        run: echo hi-there
  bad:
    steps:
      fail:
        run: exit 4
"""
        )
    )
    config = []
    ok = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*config, "run", "ok"], catch_exceptions=False, cwd=root
    )
    assert ok.exit_code == 0 and "hi-there" in ok.output
    bad = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*config, "run", "bad"], catch_exceptions=False, cwd=root
    )
    assert bad.exit_code == 1 and "exit code 4" in bad.output
