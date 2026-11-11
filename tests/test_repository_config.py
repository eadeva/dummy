"""The repository's own PTk configuration must stay usable without release tags."""

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


def test_repository_jobs_and_component_free_default_variant():
    app = create_app()
    project = app.load_project.execute(config_file=ROOT / ".main.ptk.yml", cx=False)
    assert project.config.repository.alias == "ptk"
    assert set(project.config.jobs) == {"test", "docs", "check", "package", "extension"}
    assert project.config.project.default_job == "test"
    assert "default" in project.config.variants.variants
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


def test_repository_python_jobs_do_not_sync_the_cli_environment():
    app = create_app()
    project = app.load_project.execute(config_file=ROOT / ".main.ptk.yml", cx=False)
    environments = set()
    for name in ("test", "check", "docs", "package"):
        prepared = app.prepare_run(project).execute(
            project, RunRequest(job=name, dry_run=True)
        )
        command = app.run_job(project)._command(prepared, prepared.plan.steps[0], None)
        target = Path(command.env["UV_PROJECT_ENVIRONMENT"]).resolve()
        assert target == (ROOT / ".ptk" / "venvs" / name).resolve()
        assert target not in environments
        environments.add(target)


@pytest.mark.parametrize("run", [["python", "-m", "sphinx"], ["build_docs.py"]])
def test_project_dependency_groups_reach_uv_before_the_command(tmp_path, run):
    project = tmp_path / "project with spaces"
    project.mkdir()
    manager = UvPythonEnvManager(None, uv="/tools/uv")
    spec = PythonSpec(project="project with spaces", groups=["dev", "docs"])
    runtime = manager.runtime(spec, tmp_path, create=False)
    step = PlannedStep(path=("docs",), spec=StepSpec(run=run, python=spec), run=run)
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


def test_python_version_index_and_downloads_reach_every_uv_mode(tmp_path):
    from ptk.domain.config.model import PythonDefaults, VenvSpec

    manager = UvPythonEnvManager(None, uv="uv")
    defaults = PythonDefaults(
        version="3.12", index=["tcc=https://example.invalid/simple/"], downloads="never"
    )
    expected_env = {
        "UV_INDEX": "tcc=https://example.invalid/simple/",
        "UV_PYTHON_DOWNLOADS": "never",
    }
    plain = manager.runtime(None, tmp_path, create=False, defaults=defaults)
    assert plain.script_prefix == ["uv", "run", "--no-project", "--python", "3.12"]
    assert plain.env == expected_env and "Python 3.12" in plain.description
    tool = manager.runtime(
        PythonSpec(uvx="ruff", version="3.11"),
        tmp_path,
        create=False,
        defaults=defaults,
    )
    assert tool.command_prefix[:5] == ["uv", "tool", "run", "--python", "3.11"]
    project = manager.runtime(
        PythonSpec(project="."), tmp_path, create=False, defaults=defaults
    )
    assert project.command_prefix[4:6] == ["--python", "3.12"]
    venv = manager.runtime(
        PythonSpec(venv=VenvSpec()), tmp_path, create=False, defaults=defaults
    )
    assert venv.env["UV_INDEX"] and "Python 3.12" in venv.description
    other = manager.runtime(
        PythonSpec(venv=VenvSpec(), version="3.11"), tmp_path, create=False
    )
    assert other.script_prefix != venv.script_prefix  # version is part of the hash
    cli = manager.runtime(
        PythonSpec(interpreter="cli"), tmp_path, create=False, defaults=defaults
    )
    assert cli.env == {} and "--python" not in cli.script_prefix
    step = PlannedStep(path=("s",), spec=StepSpec(run=["x.py"]), run=["x.py"])
    command = build_command(
        step,
        env={},
        cwd=str(tmp_path),
        os_name="linux",
        python=None,
        plain_python=plain,
    )
    assert command.argv[:5] == ["uv", "run", "--no-project", "--python", "3.12"]
    assert command.env["UV_PYTHON_DOWNLOADS"] == "never"


def test_python_version_and_index_are_validated():
    from ptk.domain.config.model import PythonDefaults

    for version in ("3", "3.12", "3.12.4", ">=3.11,<3.13", "~=3.12"):
        assert PythonSpec(uvx="ruff", version=version).version == version
    for version in ("3.1.2.3", "python3", "latest", "3.12,"):
        with pytest.raises(ValidationError, match="invalid Python version"):
            PythonSpec(uvx="ruff", version=version)
    with pytest.raises(ValidationError, match="interpreter: cli"):
        PythonSpec(interpreter="cli", version="3.12")
    with pytest.raises(ValidationError, match="invalid package index"):
        PythonDefaults(index=["no url"])
    with pytest.raises(ValidationError, match="Extra inputs"):
        PythonSpec.model_validate({"venv": {"python": "3.12"}})


@pytest.mark.parametrize("cx", [False, True], ids=["local", "cx"])
@pytest.mark.parametrize(
    "entry",
    [ROOT / ".main.ptk.yml", *sorted((ROOT / "examples").rglob(".main.ptk.yml"))],
    ids=lambda entry: entry.relative_to(ROOT).as_posix(),
)
def test_checked_in_configuration_uses_discovered_schema_fragments(entry, cx):
    import yaml

    metadata = yaml.safe_load(entry.read_text())
    if metadata.get("virtual_monorepo") is True:
        from ptk.adapters.config.yaml_loader import YamlConfigReader

        YamlConfigReader().read(entry)
        return
    project = create_app().load_project.execute(config_file=entry, cx=cx)
    assert project.config.repository.alias == metadata["repository"]["alias"]
    assert entry in project.files
    assert all(file.name.endswith((".ptk.yml", ".ptk.yaml")) for file in project.files)
