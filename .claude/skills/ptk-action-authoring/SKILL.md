---
name: ptk-action-authoring
description: Add or modify ptk actions, parameters, nested steps, conditions and maintainer
  visibility.
---

# ptk-action-authoring

1. Read `docs/configuration.rst` and `src/ptk/domain/config/model.py`.

2. Use ordered, uniquely named steps with exactly one of `run`, `uses`, or `steps`.

3. Use argument lists for commands with parameters or paths containing spaces.

4. Declare typed parameters; keep CLI > parameter file > declared env > default precedence.

5. Do not combine `required: true` with a default or make a default reference other parameters.

6. Apply `parallel` only to sets; `python` and `passthrough` only to run steps; `with` only to built-ins.

7. Check registered `uses` names in `src/ptk/bootstrap.py` and `src/ptk/application/use_cases/run.py`; including echo, wait, report.import, configs.sync, tools.ensure, files.copy, files.clean and variant.generate.

8. Preview `ptk dry-run ACTION -V VARIANT`; check `ptk ACTION --help` and top-level `--from/--to` boundaries.

9. After changes, run the affected action in a disposable example and inspect logs and reports.

10. Regenerate `ptk setup vscode tasks --users-only` if committing tasks; verify maintainer-only actions stay hidden for users.

11. Background processes are finite and joined at their containing group boundary. Group retries repeat all children; Python handlers must cooperate with deadlines. Use `files.clean` only within generated workspace folders.
