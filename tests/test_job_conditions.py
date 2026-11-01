"""One portable job condition across runtime, inventory and workflow setup."""

import json

import pytest

from ptk.domain.errors import ConfigError
from tests.project_files import project_files, write_project
from tests.test_github_actions import configure_workflow
from tests.test_matrix_export import invoke
from tests.test_matrix_export import project as matrix_project


@pytest.fixture
def project(tmp_path):
    return matrix_project.__wrapped__(tmp_path)


@pytest.mark.parametrize(
    "symbol", ["os == 'linux'", "env.X", "params.enabled", "vars.channel"]
)
def test_runner_specific_job_conditions_rejected(write, load, symbol):
    root = write(
        project_files(f"""
project: {{name: demo}}
jobs:
  build:
    when: {symbol}
    steps:
      check: {{uses: echo}}
""")
    )
    with pytest.raises(ConfigError, match="step-only"):
        load(root)


@pytest.mark.parametrize(
    "field,value",
    [("only_cx", True), ("only_variants", ["debug"]), ("omit_variants", ["release"])],
)
def test_old_job_filters_rejected(project, field, value):
    root, model = project
    model["jobs"]["build"][field] = value
    write_project(root / ".main.ptk.yml", model)
    result = invoke(root, "validate")
    assert result.exit_code != 0 and f"unknown key '{field}'" in result.output


def test_disabled_job_skips_without_resolving_required_params_or_tools(project):
    root, model = project
    job = model["jobs"]["build"]
    job["when"] = "variant == 'release'"
    job["params"] = {"required_input": {"required": True}}
    write_project(root / ".main.ptk.yml", model)
    result = invoke(root, "-V", "debug", "run", "build")
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output.lower()
    assert "condition is false" in result.output


def test_workflow_matrix_prunes_disabled_producer_branch_but_keeps_independent_jobs(
    project,
):
    root, model = project
    configure_workflow(project)
    from tests.project_files import read_project

    model = read_project(root / ".main.ptk.yml")
    model["jobs"]["build"]["when"] = "variant == 'release'"
    model["workflows"]["verify"]["jobs"]["independent"] = {"job": "cx"}
    write_project(root / ".main.ptk.yml", model)
    result = invoke(root, "maintainer", "matrix", "--workflow", "verify", cx=True)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["jobs"]
    assert [r["variant"] for r in data["compile"]["include"]] == ["release"]
    assert [r["variant"] for r in data["check"]["include"]] == ["release"]
    assert len(data["independent"]["include"]) == 2
    result = invoke(
        root,
        "-V",
        "debug",
        "maintainer",
        "matrix",
        "--workflow",
        "verify",
        "--format",
        "github",
        cx=True,
    )
    assert result.exit_code == 0, result.output
    assert 'matrix_compile={"include":[]}' in result.output
    assert "has_jobs_compile=false" in result.output
    assert "has_jobs_independent=true" in result.output
