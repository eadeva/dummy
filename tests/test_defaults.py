"""Default job and parameter defaults (static, per variant, per layer)."""

from __future__ import annotations

import os

import pytest

from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import ConfigError, PtkError
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import DEMO
from tests.project_files import project_files

HOST = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}

PROJECT = """\
project:
  name: t
  default_job: hello
vars:
  flavour: vanilla
variants:
  default: slow
  components:
    core:
      features:
        SPEED:
          type: int
          default: 1
  variants:
    slow:
      components:
      - core
      data:
        mode: careful
    fast:
      components:
      - core
      features:
        SPEED: 9
      data:
        mode: quick
jobs:
  hello:
    params:
      who:
        default: world
      mode:
        type: choice
        choices:
        - careful
        - quick
        default: ${vh.data.mode}
      taste:
        default: ${vars.flavour}-${env:TASTE:-plain}
      speed:
        type: int
        default: ${vh.features.SPEED}
    steps:
      say:
        run: echo hello ${params.who} ${params.mode} ${params.taste} ${params.speed}
  other:
    steps:
      x:
        run: echo other
"""


def prepare(root, environ=None, **request):
    app = create_app(environ={**HOST, **(environ or {})})
    project = app.load_project.execute(root)
    return app.prepare_run(project).execute(project, RunRequest(**request)).plan


def test_default_job_is_used_when_no_job_given(write):
    root = write(project_files(PROJECT))
    plan = prepare(root, variant="slow")
    assert plan.job == "hello"
    assert prepare(root, job="other", variant="slow").job == "other"


def test_parameter_defaults_per_variant_vars_and_env(write):
    root = write(project_files(PROJECT))
    slow = prepare(root, variant="slow")
    assert slow.params == {
        "who": "world",
        "mode": "careful",
        "taste": "vanilla-plain",
        "speed": 1,
    }
    assert slow.param_sources["mode"] == "default ${vh.data.mode}"
    fast = prepare(root, variant="fast", environ={"TASTE": "sweet"})
    assert fast.params["mode"] == "quick" and fast.params["speed"] == 9  # typed int
    assert fast.params["taste"] == "vanilla-sweet"
    # the command line still wins over any default
    assert (
        prepare(root, variant="fast", params={"mode": "careful"}).params["mode"]
        == "careful"
    )


def test_template_default_is_type_checked_at_run_time(write):
    root = write(project_files(PROJECT.replace("mode: quick", "mode: reckless")))
    with pytest.raises(
        PtkError, match="parameter 'mode': expected one of careful, quick"
    ):
        prepare(root, variant="fast")


def test_duplicate_defaults_are_rejected_across_files(write):
    root = write(
        project_files(
            PROJECT,
            {"local.ptk.yml": "jobs: {hello: {params: {who: {default: me}}}}\n"},
        )
    )
    with pytest.raises(ConfigError, match="unexpected configuration filename"):
        prepare(root, variant="slow")


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ('who: {default: "${params.other}"}', "params.other"),
        ('who: {default: "${vars.flavor}"}', "did you mean 'flavour'"),
    ],
)
def test_invalid_default_references_are_config_errors(write, snippet, message):
    root = write(
        project_files(PROJECT.replace("who:\n        default: world", snippet))
    )
    with pytest.raises(ConfigError, match=message.replace("$", r"\$")):
        create_app(environ={}).load_project.execute(root)


def test_default_job_must_exist_and_be_public(write):
    root = write(
        project_files(PROJECT.replace("default_job: hello", "default_job: helo"))
    )
    with pytest.raises(ConfigError, match="did you mean 'hello'"):
        create_app(environ={}).load_project.execute(root)
    root = write(
        project_files(
            PROJECT.replace(
                "  other:\n    steps", "  other:\n    audience: maintainer\n    steps"
            ).replace("default_job: hello", "default_job: other")
        )
    )
    with pytest.raises(ConfigError, match="available to everyone"):
        create_app(environ={}).load_project.execute(root)


def test_no_job_and_no_default(write):
    root = write(project_files(PROJECT.replace("  default_job: hello\n", "")))
    with pytest.raises(PtkError, match="no project.default_job"):
        prepare(root, variant="slow")


def test_plain_ptk_runs_default_job(write):
    root = write(project_files(PROJECT))
    args = []
    result = CliRunner(env={"PTK_CI": "0", **HOST}).invoke(
        cli, args, catch_exceptions=False, cwd=root
    )
    assert result.exit_code == 0, result.output
    assert "hello world careful vanilla-plain 1" in result.output
    dry = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*args, "-V", "fast", "run", "--dry-run"], catch_exceptions=False, cwd=root
    )
    assert "say  echo hello world quick" in dry.output


def test_plain_ptk_outside_a_project_shows_help(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner(env={"PTK_CI": "0"}).invoke(cli, [], catch_exceptions=False)
    assert result.exit_code == 0 and "Commands" in result.output


def test_demo_toolchain_follows_variant(tmp_path):
    import shutil

    demo = shutil.copytree(DEMO, tmp_path / "demo")
    args = []
    us = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, [*args, "-V", "b_us", "run", "--dry-run"], catch_exceptions=False, cwd=demo
    )
    assert "-DTOOLCHAIN=arm-clang" in us.output and "build (dry run" in us.output
