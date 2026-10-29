"""Canonical navigation, removed aliases and read-only preview boundaries."""

import json

import pytest
from click.testing import CliRunner
from rich.text import Text

from ptk.application.use_cases.hooks import EnsureHooks
from ptk.application.use_cases.tools import ToolService
from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer
from tests.project_files import project_files


@pytest.fixture
def invoke(write):
    root = write(
        project_files(
            "project: {name: demo}\njobs: {build: {steps: [{hi: {uses: echo}}]}}\n"
        )
    )
    grant_maintainer(root)

    def call(*args):
        return CliRunner(env={"PTK_CI": "0", "PTK_ROLE": ""}).invoke(
            cli, ["-C", str(root / ".main.ptk.yml"), *args], catch_exceptions=False
        )

    return call


def test_groups_are_navigation_only(invoke):
    for group, commands in (
        (
            "self-service",
            ("tools", "creds", "completion", "extension", "doctor", "hooks"),
        ),
        ("maintainer", ("config", "sync", "version", "artifacts", "workflow")),
    ):
        result = invoke(group)
        assert result.exit_code == 0, result.output
        text = Text.from_ansi(result.output).plain
        for command in commands:
            assert command in text
        assert "would install" not in text
    assert "init" not in cli.commands["self-service"].commands


@pytest.mark.parametrize(
    "args",
    [
        ["setup"],
        ["config", "show"],
        ["configs", "sync"],
        ["creds", "list"],
        ["self-setup"],
        ["doctor"],
        ["vscode", "tasks"],
        ["version", "show"],
        ["artifacts", "destination"],
        ["dry-run", "build"],
        ["variant", "check"],
        ["workflow", "dry-run", "verify"],
        ["workflow", "report", "verify"],
        ["pre-commit", "check"],
        ["pre-commit", "install"],
        ["maintainer", "version", "check"],
        ["maintainer", "config", "validate"],
    ],
)
def test_removed_commands_are_rejected(invoke, args):
    result = invoke(*args)
    assert result.exit_code == 2, result.output
    assert "No such command" in result.output


def test_nested_config_and_validation_use_root_options(invoke):
    result = invoke("maintainer", "config", "show", "project", "--format", "json")
    assert result.exit_code == 0
    assert json.loads(result.output)["name"] == "demo"
    assert invoke("validate").exit_code == 0
    assert invoke("validate", "--variants").exit_code == 0


def test_explicit_sync_target_and_option_scope(invoke):
    assert invoke("maintainer", "sync").exit_code == 2
    assert invoke("self-service", "--dry-run").exit_code == 2
    assert invoke("self-service", "tools", "--dry-run").exit_code == 0
    for args in (
        ("skills", "ruff"),
        ("skills", "--diff"),
        ("configs", "--diff", "--check"),
        ("configs", "--output", "tasks.json"),
    ):
        assert invoke("maintainer", "sync", *args).exit_code == 2


def test_preview_never_installs_tools_or_hooks(invoke, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("preview attempted installation")

    monkeypatch.setattr(ToolService, "setup", forbidden)
    monkeypatch.setattr(EnsureHooks, "execute", forbidden)
    for args in (
        ("build", "--dry-run", "--setup"),
        ("run", "build", "--dry-run", "--setup"),
    ):
        result = invoke(*args)
        assert result.exit_code == 0, result.output
    assert invoke("build", "--env").exit_code == 2


def test_html_and_terminal_help_expose_canonical_order(invoke, tmp_path):
    result = invoke("--help")
    assert result.exit_code == 0
    text = Text.from_ansi(result.output).plain
    assert (
        text.index("Jobs (from")
        < text.index("Commands")
        < text.index("Self-service")
        < text.index("Maintenance")
    )
    assert cli.commands["run"].hidden and cli.commands["describe"].hidden
    output = tmp_path / "help.html"
    result = invoke("help", "--no-open", "-o", str(output))
    assert result.exit_code == 0, result.output
    html = output.read_text()
    for command in (
        "ptk validate",
        "ptk self-service creds set",
        "ptk maintainer sync",
    ):
        assert command in html
    for command in ("ptk setup", "ptk dry-run", "ptk self-setup"):
        assert command not in html
