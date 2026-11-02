---
name: ptk-job-authoring
description: Add, change or explain PTK jobs, typed parameters, step dependency graphs, GUI launchers, declared outputs, optional caching, conditions and maintainer visibility in an existing or new project.
---

# ptk-job-authoring

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [configuration](../../../docs/guides/configuration.rst), the owning job document and referenced tools/parameters. Use the installed document schema for exact fields. Preserve existing job names, scripts, selected runtimes and output conventions unless the requested change requires otherwise.

2. Use a `steps` mapping of unique IDs, each with `run`, `uses`, or a nonempty generation-only `generators` list. `run` and `uses` are mutually exclusive; generators may accompany either. Add `needs: ID` or `needs: [ID, ID]` for prerequisites. Independent steps may overlap; declaration order does not serialize them.

3. Use argument lists for commands with parameters or paths containing spaces.

4. Recommend the extension’s **Set up new parameter** / **Edit parameter…** form for parameter definitions: select a type, description, allowed choices, required setting, environment source and optional literal/template default, then review before saving. Changing type resets its draft default/choices; Cancel preserves the source. Keep secrets out of defaults. To discover job options in a configured shell, type `ptk JOB --` then Tab; bare whitespace does not list options. Use `ptk JOB --help` for descriptions and `ptk self-service completion install` if registration is missing. Declare typed parameters; keep CLI > parameter file > declared env > default precedence.

5. Do not combine `required: true` with a default or make a default reference other parameters.

6. Set job `max_workers` to bound concurrency. Use `python` and `passthrough` only on run steps and `with` only on handlers. Do not author lists, shorthand bodies, nested groups, `parallel` or `background`.

7. Read the built-in contracts in [docs/reference/builtins.rst](../../../docs/reference/builtins.rst) for available built-ins. Do not invent a `uses` name from a tool binary name.

8. Use the discovered execution/help paths, including any maintainer prefix. Preview the affected job; add `-V VARIANT` only for an actual variant. Check parameter choices/help and `--to` prerequisite closure and explicit `--only-step` omission notices.

9. Validate the edit and preview the affected path. Run a focused check only within the authorized scope, using disposable inputs where possible; inspect its actual output paths and exit status.

10. If the requested change affects maintained VS Code tasks, update them with `ptk maintainer sync tasks`, preserving the project's user/maintainer task policy; use `--users-only` when explicitly wanted.

11. Inspect with `--graph`; dry-runs include graphs automatically. Keep repository-root default cwd. Step folders are conventions, not enforced sandboxes: declare dependencies for shared writes and use `${steps.ID.build_dir}` for known paths. `--only-step` requires existing prerequisite artifacts; never assume stored runtime outputs. Retries affect one step; built-in handlers observe cancellation, and external processes follow the documented timeout behavior. Use `files.clean` only within generated workspace folders.

Declare `outputs` explicitly as paths or `{path, artifact_type}` objects on the producing step/job. Their principal purpose is workflow artifact transfer; output validity is project responsibility. Opt into reuse only with declared outputs and `cache: true`; content hashes, not timestamps, decide reuse. Root steps/calls still execute, and `--no-cache-ptk` disables reuse throughout execution. Read [output reuse](../../../docs/guides/output-reuse.rst) and [artifact manifests](../../../docs/guides/artifacts.rst).

For GUI launchers, inspect the installed job `gui` field and its constraints in [execution](../../../docs/reference/execution.rst). The launched process outlives PTK; successful launch is not proof the application completed. Do not treat detached GUI jobs as completed artifact producers. Use the editor's creation wizard and runtime mode descriptions for Python, direct-command and shell choices; do not embed shell syntax in argv lists.

Before real execution, account for required-tool/credential checks and enabled local hook installation. Python environments are prepared when their steps start. Configuration freshness is a separate explicit check, not an automatic job prerequisite. Read [local setup](../../../docs/guides/local-setup.rst) when startup fails.

Read [versioning](../ptk-versioning/SKILL.md) only for version sources or generated version files, and [workflow authoring](../ptk-workflow-authoring/SKILL.md) to compose existing jobs.

Use `audience: maintainer` for configuration-writing or release jobs. Maintainer
IDs are plain login strings in `maintainers.ptk.yml`, never Git-email records.
Editor task generation now requires a maintainer; use `--users-only` for shared
tasks and verify user visibility with `PTK_ROLE=user`. Role elevation via the
environment is not supported.

Use `when` for job and step eligibility; never author `only_cx`, `only_variants`
or `omit_variants`. Job conditions accept only CX and resolved variant context
(`cx`, `variant`, component/feature symbols and `vh`); use `os`, `env`, `params`
and `vars` only on steps. Combine migrated filters with `and`. Check enabled and
disabled variants. False job conditions skip execution and block dependent branches.

Treat every declared output as required. Verify the producer actually creates it;
missing outputs fail before consumers and cannot be tolerated by `continue_on_error`.
Partial runs validate executed step outputs only; detached GUI launchers cannot
promise outputs. Existing files satisfy existence checks, so keep semantic freshness
and cache correctness project-owned. Never publish an `outputs_valid: false` manifest.

For generated workflows, preserve setup's per-invocation `has_jobs_*` outputs and
job guards for empty matrices. Matrix export prunes false rows and dependent rows,
including mapped repository variants. Review existing project-owned workflows
explicitly; generation never overwrites them. Do not claim hosted execution from
local validation alone. Read the linked execution and GitHub workflow docs for details.
