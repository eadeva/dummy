---
name: ptk-python-steps
description: Choose and diagnose PTK Python execution modes, standalone scripts, editable local projects, requirements environments and packaged tools.
---

# ptk-python-steps

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [configuration](../../../docs/guides/configuration.rst), [reusable Python tools](../../../docs/guides/python-tools.rst), and the PythonSpec definition from `ptk maintainer config schema`. Packages expose ordinary commands through `project.scripts`; PTK does not load third-party callbacks or promise a public internal Python API.

2. A step may omit `python`: a leading `.py` script uses `uv run --no-project` (including PEP 723), while explicit `[python, script.py]` uses ordinary PATH lookup. Otherwise choose exactly one runtime: `uvx` for a tool, `venv` for requirement files/packages, `project` for a uv project, or `interpreter: cli` for ptk's environment.

3. Pin package versions where reproducibility matters. Use `with` only with `uvx`. Use `groups` only with `project`, selecting dependency groups that actually exist in that project.

4. Use `run: [script.py, arg]` for scripts and a tool command for uvx; do not feed a project script to a tool that does not run Python files.

5. For editable local packages, use `python: {project: .}` or the actual project directory. uv synchronizes that project normally; editable installation depends on its packaging configuration. Keep development groups explicit and do not replace this with ad hoc `pip install -e` in PTK’s environment. Project/requirements paths resolve from the repository root; script paths resolve from step `cwd`, whose default is the repository root.

6. Do not activate environments or mutate the parent process environment. Python-mode commands are argv, not shells: use an explicit shell command for pipes/redirection. See [execution forms](../../../docs/reference/execution.rst).

7. Use `ptk JOB --dry-run` to inspect runtime and command resolution before installation or execution.

8. When execution is authorized, verify the relevant job and its recorded interpreter/debug log. Test space-containing paths on the supported platforms; report platforms not exercised.

9. Inspect debug logs to verify which cached environment is selected. Account for uv availability and downloads when choosing a runtime.
