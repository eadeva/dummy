---
name: ptk-python-steps
description: Choose and diagnose Python runtimes for ptk scripts and Python tools.
---

# ptk-python-steps

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [docs/guides/configuration.rst](../../../docs/guides/configuration.rst) and the PythonSpec definition from `ptk maintainer config schema`.

2. Choose exactly one runtime: `uvx` for a tool, `venv` for requirement files/packages, `project` for a uv project, or `interpreter: cli` for ptk's environment.

3. Pin package versions where reproducibility matters. Use `with` only with `uvx`. Use `groups` only with `project`, selecting dependency groups that actually exist in that project.

4. Use `run: [script.py, arg]` for scripts and a tool command for uvx; do not feed a project script to a tool that does not run Python files.

5. Do not activate environments or mutate the parent process environment.

6. Use `ptk JOB --dry-run` to inspect runtime and command resolution before installation or execution.

7. When execution is authorized, verify the relevant job and its recorded interpreter/debug log. Test space-containing paths on the supported platforms; report platforms not exercised.

8. Inspect debug logs to verify which cached environment is selected. Account for uv availability and downloads when choosing a runtime.
