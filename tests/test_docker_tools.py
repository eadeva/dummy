"""Docker installation policy leaves dependency checks and activation intact."""

from pathlib import Path

import pytest

from ptk.adapters.host import SystemHost
from ptk.application.ports import ProcessOutcome
from ptk.application.use_cases.tools import ToolService, tools_for_jobs
from ptk.domain.config.model import ToolSpec
from ptk.domain.tools import tool_identity


class Runner:
    def __init__(self, output=None):
        self.output = output
        self.calls = []

    def run(self, command, on_output, cancel=None):
        self.calls.append(command)
        if self.output:
            on_output(self.output)
        return ProcessOutcome(0 if self.output else 1)

    def which(self, program, path=None):
        return "/image/compiler" if self.output else None


class Installer:
    def __init__(self):
        self.installed = []

    def bin_dirs(self, tools=None):
        return ["/managed/compiler"] if tools else []

    def clean_environment(self, env):
        return dict(env)

    def install(self, name, method, out):
        self.installed.append(name)


@pytest.fixture
def project(write, load):
    return load(
        write(
            {
                ".main.ptk.yml": """
project: {name: docker-example}
tools:
  compiler:
    version: '>=12'
    check: compiler --version
    uv_tool: compiler==12.0
requires_tools: [compiler]
jobs:
  build:
    requires_tools: [compiler]
    steps:
      - hello: echo hello
"""
            }
        )
    )


@pytest.mark.parametrize("output", [None, "compiler 11.0", "compiler 12.0"])
def test_docker_checks_and_paths_remain_but_install_never_runs(project, output):
    runner, installer = Runner(output), Installer()
    service = ToolService(SystemHost({"PTK_DOCKER": "1"}), runner, installer)
    assert service.paths(project) == ["/managed/compiler"]
    [result] = service.setup(project, ["compiler"])
    assert runner.calls
    assert installer.installed == []
    assert result.ok == (output == "compiler 12.0")
    if result.ok:
        assert result.before.version == "12.0"
        assert result.before.source == "/image/compiler"
    else:
        assert "disabled inside Docker" in result.outcome
    [preview] = service.setup(project, ["compiler"], dry_run=True)
    assert preview.ok == result.ok


def test_host_install_and_job_override(project):
    runner, installer = Runner(), Installer()
    service = ToolService(SystemHost({"PTK_DOCKER": "0"}), runner, installer)
    service.setup(project, ["compiler"])
    assert installer.installed == ["compiler"]
    project.config.jobs["build"].requires_tools = {"compiler": ToolSpec(docker=True)}
    selected = tools_for_jobs(project, ["build"])
    service = ToolService(SystemHost({"PTK_DOCKER": "1"}), runner, installer)
    service.setup(selected, ["compiler"])
    assert installer.installed == ["compiler", "compiler"]


def test_policy_does_not_change_installation_identity():
    spec = ToolSpec(uv_tool="compiler==12.0")
    assert tool_identity(spec) == tool_identity(
        spec.model_copy(update={"docker": True})
    )


def test_docker_detection(monkeypatch):
    monkeypatch.setattr(Path, "is_file", lambda path: path == Path("/.dockerenv"))
    assert SystemHost({}).is_docker()
    assert not SystemHost({"PTK_DOCKER": "0"}).is_docker()
    monkeypatch.setattr(Path, "is_file", lambda _: False)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *args, **kwargs: "0::/system.slice/docker-abc123.scope",
    )
    assert SystemHost({}).is_docker()
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: "0::/user.slice")
    assert not SystemHost({}).is_docker()
    assert SystemHost({"PTK_DOCKER": "1"}).is_docker()
    assert SystemHost({"container": "docker"}).is_docker()
