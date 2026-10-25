"""Grouped setup navigation, compatibility, and side-effect boundaries."""

import json
import re

import pytest
from click.testing import CliRunner
from rich.text import Text

from ptk.drivers.cli.main import cli


@pytest.fixture
def invoke(write):
    root = write({"main.ptk.yml": "project: {name: demo}\n"})

    def call(*args):
        return CliRunner().invoke(
            cli,
            ["-c", str(root / "main.ptk.yml"), "--no-ci", *args],
            catch_exceptions=False,
        )

    return call


def test_setup_is_a_navigation_group(invoke):
    result = invoke("setup")
    assert result.exit_code == 0
    text = Text.from_ansi(result.output).plain
    for name in ("install", "config", "configs", "creds", "self", "doctor", "vscode"):
        assert name in text
    assert "would install" not in text
    for old in ("config", "configs", "creds", "self-setup", "doctor", "vscode"):
        assert cli.commands[old].hidden
        assert (
            not cli.commands["setup"]
            .commands["self" if old == "self-setup" else old]
            .hidden
        )


@pytest.mark.parametrize("command", ["config", "configs", "creds", "vscode"])
def test_nested_help_and_legacy_aliases(invoke, command):
    assert invoke("setup", command, "--help").exit_code == 0
    assert invoke(command, "--help").exit_code == 0


def test_nested_config_uses_root_options(invoke):
    result = invoke("setup", "config", "show", "project", "--format", "json")
    assert result.exit_code == 0
    assert json.loads(result.output)["name"] == "demo"
    assert invoke("setup", "config", "validate").exit_code == 0


def test_legacy_install_options_and_canonical_install(invoke):
    legacy = invoke("setup", "--dry-run")
    canonical = invoke("setup", "install", "--dry-run")
    assert legacy.exit_code == canonical.exit_code == 0
    assert legacy.output == canonical.output


def test_group_options_cannot_be_silently_ignored(invoke):
    result = invoke("setup", "--allow-system", "config", "validate")
    assert result.exit_code == 2
    assert "after 'setup install'" in result.output


def test_html_help_lists_canonical_tree(invoke, tmp_path):
    output = tmp_path / "help.html"
    result = invoke("help", "--no-open", "-o", str(output))
    assert result.exit_code == 0
    html = output.read_text()
    assert "ptk setup config validate" in html
    assert "ptk setup creds set" in html
    assert 'id="cmd-config-validate"' not in html


def test_root_help_hides_legacy_aliases(invoke):
    result = invoke("--help")
    assert result.exit_code == 0
    output = Text.from_ansi(result.output).plain
    assert re.search(r"(?m)^\s*[│|]?\s*setup\s{2,}", output)
    for name in ("config", "configs", "creds", "self-setup", "doctor", "vscode"):
        assert not re.search(rf"(?m)^\s*[│|]?\s*{name}\s{{2,}}", output), output
