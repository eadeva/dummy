"""Real hook bootstrap and environment-changing hooks must leave PTK intact."""

import importlib.metadata
import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

import pytest
import yaml

from ptk.adapters.hooks import PYTHON_ENV_VARIABLES, GitHooks
from ptk.adapters.process import SubprocessRunner
from ptk.adapters.python_env import venv_python

UV = shutil.which("uv")


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "consumer with spaces"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "consumer"\nversion = "0.0.0"\n'
        'requires-python = ">=3.12"\ndependencies = []\n',
        encoding="utf-8",
    )
    return root


class OfflineBootstrap(SubprocessRunner):
    """Exercise real uv creation and installation, with an offline framework wheel."""

    def __init__(self):
        self.installs = []

    def run(self, command, on_output, cancel=None):
        argv = command.argv or []
        if argv[1:3] == ["pip", "install"] and "pre-commit>=4,<5" in argv:
            self.installs.append(command)
        return super().run(command, on_output, cancel)


def framework_wheel(root):
    # The wheel bridges to the real framework/dependencies installed for tests.
    # uv still executes the production pip install command and selects its target;
    # only downloading packages is replaced, so wrong-target installs are visible.
    version = importlib.metadata.version("pre-commit")
    directory = root / "wheels"
    directory.mkdir(exist_ok=True)
    info = f"pre_commit-{version}.dist-info"
    files = {
        "test-framework.pth": sysconfig.get_path("purelib") + "\n",
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: pre-commit\nVersion: {version}\n",
        f"{info}/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    files[f"{info}/RECORD"] = (
        "".join(f"{name},,\n" for name in files) + f"{info}/RECORD,,\n"
    )
    with zipfile.ZipFile(
        directory / f"pre_commit-{version}-py3-none-any.whl", "w"
    ) as wheel:
        for name, content in files.items():
            wheel.writestr(name, content)
    return directory


def service(root, **overrides):
    runner = OfflineBootstrap()
    env = {
        **os.environ,
        "PRE_COMMIT_HOME": str(root / "hook-cache"),
        "UV_OFFLINE": "1",
        "UV_NO_INDEX": "1",
        "UV_FIND_LINKS": str(framework_wheel(root)),
        **overrides,
    }
    return GitHooks(runner, env, uv=UV), runner


@pytest.mark.skipif(UV is None, reason="uv is required")
def test_real_runtime_creation_reuse_and_repair(root):
    config = root / ".pre-commit-config.yaml"
    config.write_text("repos: []\n", encoding="utf-8")
    hooks, runner = service(root)
    for _ in range(2):
        assert (
            hooks.run(root, config, ["validate-config"], lambda _: None).exit_code == 0
        )
    assert len(runner.installs) == 1
    python = venv_python(root / ".git/ptk/pre-commit")
    prefix = subprocess.check_output(
        [str(python), "-I", "-c", "import sys; print(sys.prefix)"], text=True
    ).strip()
    assert Path(prefix).samefile(root / ".git/ptk/pre-commit")
    assert not Path(prefix).samefile(sys.prefix)
    library = subprocess.check_output(
        [
            str(python),
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))",
        ],
        text=True,
    ).strip()
    (Path(library) / "test-framework.pth").unlink()
    assert hooks.run(root, config, ["validate-config"], lambda _: None).exit_code == 0
    assert len(runner.installs) == 2


@pytest.mark.skipif(UV is None, reason="uv is required")
@pytest.mark.parametrize(
    "selector", ["UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV", "UV_PYTHON"]
)
def test_hook_sync_cannot_uninstall_callers_packages(root, selector):
    outer = root.parent / "installed-ptk"
    subprocess.run(
        [UV, "venv", "--offline", "--python", sys.executable, str(outer)], check=True
    )
    python = str(venv_python(outer))
    wheel = root / "ptk_canary-1.0-py3-none-any.whl"
    files = {
        "ptk_canary.py": "value = 'PTK installation survives'\n",
        "ptk_canary-1.0.dist-info/METADATA": "Metadata-Version: 2.1\nName: ptk-canary\nVersion: 1.0\n",
        "ptk_canary-1.0.dist-info/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    files["ptk_canary-1.0.dist-info/RECORD"] = (
        "".join(f"{name},,\n" for name in files) + "ptk_canary-1.0.dist-info/RECORD,,\n"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    subprocess.run(
        [UV, "pip", "install", "--offline", "--python", python, str(wheel)], check=True
    )
    subprocess.run(
        [UV, "venv", "--offline", "--python", sys.executable, str(root / ".venv")],
        check=True,
    )
    requirements = root / "empty.txt"
    requirements.write_text("# no dependencies\n", encoding="utf-8")
    command = (
        [UV, "sync", "--offline"]
        if selector == "UV_PROJECT_ENVIRONMENT"
        else [
            UV,
            "pip",
            "sync",
            "--offline",
            "--allow-empty-requirements",
            str(requirements),
        ]
    )
    config = root / ".pre-commit-config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "repos": [
                    {
                        "repo": "local",
                        "hooks": [
                            {
                                "id": "sync",
                                "name": "sync",
                                "language": "system",
                                "entry": shlex.join(command),
                                "always_run": True,
                                "pass_filenames": False,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    hooks, _ = service(
        root, **{selector: python if selector == "UV_PYTHON" else str(outer)}
    )
    output = []
    result = hooks.run(root, config, ["run", "--all-files"], output.append)
    assert result.exit_code == 0, output
    result = subprocess.run(
        [python, "-I", "-c", "import ptk_canary; print(ptk_canary.value)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PTK installation survives" in result.stdout


def test_hook_environment_keeps_network_settings_without_caller_python_selectors(root):
    host = {name: "caller-runtime" for name in PYTHON_ENV_VARIABLES}
    host.update(
        {
            "UV_INDEX_URL": "https://packages.example.invalid/simple",
            "HTTPS_PROXY": "http://proxy.example.invalid",
            "UV_CACHE_DIR": str(root / "cache"),
            "GIT_DIR": "other-repo",
            "Path": os.pathsep.join(
                [str(venv_python(Path(sys.prefix)).parent), str(root / "tools")]
            ),
        }
    )
    snapshot = dict(host)
    hooks = GitHooks(SubprocessRunner(), host, uv=UV or "uv")
    assert not (PYTHON_ENV_VARIABLES & hooks._env.keys())
    assert "GIT_DIR" not in hooks._env
    for key in ["UV_INDEX_URL", "HTTPS_PROXY", "UV_CACHE_DIR"]:
        assert hooks._env[key] == host[key]
    assert hooks._env["Path"] == str(root / "tools")
    assert host == snapshot
