"""Bound startup work without timing thresholds that vary across machines."""

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from ptk.adapters.config import yaml_loader
from ptk.adapters.host import SystemHost
from ptk.application.use_cases.project import LoadProject
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def make_project(root):
    file = root / ".main.ptk.yml"
    write_project(
        file,
        """\
repository:
  alias: demo
  config_path: .
project:
  name: demo
jobs:
  build:
    steps:
      hello:
        uses: echo
credentials:
  remote:
    providers:
    - env
    - keyring
    - vault
""",
        encoding="utf-8",
    )
    (root / "maintainers.ptk.yml").write_text(
        "maintainers: [alice]\n", encoding="utf-8"
    )
    return file


def test_help_loads_project_and_identity_once_per_invocation(tmp_path, monkeypatch):
    file = make_project(tmp_path)
    calls = Counter()
    original_load = LoadProject.execute

    def load(self, *args, **kwargs):
        calls["load"] += 1
        return original_load(self, *args, **kwargs)

    def user_id(self):
        calls["identity"] += 1
        return "alice"

    monkeypatch.setattr(LoadProject, "execute", load)
    monkeypatch.setattr(SystemHost, "user_id", user_id)
    runner = CliRunner(env={"PTK_ROLE": ""})
    args = ["--help"]
    result = runner.invoke(cli, args, cwd=Path(file).parent)
    assert result.exit_code == 0 and "maintainer" in result.output, result.output
    assert calls == {"load": 1, "identity": 1}
    # Permissions and configuration must be reread on the next invocation.
    (tmp_path / "maintainers.ptk.yml").write_text("maintainers: []\n")
    result = runner.invoke(cli, args, cwd=Path(file).parent)
    assert result.exit_code == 0 and "maintainer" not in result.output, result.output
    assert calls == {"load": 2, "identity": 2}


def test_failed_configuration_is_loaded_once_but_retry_next_invocation(
    tmp_path, monkeypatch
):
    file = make_project(tmp_path)
    valid = file.read_text()
    file.write_text(valid + "include: missing.ptk.yml\n")
    calls = []
    original = LoadProject.execute

    def load(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(LoadProject, "execute", load)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    args = ["--help"]
    assert runner.invoke(cli, args, cwd=Path(file).parent).exit_code == 0
    assert len(calls) == 1
    file.write_text(valid)
    result = runner.invoke(cli, args, cwd=Path(file).parent)
    assert result.exit_code == 0 and "build" in result.output
    assert len(calls) == 2


@pytest.mark.parametrize(
    "args", [["--help"], ["self-service", "--help"], ["build", "--help"]]
)
def test_help_does_not_import_or_construct_runtime_services(tmp_path, args):
    file = make_project(tmp_path)
    code = """
import sys
from click.testing import CliRunner
from ptk.drivers.cli.main import cli
result = CliRunner(env={'PTK_ROLE': 'user'}).invoke(cli, sys.argv[1:])
assert result.exit_code == 0, result.output
unused = ['ptk.adapters.tools', 'ptk.adapters.python_env', 'ptk.adapters.reporting.store',
          'ptk.adapters.credentials.vault', 'ptk.application.use_cases.run',
          'ptk.application.use_cases.workflow', 'ptk.adapters.hooks', 'cryptography']
assert not set(unused).intersection(sys.modules), sorted(set(unused).intersection(sys.modules))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=file.parent,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_yaml_diagnostic_filename_is_computed_once_per_file(tmp_path, monkeypatch):
    file = tmp_path / "many.ptk.yml"
    file.write_text(json.dumps({"vars": {f"v{i}": i for i in range(100)}}))
    calls = []
    original = yaml_loader._display

    def display(path, root):
        calls.append(path)
        return original(path, root)

    monkeypatch.setattr(yaml_loader, "_display", display)
    tree = yaml_loader.YamlConfigReader(display_root=tmp_path).read(file)
    assert len(tree.value["vars"].value) == 100
    assert calls == [file]
    assert tree.value["vars"].value["v99"].loc.file == "many.ptk.yml"
