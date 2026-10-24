"""HTML help and maintainer visibility."""

from __future__ import annotations

from click.testing import CliRunner

from ptk.adapters.help_html import render
from ptk.application.use_cases.help import BuildHelp
from ptk.application.use_cases.role import resolve_role
from ptk.bootstrap import create_app
from ptk.drivers.cli.main import cli
from tests.conftest import DEMO


class Host:
    def __init__(self, variables=None, email=None, user=None):
        self.variables = variables or {}
        self._identity = (email, user)

    def is_ci(self):
        return False

    def os_name(self):
        return "linux"

    def user_identity(self):
        return self._identity


def demo_project():
    return create_app(environ={}).load_project.execute(DEMO)


def test_role_from_maintainers_file_and_override():
    project = demo_project()
    emails = [m.email for m in project.maintainers.maintainers if m.email]
    assert resolve_role(project, Host(email=emails[0].upper())) == "maintainer"
    assert (
        resolve_role(project, Host(email="someone@else.org", user="nobody")) == "user"
    )
    assert resolve_role(project, Host({"PTK_ROLE": "maintainer"})) == "maintainer"
    assert resolve_role(None, Host()) == "user"


def test_users_do_not_see_maintainer_actions():
    project = demo_project()
    user = BuildHelp("1.0").execute(project, [], "user")
    assert [a.name for a in user.actions] == ["build"] and user.hidden_actions == 1
    maint = BuildHelp("1.0").execute(project, [], "maintainer")
    assert [a.name for a in maint.actions] == ["build", "deploy"]


def test_rendered_page_shows_pipeline_and_escapes():
    doc = BuildHelp("1.0").execute(demo_project(), [], "maintainer")
    doc.description = "<script>alert(1)</script>"
    html = render(doc)
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html
    assert 'class="lanes"' in html and "runs in parallel" in html
    assert "only if <code>COMPONENT_CAMERA and DISPLAY_SIZE &gt;= 10</code>" in html
    assert "https://" not in html  # self-contained, works offline


def test_help_command_writes_page(tmp_path):
    out = tmp_path / "help.html"
    result = CliRunner().invoke(
        cli,
        ["--config", str(DEMO / "main.ptk.yml"), "help", "--no-open", "-o", str(out)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    html = out.read_text()
    for text in (
        "ptk build [OPTIONS]",
        "ptk variant show",
        "ptk dry-run build",
        "customer_a_high",
    ):
        assert text in html


def test_help_without_project_still_lists_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "h.html"
    result = CliRunner().invoke(
        cli, ["help", "--no-open", "-o", str(out)], catch_exceptions=False
    )
    assert result.exit_code == 0
    html = out.read_text()
    assert "could not be loaded" in html and "ptk config validate" in html
