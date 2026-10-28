from tests.project_files import write_workflows

"""Job/workflow startup boundaries and failures before executing user steps."""

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.hooks import GitHooks
from ptk.application.use_cases.hooks import EnsureHooks
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli

from .conftest import git, invoke, repository
from .test_installation import hook_path


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["build", "--help"],
        ["dry-run", "build"],
        ["workflow", "dry-run", "verify"],
        ["build"],
    ],
)
def test_help_preview_and_ci_do_not_install(tmp_path, monkeypatch, args):
    root = repository(tmp_path / "app")
    write_workflows(
        (root / "config/workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump(
                {
                    "workflows": {
                        "verify": {
                            "steps": [{"first": {"job": "build"}}],
                        }
                    }
                }
            )
        )["workflows"],
    )

    def forbidden(*args, **kwargs):
        pytest.fail("hook inspection/installation must not run")

    monkeypatch.setattr(GitHooks, "ensure", forbidden)
    if args == ["build"]:
        result = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
            cli, ["-C", str(root / ".main.ptk.yml"), *args]
        )
    else:
        result = invoke(root, *args)
    assert result.exit_code == 0, result.output
    assert not hook_path(root).exists()


def test_disabled_entry_does_not_require_config_or_git(tmp_path, offline_engine):
    root = repository(tmp_path / "app", enabled=False)
    (root / ".pre-commit-config.yaml").unlink()
    assert invoke(root, "build").exit_code == 0
    assert not offline_engine


@pytest.mark.parametrize(
    "failure", ["missing", "invalid", "installation", "verification"]
)
def test_hook_failures_block_job(tmp_path, monkeypatch, failure):
    root = repository(tmp_path / "app")
    if failure == "missing":
        (root / ".pre-commit-config.yaml").unlink()
    elif failure == "invalid":
        (root / ".pre-commit-config.yaml").write_text(
            "repos: []\ndefault_install_hook_types: ['../../outside']\n"
        )
    elif failure == "installation":

        def fail(*args):
            raise PtkError("package installation failed")

        monkeypatch.setattr(GitHooks, "_runtime", fail)
    else:
        original = GitHooks._checked

        def no_install(self, root, argv, **kwargs):
            return "" if "install" in argv else original(self, root, argv, **kwargs)

        monkeypatch.setattr(GitHooks, "_checked", no_install)
    result = invoke(root, "build")
    assert result.exit_code == 2, result.output
    assert not (root / "job-ran").exists()


@pytest.mark.parametrize("fails", [False, True])
def test_vmr_workflow_checks_each_participant_before_any_job(
    tmp_path, monkeypatch, fails
):
    workspace = tmp_path / "vmr"
    a = repository(workspace / "a", alias="a")
    b = repository(workspace / "b", alias="b")
    unused = repository(workspace / "unused", alias="unused")
    (unused / ".pre-commit-config.yaml").unlink()
    (workspace / ".main.ptk.yml").write_text("virtual_monorepo: true\n")
    write_workflows(
        (workspace / "workflow.ptk.yml").parent / "workflows",
        yaml.safe_load(
            yaml.safe_dump(
                {
                    "workflows": {
                        "verify": {
                            "open_report": None,
                            "steps": [
                                {
                                    "parallel": {
                                        "parallel": True,
                                        "steps": [
                                            {"one": {"repo": "a", "job": "build"}},
                                            {"two": {"repo": "b", "job": "build"}},
                                        ],
                                    }
                                },
                                {"again": {"repo": "a", "job": "build"}},
                            ],
                        }
                    }
                }
            )
        )["workflows"],
    )
    seen = []
    original = EnsureHooks.execute

    def check(self, project, out):
        assert not (a / "job-ran").exists() and not (b / "job-ran").exists()
        seen.append(project.root.name)
        if fails and project.root == b:
            raise PtkError("cannot install b hooks")
        original(self, project, out)

    monkeypatch.setattr(EnsureHooks, "execute", check)
    monkeypatch.chdir(workspace)
    result = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"}).invoke(
        cli, ["verify"], catch_exceptions=False
    )
    assert result.exit_code == (2 if fails else 0), result.output
    assert seen == ["a", "b"]
    assert (a / "job-ran").exists() is not fails
    assert (b / "job-ran").exists() is not fails
    assert not hook_path(unused).exists()


def test_doctor_reports_pointer_repo_without_installing(tmp_path, offline_engine):
    root = repository(tmp_path / "app")
    git(root, "init", "--separate-git-dir", str(tmp_path / "metadata"))
    result = invoke(root, "setup", "doctor")
    assert "missing or unusable" in result.output
    assert not offline_engine
    assert invoke(root, "build").exit_code == 0
    result = invoke(root, "setup", "doctor")
    assert "installed (pre-commit)" in result.output


def test_vmr_member_job_does_not_inspect_unrelated_repositories(tmp_path, monkeypatch):
    root = tmp_path / "vmr"
    a = repository(root / "a", alias="a")
    b = repository(root / "b", alias="b")
    (b / ".pre-commit-config.yaml").unlink()
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\n")
    monkeypatch.chdir(root)
    result = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"}).invoke(
        cli, ["a", "build"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert hook_path(a).exists() and not hook_path(b).exists()
