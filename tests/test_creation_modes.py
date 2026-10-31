"""Authoring templates must stay ordinary, valid executable configuration."""

import pytest

from ptk.adapters.python_env import UvPythonEnvManager
from ptk.application.use_cases.project import ExportSchema
from ptk.domain.config.model import JobSpec, PythonSpec, StepSpec
from ptk.domain.config.step_modes import creation_modes
from ptk.domain.execution.commands import build_command
from ptk.domain.execution.model import PlannedStep


@pytest.mark.parametrize("mode", creation_modes(), ids=lambda mode: mode["id"])
def test_step_modes_resolve_through_the_actual_execution_engine(mode, tmp_path):
    spec = StepSpec.model_validate(mode["initial"])
    if spec.run is None:
        assert spec.uses == "echo" or spec.generators == ["cmake"]
        return
    manager = UvPythonEnvManager(None, uv="uv")
    runtime = (
        manager.runtime(spec.python, tmp_path, create=False) if spec.python else None
    )
    step = PlannedStep(path=("check",), spec=spec, run=spec.run)
    command = build_command(
        step,
        env={},
        cwd=str(tmp_path),
        os_name="linux",
        python=runtime,
        powershell="pwsh",
    )
    if mode["id"] == "shell":
        assert command.shell == "echo Hello" and command.argv is None
        return
    assert command.shell is None
    expected = {
        "command": ["tool", "--help"],
        "bash-script": ["bash", "tools/script.sh"],
        "powershell-script": [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools/script.ps1",
        ],
        "batch-script": ["cmd", "/c", "tools/script.cmd"],
        "python-script": ["uv", "run", "--no-project", "tools/script.py"],
        "python-tool": [
            "uv",
            "tool",
            "run",
            "--from",
            "your-package==1.0.0",
            "your-command",
        ],
    }
    if mode["id"] in expected:
        assert command.argv == expected[mode["id"]]
    elif spec.python and spec.python.project is not None:
        assert command.argv[:4] == [
            "uv",
            "run",
            "--project",
            str((tmp_path / spec.python.project).resolve()),
        ]
    elif not spec.python:
        assert command.argv == spec.run
    else:
        assert command.argv[-1] == spec.run[-1]
    assert not (tmp_path / ".ptk").exists()


def test_schema_modes_have_help_and_valid_job_and_python_templates():
    schema = ExportSchema().execute()
    for name, model in [
        ("StepSpec", StepSpec),
        ("JobSpec", JobSpec),
        ("PythonSpec", PythonSpec),
    ]:
        modes = schema["$defs"][name]["x-ptk-creation-modes"]
        assert len({mode["id"] for mode in modes}) == len(modes)
        for mode in modes:
            assert all(
                mode.get(key)
                for key in (
                    "group",
                    "label",
                    "description",
                    "requirements",
                    "constraints",
                )
            )
            model.model_validate(mode["initial"])
            assert "mode" not in mode["initial"]
    schema["$defs"]["StepSpec"]["x-ptk-creation-modes"][0]["initial"]["run"].append(
        "mutated"
    )
    assert ExportSchema().execute()["$defs"]["StepSpec"]["x-ptk-creation-modes"][0][
        "initial"
    ]["run"] == ["tool", "--help"]
