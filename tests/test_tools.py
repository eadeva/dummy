"""Tools: version checks, install methods, ptk setup, --setup, doctor, self-setup."""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.adapters.tools import SystemToolInstaller
from ptk.application.ports import ProcessOutcome
from ptk.domain.config.model import ToolSpec
from ptk.domain.errors import PtkError
from ptk.domain.tools import check_version, install_methods, parse_version, satisfies
from ptk.drivers.cli.main import cli

posix_only = pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX shell")


def test_versions():
    assert (
        parse_version("cmake version 3.30.2\nCMake suite", r"(\d+\.\d+(?:\.\d+)?)")
        == "3.30.2"
    )
    assert satisfies("3.30.2", ">=3.28,<4") and not satisfies("4.0", ">=3.28,<4")
    assert satisfies("18.1.8", "==18.*")
    spec = ToolSpec(version=">=2", check="x --version")
    assert check_version("x", spec, None).problem == "not found"
    assert "does not match" in check_version("x", spec, "x 1.5").problem
    assert "cannot read" in check_version("x", spec, "no digits").problem
    assert check_version("x", spec, "x 2.1.0").ok


def test_install_order():
    spec = ToolSpec(
        choco={"package": "cmake", "version": "3.30.2"},
        uv_tool="cmake",
        download={"linux": {"url": "file:///x.tgz"}},
        apt="cmake",
    )
    assert [m.kind for m in install_methods(spec, "windows", allow_system=True)] == [
        "choco",
        "uv_tool",
    ]
    assert [m.kind for m in install_methods(spec, "linux", allow_system=False)] == [
        "uv_tool",
        "download",
    ]
    assert [m.kind for m in install_methods(spec, "linux", allow_system=True)][
        -1
    ] == "apt"
    assert (
        install_methods(spec, "windows", allow_system=False)[0].describe()
        == "choco install cmake --version 3.30.2"
    )


class FakeRunner:
    def __init__(self):
        self.calls: list[list[str]] = []

    def run(self, command, on_output, cancel=None):
        self.calls.append(command.argv or [command.shell])
        return ProcessOutcome(0)

    def which(self, program, path=None):
        return None


def test_chocolatey_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ptk.adapters.tools.shutil.which",
        lambda program, path=None: str(tmp_path / "choco") if path else None,
    )
    env = {"PATH": str(tmp_path)}
    method = install_methods(
        ToolSpec(choco={"package": "llvm", "version": "18.1.8"}),
        "windows",
        allow_system=False,
    )[0]
    runner = FakeRunner()
    no_admin = SystemToolInstaller(
        runner, env, admin=lambda: False, windows=True, tools_dir=tmp_path
    )
    with pytest.raises(PtkError, match="administrator terminal"):
        no_admin.install("llvm", method, print)
    admin = SystemToolInstaller(
        runner, env, admin=lambda: True, windows=True, tools_dir=tmp_path
    )
    admin.install("llvm", method, print)
    assert runner.calls[-1] == [
        "choco",
        "install",
        "llvm",
        "-y",
        "--no-progress",
        "--version",
        "18.1.8",
        "--allow-downgrade",
    ]
    missing = SystemToolInstaller(
        runner, {"PATH": ""}, admin=lambda: True, windows=True
    )
    with pytest.raises(PtkError, match="bootstrap-choco"):
        missing.install("llvm", method, print)


def make_tool_archive(folder: Path) -> tuple[str, str]:
    script = b"#!/bin/sh\necho mytool 1.2.3\n"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("mytool-1.2.3/bin/mytool")
        info.size = len(script)
        info.mode = 0o755
        archive.addfile(info, io.BytesIO(script))
    path = folder / "mytool.tar.gz"
    path.write_bytes(buffer.getvalue())
    return path.as_uri(), hashlib.sha256(buffer.getvalue()).hexdigest()


PROJECT = """
project: {{name: tools, default_action: build}}
tools:
  mytool:
    version: ">=1.2,<2"
    check: mytool --version
    download: {{linux: {{url: "{url}", sha256: "{sha}", bin: bin}}}}
  ancient:
    version: ">=99"
    check: sh -c "echo ancient 1.0"
    apt: ancient-pkg
actions:
  build:
    requires_tools: [mytool]
    steps: [{{use: "mytool --version"}}]
  other:
    requires_tools: [ancient]
    steps: [{{x: "true"}}]
"""


@pytest.fixture
def project(write, tmp_path):
    url, sha = make_tool_archive(tmp_path)
    root = write({".main.ptk.yml": PROJECT.format(url=url, sha=sha)})
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "PTK_TOOLS_DIR": str(tmp_path / "tools"),
        "PTK_ROLE": "user",
        "PTK_VAULT_FILE": str(tmp_path / "vault.json"),
    }

    def invoke(*args):
        base = ["--config", str(root / ".main.ptk.yml"), "--no-ci"]
        return CliRunner(env=env).invoke(cli, [*base, *args], catch_exceptions=False)

    invoke.root = root
    invoke.tools = tmp_path / "tools"
    invoke.write_sha = lambda sha: (root / ".main.ptk.yml").write_text(
        PROJECT.format(url=url, sha=sha)
        + "\nrepository: {alias: demo, config_path: .}\n"
    )
    return invoke


@posix_only
def test_missing_tool_blocks_run(project):
    result = project("build")
    assert result.exit_code == 2
    assert (
        "mytool: not found" in result.output
        and "ptk setup install --action build" in result.output
    )
    assert project("dry-run", "build").exit_code == 0  # dry runs never block


@posix_only
def test_setup_installs_download_and_puts_it_on_path(project):
    preview = project("setup", "--action", "build", "--dry-run")
    assert "would install via download" in preview.output and not project.tools.exists()
    result = project("setup", "--action", "build")
    assert result.exit_code == 0, result.output
    assert "mytool 1.2.3" in result.output and "installed via download" in result.output
    assert (project.tools / "mytool" / "bin" / "mytool").is_file()
    ran = project("build")
    assert ran.exit_code == 0 and "mytool 1.2.3" in ran.output


@posix_only
def test_run_with_setup_flag(project):
    result = project("build", "--setup")
    assert result.exit_code == 0, result.output
    assert "installed via download" in result.output


@posix_only
def test_checksum_mismatch(project):
    project.write_sha("0" * 64)
    result = project("setup", "--action", "build")
    assert result.exit_code == 1 and "sha256 mismatch" in result.output


@posix_only
def test_wrong_version_and_system_packages(project):
    result = project("setup", "--action", "other")
    assert result.exit_code == 1
    assert (
        "does not match >=99" in result.output or "no install method" in result.output
    )
    assert "--allow-system" in result.output


@posix_only
def test_doctor_reports_tool_problems(project):
    result = project("doctor")
    assert result.exit_code == 1
    assert "tool mytool" in result.output and "ptk setup" in result.output


@posix_only
def test_self_setup(project):
    (project.root / ".main.ptk.yml").write_text(
        (project.root / ".main.ptk.yml").read_text() + "configs: {clang-format: {}}\n"
    )
    result = project("self-setup")
    assert (
        "shared configs" in result.output and (project.root / ".clang-format").is_file()
    )


def test_per_os_download_is_validated(write, load):
    from ptk.domain.errors import ConfigError

    root = write(
        {
            ".main.ptk.yml": """
        project: {name: t}
        tools:
          a: {download: {linux: {urll: "x"}}}
        """
        }
    )
    with pytest.raises(ConfigError, match="unknown key 'urll'"):
        load(root)
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: t}
        tools:
          a: {download: {linux: {url: "file:///x"}, windows: {url: "file:///y"}}}
        """
        }
    )
    assert load(root).config.tools["a"].download["windows"].url == "file:///y"
