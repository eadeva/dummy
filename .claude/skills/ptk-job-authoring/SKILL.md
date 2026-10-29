---
name: ptk-job-authoring
description: Add, change or explain PTK jobs, typed parameters, nested steps, conditions, runtime variables and maintainer visibility in an existing or new project.
---

# ptk-job-authoring

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [configuration](../../../docs/guides/configuration.rst), the owning job document and referenced tools/parameters. Use the installed document schema for exact fields. Preserve existing job names, scripts, selected runtimes and output conventions unless the requested change requires otherwise.

2. Use ordered, uniquely named steps with exactly one of `run`, `uses`, or `steps`.

3. Use argument lists for commands with parameters or paths containing spaces.

4. Declare typed parameters; keep CLI > parameter file > declared env > default precedence.

5. Do not combine `required: true` with a default or make a default reference other parameters.

6. Apply `parallel` only to sets; `python` and `passthrough` only to run steps; `with` only to built-ins.

7. Read the built-in contracts in [docs/reference/plugins.rst](../../../docs/reference/plugins.rst); for available built-ins and selected plugins. Do not invent a `uses` name from a tool binary name.

8. Use the discovered execution/help paths, including any maintainer prefix. Preview the affected job; add `-V VARIANT` only for an actual variant. Check parameter choices/help and top-level `--from/--to` boundaries.

9. Validate the edit and preview the affected path. Run a focused check only within the authorized scope, using disposable inputs where possible; inspect its actual output paths and exit status.

10. If the requested change affects maintained VS Code tasks, update them with `ptk maintainer sync tasks`, preserving the project's user/maintainer task policy; use `--users-only` when explicitly wanted.

11. Background processes are finite and joined at their containing group boundary. Group retries repeat all children; Python handlers must cooperate with deadlines. Use `files.clean` only within generated workspace folders.

Read [versioning](../ptk-versioning/SKILL.md) only for version sources or generated version files, and [workflow authoring](../ptk-workflow-authoring/SKILL.md) to compose existing jobs.

Use `audience: maintainer` for configuration-writing or release jobs. Maintainer
IDs are plain login strings in `maintainers.ptk.yml`, never Git-email records.
Editor task generation now requires a maintainer; use `--users-only` for shared
tasks and verify user visibility with `PTK_ROLE=user`. Role elevation via the
environment is not supported.
