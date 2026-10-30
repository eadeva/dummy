"""Exercise Click's completion protocol without invoking command callbacks."""

import os
import shlex
import shutil
import subprocess
import sys

import pytest
from click.shell_completion import get_completion_class
from click.testing import CliRunner

from ptk.adapters.git_metadata import GitMetadata
from ptk.application.use_cases.project import LoadProject
from ptk.bootstrap import App
from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer
from tests.project_files import read_project, write_project, write_workflows
from tests.test_command_access import snapshot
from tests.test_workspace import workspace


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PTK_CI", "false")
    monkeypatch.setenv("PTK_ROLE", "user")
    return write_project(
        tmp_path / ".main.ptk.yml",
        {
            "project": {"name": "completion", "default_job": "build"},
            "variants": {
                "variants": {
                    "base": {"abstract": True},
                    "debug": {"aliases": ["dev"]},
                    "release": {},
                }
            },
            "jobs": {
                "build": {
                    "help": "Build the project",
                    "params": {
                        "build_type": {
                            "type": "choice",
                            "choices": ["Debug", "Release"],
                        },
                        "enabled": {"type": "bool"},
                        "folder": {"type": "path"},
                        "token": {"type": "secret", "env": "COMPLETION_SECRET"},
                        "branch": {"default": "${git.branch}"},
                    },
                    "steps": {
                        "configure": {"run": "echo config"},
                        "compile": {"run": "echo build", "needs": ["configure"]},
                    },
                },
                "publish": {
                    "audience": "maintainer",
                    "steps": {"push": {"run": "echo push"}},
                },
                "ci-only": {"only_cx": True, "steps": {"push": {"run": "echo push"}}},
            },
            "workflows": {
                "all": {"help": "Build everything", "jobs": {"make": {"job": "build"}}},
                "private": {
                    "audience": "maintainer",
                    "jobs": {"make": {"job": "build"}},
                },
            },
        },
    )


def complete(args=(), incomplete="", shell="bash"):
    engine = get_completion_class(shell)(cli, {}, "ptk", "_PTK_COMPLETE")
    return {item.value for item in engine.get_completions(list(args), incomplete)}


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
def test_registration_outside_project_and_file_output(tmp_path, monkeypatch, shell):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    args = ["self-service", "completion", shell]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "_PTK_COMPLETE" in result.output and f"{shell}_complete" in result.output
    target = tmp_path / "completion script.txt"
    saved = runner.invoke(cli, [*args, "--output", str(target)])
    assert saved.exit_code == 0, saved.output
    assert target.read_text(encoding="utf-8") == result.output
    assert not (tmp_path / ".main.ptk.yml").exists()


@pytest.mark.parametrize("shell", ["bash", "powershell", "zsh", "fish"])
def test_commands_options_and_typed_values(project, shell):
    assert {"build", "all", "self-service", "variant", "workflow"} <= complete(
        shell=shell
    )
    assert not {"publish", "private", "ci-only", "self-setup"} & complete(shell=shell)
    assert complete(incomplete="bu", shell=shell) == {"build"}
    assert {"--build-type", "--enabled", "--no-enabled", "--only-step"} <= complete(
        ["build"], "--", shell
    )
    assert complete(["build", "--build-type"], "D", shell) == {"Debug"}
    assert complete(["build", "--dry-run", "--only-step"], "con", shell) == {
        "configure"
    }
    assert complete(["build", "--to"], "com", shell) == {"compile"}
    assert complete(["maintainer", "config", "show", "--format"], "j", shell) == set()


@pytest.mark.parametrize(
    "args",
    [
        ["run"],
        ["report", "open"],
        ["report", "export"],
        ["self-service", "tools", "--job"],
    ],
)
def test_job_arguments_and_options(project, args):
    assert complete(args) == {"build"}


@pytest.mark.parametrize("command", ["show", "run"])
def test_workflow_names(project, command):
    assert complete(["workflow", command]) == {"all"}


def test_variants_aliases_and_comma_selections(project):
    assert complete(["--variant"]) == {"debug", "dev", "release"}
    assert complete(["--variant"], "debug,r") == {"debug,release"}
    assert "debug,debug" not in complete(["--variant"], "debug,")
    assert complete(["variant", "show"], "d") == {"debug", "dev"}
    assert complete(["--variant"], "r") == {"release"}


def test_generic_parameters_never_complete_secrets(project, monkeypatch):
    monkeypatch.setenv("COMPLETION_SECRET", "do-not-suggest-this")
    assert complete(["run", "build", "--param"], "b") == {"build_type=", "branch="}
    assert complete(["run", "build", "--param"], "build-type=R") == {
        "build-type=Release"
    }
    assert complete(["run", "--param"], "enabled=") == {"enabled=true", "enabled=false"}
    assert complete(["run", "build", "--param"], "token=") == set()
    assert complete(["run", "build", "--param"], "branch=") == set()


def test_completion_is_read_only_and_loads_once(project, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail(
            "completion must not initialize plugins, discover Git, run or prompt"
        )

    monkeypatch.setattr(App, "configure_project", forbidden)
    monkeypatch.setattr(GitMetadata, "discover", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr("ptk.drivers.cli.jobs.click.prompt", forbidden)
    before = snapshot(project.parent)
    loaded = []
    original = LoadProject.execute

    def load(self, *args, **kwargs):
        loaded.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LoadProject, "execute", load)
    assert "build" in complete()
    assert loaded == [1]
    assert snapshot(project.parent) == before
    assert complete(["build", "--build-type"], "D") == {"Debug"}
    assert complete(["workflow", "run"], "a") == {"all"}
    assert snapshot(project.parent) == before


def test_job_workflow_collision_never_prompts(project, monkeypatch):
    model = read_project(project)
    model["workflows"]["build"] = {"jobs": {"make": {"job": "build"}}}
    write_project(project, model)

    def forbidden(*args, **kwargs):
        pytest.fail("completion must not prompt")

    monkeypatch.setattr("ptk.drivers.cli.jobs.click.prompt", forbidden)
    assert "--build-type" in complete(["build"], "--b")


def test_registration_and_static_completions_with_broken_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for content in (
        None,
        "broken: [",
        "repository: {alias: demo, config_path: missing}",
    ):
        if content:
            (tmp_path / ".main.ptk.yml").write_text(content)
        assert {"self-service", "variant"} <= complete()
        assert "completion" in complete(["self-service"])
        result = CliRunner().invoke(cli, ["self-service", "completion", "powershell"])
        assert result.exit_code == 0, result.output


def test_permission_changes_are_seen_on_next_completion(project, monkeypatch):
    assert "publish" not in complete()
    grant_maintainer(project.parent)
    monkeypatch.delenv("PTK_ROLE")
    assert "publish" not in complete()
    assert "publish" in complete(["maintainer"])
    assert complete(["maintainer", "config", "show", "--format"], "j") == {"json"}
    assert "build" in complete(["maintainer", "artifacts", "destination", "--job"])
    assert "private" in complete(["maintainer", "workflow", "show"])
    assert "private" not in complete(["workflow", "show"])


@pytest.mark.parametrize("broken", ["member", "alias"])
def test_invalid_vmr_keeps_static_completion_available(tmp_path, monkeypatch, broken):
    a, _ = workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    if broken == "member":
        (a.parent / "config/project.ptk.yml").write_text("name: [")
    else:
        a.write_text("repository: {alias: self-service, config_path: config}")
    assert {"self-service", "workflow"} <= complete()
    assert "completion" in complete(["self-service"])
    result = CliRunner().invoke(cli, ["self-service", "completion", "powershell"])
    assert result.exit_code == 0, result.output


def test_vmr_repositories_jobs_workflows_and_variants(tmp_path, monkeypatch):
    a, _ = workspace(tmp_path)
    model = read_project(a)
    model["variants"] = {"variants": {"debug": {"aliases": ["dev"]}}}
    model["workflows"] = {"all": {"jobs": {"make": {"job": "build"}}}}
    write_project(a, model)
    write_workflows(
        tmp_path / "workflows",
        {"everything": {"jobs": {"make": {"job": "firmware:build"}}}},
    )
    monkeypatch.chdir(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("completion must not configure repository plugins")

    monkeypatch.setattr(App, "configure_project", forbidden)
    assert {"firmware", "bootloader", "everything"} <= complete()
    assert "build" in complete(["firmware"])
    assert "--only-step" in complete(["firmware", "build"], "--")
    assert complete(["firmware", "build", "--only-step"], "h") == {"hello"}
    assert complete(["--variant"], "d") == {"debug", "dev"}
    assert complete(["firmware", "variant", "show"], "d") == {"debug", "dev"}
    assert complete(["workflow", "run"], "f") == {"firmware/all"}
    assert complete(["firmware", "workflow", "run"]) == {"all"}
    result = CliRunner().invoke(cli, ["self-service", "completion", "powershell"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "shell,expected",
    [
        ("bash", "plain,Debug"),
        ("powershell", "plain\nDebug\n"),
    ],
)
def test_native_completion_protocol(project, shell, expected):
    result = CliRunner().invoke(
        cli,
        [],
        prog_name="ptk",
        env={
            "_PTK_COMPLETE": f"{shell}_complete",
            "COMP_WORDS": "ptk build --build-type D",
            "COMP_CWORD": "3",
        },
    )
    assert result.exit_code == 0, result.output
    assert expected in result.output
    assert "error" not in result.output.lower()


@pytest.mark.skipif(
    not shutil.which("bash") or sys.platform == "win32", reason="requires Bash"
)
def test_generated_bash_script_calls_real_ptk(project, tmp_path):
    executable = tmp_path / "ptk"
    executable.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m ptk "$@"\n'
    )
    executable.chmod(0o755)
    script = tmp_path / "completion.bash"
    result = CliRunner().invoke(
        cli, ["self-service", "completion", "bash", "-o", str(script)]
    )
    assert result.exit_code == 0, result.output
    result = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            """
source "$1"
COMP_WORDS=(ptk build --build-type D)
COMP_CWORD=3
_ptk_completion ptk
printf '%s\n' "${COMPREPLY[@]}"
""",
            "bash",
            str(script),
        ],
        cwd=tmp_path,
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Debug"


def test_powershell_double_tab_is_explicit_and_shell_specific(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    normal = runner.invoke(cli, ["self-service", "completion", "powershell"])
    assert "Set-PSReadLineKeyHandler" not in normal.output
    listing = runner.invoke(
        cli, ["self-service", "completion", "powershell", "--double-tab"]
    )
    assert listing.exit_code == 0, listing.output
    assert "Set-PSReadLineKeyHandler -Key Tab -Function Complete" in listing.output
    assert "Register-ArgumentCompleter" in listing.output
    invalid = runner.invoke(cli, ["self-service", "completion", "bash", "--double-tab"])
    assert invalid.exit_code == 2 and "PowerShell option" in invalid.output
