"""The repository's own PTK configuration must stay usable without release tags."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ptk.adapters.python_env import UvPythonEnvManager
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import PythonSpec, StepSpec
from ptk.domain.execution.commands import build_command
from ptk.domain.execution.model import PlannedStep

ROOT = Path(__file__).resolve().parents[1]


def test_repository_jobs_and_single_component_free_variant():
    app = create_app()
    project = app.load_project.execute(config_file=ROOT / ".main.ptk.yml", ci=False)
    assert project.config.repository.alias == "ptk"
    assert set(project.config.jobs) == {"test", "docs", "check", "package"}
    assert project.config.project.default_job == "test"
    assert list(project.config.variants.variants) == ["default"]
    assert not project.config.variants.components
    assert not project.config.versioning.components
    for job in project.config.jobs:
        prepared = app.prepare_run(project).execute(
            project, RunRequest(job=job, dry_run=True)
        )
        assert prepared.plan.variant == "default"
        assert "PTK_VERSION_PTK" in prepared.plan.base_env
        assert not prepared.versions["projects"]["ptk"]["components"]
        assert not any("_COMPONENT_" in key for key in prepared.plan.base_env)


@pytest.mark.parametrize("run", [["python", "-m", "sphinx"], ["build_docs.py"]])
def test_project_dependency_groups_reach_uv_before_the_command(tmp_path, run):
    project = tmp_path / "project with spaces"
    project.mkdir()
    manager = UvPythonEnvManager(None, uv="/tools/uv")
    spec = PythonSpec(project="project with spaces", groups=["dev", "docs"])
    runtime = manager.runtime(spec, tmp_path, create=False)
    step = PlannedStep(
        path=("docs",), spec=StepSpec(name="docs", run=run, python=spec), run=run
    )
    command = build_command(
        step, env={}, cwd=str(tmp_path), os_name="linux", python=runtime
    )
    assert command.argv[:3] == ["/tools/uv", "run", "--project"]
    # Windows may canonicalize directory-name casing during resolve().
    assert Path(command.argv[3]).samefile(project)
    assert command.argv[4:8] == ["--group", "dev", "--group", "docs"]
    assert command.argv[8:] == (["python", *run] if run[0].endswith(".py") else run)


def test_python_groups_are_only_allowed_for_project_mode():
    assert PythonSpec(project=".", groups="docs").groups == ["docs"]
    for data in (
        {"uvx": "ruff", "groups": ["docs"]},
        {"interpreter": "cli", "groups": ["docs"]},
    ):
        with pytest.raises(ValidationError, match="only allowed together with project"):
            PythonSpec.model_validate(data)
    with pytest.raises(ValidationError, match="invalid dependency group"):
        PythonSpec(project=".", groups=["--no-project"])
