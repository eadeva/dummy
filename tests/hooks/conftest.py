"""Real Git/pre-commit tests; only package acquisition is replaced."""

import os
import shlex
import subprocess
import sys

import pytest
import yaml

from ptk.adapters.hooks import GIT_PATH_VARIABLES, GitHooks
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def git(root, *args, check=True):
    return subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Hook Test",
            "-c",
            "user.email=hooks@example.invalid",
            *args,
        ],
        env={k: v for k, v in os.environ.items() if k not in GIT_PATH_VARIABLES},
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


def repository(root, *, alias="app", enabled=True, output=None):
    root.mkdir(parents=True, exist_ok=True)
    spec = {"enabled": enabled}
    if output:
        spec["output"] = output
    write_project(
        root / ".main.ptk.yml",
        {
            "repository": {"alias": alias, "config_path": "config"},
            "project": {"name": alias},
            "configs": {"pre-commit": spec},
            "jobs": {
                "build": {
                    "open_report": None,
                    "steps": [
                        {
                            "run": {
                                "run": [
                                    sys.executable,
                                    "-c",
                                    "from pathlib import Path; Path('job-ran').touch()",
                                ]
                            }
                        }
                    ],
                }
            },
        },
    )
    config = root / (output or ".pre-commit-config.yaml")
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        yaml.safe_dump(
            {
                "repos": [
                    {
                        "repo": "local",
                        "hooks": [
                            {
                                "id": "proof",
                                "name": "proof",
                                "language": "system",
                                "always_run": True,
                                "pass_filenames": False,
                                "entry": shlex.join(
                                    [
                                        sys.executable,
                                        "-c",
                                        "from pathlib import Path; Path('hook-ran').touch(); raise SystemExit(1 if Path('block-commit').exists() else 0)",
                                    ]
                                ),
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    git(root, "init")
    return root


def invoke(root, *args):
    return CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"}).invoke(
        cli, [*args], catch_exceptions=False, cwd=root
    )


@pytest.fixture(autouse=True)
def offline_engine(monkeypatch, tmp_path):
    # Install scripts with the real framework already installed by the dev group.
    # No hook downloads: the fixture uses only a local, language: system hook.
    calls = []
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "pre-commit-cache"))

    def runtime(self, target, out):
        calls.append(target)
        return sys.executable

    monkeypatch.setattr(GitHooks, "_runtime", runtime)
    return calls
