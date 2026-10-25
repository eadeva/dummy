"""Default action and parameter defaults (static, per variant, per layer)."""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner

from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import ConfigError, PtkError
from ptk.drivers.cli.main import cli
from tests.conftest import DEMO

HOST = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}

PROJECT = """
project: {name: t, default_action: hello}
vars: {flavour: vanilla}
variants:
  components:
    core:
      features:
        SPEED: {type: int, default: 1}
  variants:
    slow: {components: [core], data: {mode: careful}}
    fast: {components: [core], features: {SPEED: 9}, data: {mode: quick}}
actions:
  hello:
    params:
      who: {default: world}
      mode: {type: choice, choices: [careful, quick], default: "${vh.data.mode}"}
      taste: {default: "${vars.flavour}-${env:TASTE:-plain}"}
      speed: {type: int, default: "${vh.features.SPEED}"}
    steps:
      - say: "echo hello ${params.who} ${params.mode} ${params.taste} ${params.speed}"
  other:
    steps: [{x: "echo other"}]
"""


def prepare(root, environ=None, **request):
    app = create_app(environ={**HOST, **(environ or {})})
    project = app.load_project.execute(root)
    return app.prepare_run(project).execute(project, RunRequest(**request)).plan


def test_default_action_is_used_when_no_action_given(write):
    root = write({".main.ptk.yml": PROJECT})
    plan = prepare(root, variant="slow")
    assert plan.action == "hello"
    assert prepare(root, action="other", variant="slow").action == "other"


def test_parameter_defaults_per_variant_vars_and_env(write):
    root = write({".main.ptk.yml": PROJECT})
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
    root = write({".main.ptk.yml": PROJECT.replace("mode: quick}", "mode: reckless}")})
    with pytest.raises(
        PtkError, match="parameter 'mode': expected one of careful, quick"
    ):
        prepare(root, variant="fast")


def test_defaults_can_be_overridden_per_layer(write):
    root = write(
        {
            ".main.ptk.yml": PROJECT,
            "local.ptk.yml": "actions: {hello: {params: {who: {default: me}}}}\n",
        }
    )
    assert prepare(root, variant="slow").params["who"] == "me"


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ('who: {default: "${params.other}"}', "params.other"),
        ('who: {default: "${vars.flavor}"}', "did you mean 'flavour'"),
    ],
)
def test_invalid_default_references_are_config_errors(write, snippet, message):
    root = write({".main.ptk.yml": PROJECT.replace("who: {default: world}", snippet)})
    with pytest.raises(ConfigError, match=message.replace("$", r"\$")):
        create_app(environ={}).load_project.execute(root)


def test_default_action_must_exist_and_be_public(write):
    root = write(
        {
            ".main.ptk.yml": PROJECT.replace(
                "default_action: hello", "default_action: helo"
            )
        }
    )
    with pytest.raises(ConfigError, match="did you mean 'hello'"):
        create_app(environ={}).load_project.execute(root)
    root = write(
        {
            ".main.ptk.yml": PROJECT.replace(
                "  other:\n    steps", "  other:\n    audience: maintainer\n    steps"
            ).replace("default_action: hello", "default_action: other")
        }
    )
    with pytest.raises(ConfigError, match="available to everyone"):
        create_app(environ={}).load_project.execute(root)


def test_no_action_and_no_default(write):
    root = write({".main.ptk.yml": PROJECT.replace(", default_action: hello", "")})
    with pytest.raises(PtkError, match="no project.default_action"):
        prepare(root, variant="slow")


def test_plain_ptk_runs_default_action(write):
    root = write({".main.ptk.yml": PROJECT})
    args = ["--config", str(root / ".main.ptk.yml"), "--no-ci"]
    result = CliRunner(env=HOST).invoke(cli, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "hello world careful vanilla-plain 1" in result.output
    dry = CliRunner().invoke(
        cli, [*args, "dry-run", "-V", "fast"], catch_exceptions=False
    )
    assert "say  echo hello world quick" in dry.output


def test_plain_ptk_outside_a_project_shows_help(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, [], catch_exceptions=False)
    assert result.exit_code == 0 and "Commands" in result.output


def test_demo_toolchain_follows_variant():
    args = ["--config", str(DEMO / ".main.ptk.yml"), "--no-ci", "dry-run"]
    us = CliRunner().invoke(cli, [*args, "-V", "b_us"], catch_exceptions=False)
    assert "-DTOOLCHAIN=arm-clang" in us.output and "build (dry run" in us.output
