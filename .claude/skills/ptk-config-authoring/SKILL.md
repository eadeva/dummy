---
name: ptk-config-authoring
description: Create or change PTK configuration documents, component registrations and substitutions.
---

# PTK configuration authoring

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [configuration](../../../docs/guides/configuration.rst). Inspect the installed PTK with `ptk describe --json --configuration` for current values, source locations, file ownership and document schemas. `ptk maintainer config schema` describes the assembled model.
2. Preserve the existing root `.main.ptk.yml` and its chosen `config_path`; do not relocate it as part of an unrelated edit. It owns `repository: {alias: lowercase-name, config_path: relative/directory}`, `schema_version`, optional `ptk_version` and the discovery flag.
3. Use the conventional documents under `config_path`: `project.ptk.yml`, `folder_structure.ptk.yml`, `artifactory_paths.ptk.yml`, `credentials.ptk.yml`, `tools.ptk.yml`, `versioning.ptk.yml`, `configs.ptk.yml`, `project.variants.ptk.yml`, `maintainers.ptk.yml`, and individual files in `jobs/`, `workflows/`, `variants/`. All use `.ptk.yml`. Documents contain their section body, and filenames supply entity names. No includes or implicit file overlays are supported.
4. When the project needs components, register their actual relative directories as `components: {name: {path: relative/component}}` in `project.ptk.yml`. Keep `component.variants.ptk.yml` beside each component's CMakeLists.txt or Bazel module. It defines features, dependencies and constraints. Project variants select components and feature values; component constraints apply only when that component is selected.
5. Put project name, default job, variables, shared parameter/tool defaults, environment, logging_history_backups, report_formats, log_analysis and command audience in `project.ptk.yml`. Job-specific requirements and parameters go in that job's file. Explicit CLI `--set`, shared defaults and variant inheritance retain their model behavior.
6. Consult the runtime variable catalogue and each field's template capability before inserting references. Supported examples include `${vars.name}`, `${params.name}`, `${env:NAME:-fallback}` and `${vh.*}`; escape literal references with `$${...}`. `${date.timestamp}` is local invocation time and `${date.utc.timestamp}` is UTC. Registration and discovery paths are literal and repository-relative.
7. Verify with `ptk validate`, inspect origins with `ptk maintainer config show --sources`, then dry-run affected jobs and variants. Unknown fields and references are errors. Other repository files are not scanned.
8. For new projects, use `ptk init DIRECTORY --config-dir PATH`; preview with `--dry-run` when useful. Existing files are not overwritten. In VMR mode, omit DIRECTORY to initialize checked-out members without markers. A manual workspace marker contains `virtual_monorepo: true` and optional `members`; workspace workflows live in `workflows/<name>.ptk.yml` at the VMR root.

For a new configuration, consult the tested [authoring example](../../../examples/authoring/.main.ptk.yml).
See [versioning](../../../docs/guides/versioning.rst), [workflow authoring](../../../docs/guides/workflows.rst)
and [artifact destinations](../../../docs/guides/artifacts.rst) for their section contracts.
The [artifact example](../../../examples/artifacts/config/artifactory_paths.ptk.yml)
contains destination rules only. Native GitHub transfers use the shipped Actions
and workflow secret references; see [GitHub workflows](../ptk-github-workflows/SKILL.md).

Maintainers are plain login IDs in `maintainers.ptk.yml`: `maintainers: [alice, bob]`.
Match local OS usernames or triggering GitHub actors. `PTK_ROLE=maintainer` does not
grant access. PTK configuration-writing commands require a listed maintainer; command audience
can add restrictions but cannot relax these defaults. Validation stays available.
