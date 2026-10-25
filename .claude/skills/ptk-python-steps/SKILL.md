---
name: ptk-python-steps
description: Choose and diagnose Python runtimes for ptk scripts and Python tools.
---

# ptk-python-steps

1. Read `src/ptk/adapters/python_env.py` and the PythonSpec schema.

2. Choose exactly one runtime: `uvx` for a tool, `venv` for requirement files/packages, `project` for a uv project, or `interpreter: cli` for ptk's environment.

3. Pin package versions where reproducibility matters. Use `with` only with `uvx`. Use `groups: [dev, docs]` only with `project` to select pyproject dependency groups.

4. Use `run: [script.py, arg]` for scripts and a tool command for uvx; do not feed a project script to a tool that does not run Python files.

5. Do not activate environments or mutate the parent process environment.

6. Use `ptk dry-run ACTION` to inspect runtime and command resolution before installation or execution.

7. Verify with the relevant action and inspect its debug log; test paths containing spaces on Windows and Linux.

8. Consult `tests/test_run.py` for cached venv behavior. Account for uv availability and downloads when selecting tests.
