"""HTML help and maintainer visibility."""

from __future__ import annotations

from ptk.adapters.help_html import render
from ptk.application.use_cases.help import BuildHelp
from ptk.application.use_cases.role import resolve_role
from ptk.bootstrap import create_app
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import DEMO


class Host:
    def __init__(self, variables=None, email=None, user=None):
        self.variables = variables or {}
        self._identity = (email, user)

    def is_ci(self):
        return False

    def os_name(self):
        return "linux"

    def user_id(self):
        return self._identity[1]


def demo_project():
    return create_app(environ={}).load_project.execute(
        config_file=DEMO / ".main.ptk.yml"
    )


def test_role_from_login_ids_and_only_downward_override():
    project = demo_project()
    users = project.maintainers.maintainers
    assert resolve_role(project, Host(user=users[0].upper())) == "maintainer"
    assert (
        resolve_role(project, Host(email="someone@else.org", user="nobody")) == "user"
    )
    assert resolve_role(project, Host({"PTK_ROLE": "maintainer"})) == "user"
    assert resolve_role(project, Host({"PTK_ROLE": "user"}, user=users[0])) == "user"
    assert resolve_role(project, Host(email=users[0])) == "user"
    assert resolve_role(None, Host()) == "user"


def test_users_do_not_see_maintainer_jobs():
    project = demo_project()
    user = BuildHelp("1.0").execute(project, [], "user")
    assert [a.name for a in user.jobs] == ["build"] and user.hidden_jobs == 1
    maint = BuildHelp("1.0").execute(project, [], "maintainer")
    assert [a.name for a in maint.jobs] == ["build", "deploy"]


def test_rendered_page_shows_pipeline_and_escapes():
    doc = BuildHelp("1.0").execute(demo_project(), [], "maintainer")
    doc.description = "<script>alert(1)</script>"
    html = render(doc)
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html
    assert "needs: compile" in html and "--only-step" in html
    assert (
        "only if <code>COMPONENT_CAMERA and display.DISPLAY_SIZE &gt;= 10</code>"
        in html
    )
    assert "https://" not in html  # self-contained, works offline


def test_help_command_writes_page(tmp_path):
    import shutil

    demo = shutil.copytree(DEMO, tmp_path / "demo")
    out = tmp_path / "help.html"
    result = CliRunner().invoke(
        cli, ["help", "--no-open", "-o", str(out)], catch_exceptions=False, cwd=demo
    )
    assert result.exit_code == 0, result.output
    html = out.read_text()
    for text in (
        "ptk build [OPTIONS]",
        "ptk variant show",
        "ptk build --dry-run",
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
    assert "could not be loaded" in html and "ptk validate" in html
