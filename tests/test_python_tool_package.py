"""An ordinary wheel runs through uv without importing PTK into its environment."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def test_packaged_cli_runs_through_uv_in_a_project(tmp_path):
    pytest.importorskip("build")
    pytest.importorskip("hatchling")
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the native Python tool check")
    source = Path(__file__).parents[1] / "examples/python-tool"
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path / "dist"),
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheel = next((tmp_path / "dist").glob("*.whl"))
    project = tmp_path / "consumer"
    project.mkdir()
    (project / "manifest.json").write_text("{}")
    write_project(
        project / ".main.ptk.yml",
        yaml.safe_dump(
            {
                "project": {"name": "consumer"},
                "jobs": {
                    "verify": {
                        "steps": {
                            "check": {
                                "python": {"uvx": str(wheel)},
                                "run": ["ptk-example-check", "manifest.json"],
                                "env": {"UV_OFFLINE": "1"},
                            }
                        }
                    }
                },
            }
        ),
    )
    runner = CliRunner(env={"PTK_UV": uv})
    success = runner.invoke(cli, ["verify"], cwd=project)
    assert success.exit_code == 0 and "Required file exists" in success.output, (
        success.output
    )
    (project / "manifest.json").unlink()
    failure = runner.invoke(cli, ["verify"], cwd=project)
    assert failure.exit_code == 1 and "Required file is missing" in failure.output, (
        failure.output
    )
