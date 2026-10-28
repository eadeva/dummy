---
name: ptk-config-authoring
description: Create or change ptk YAML configuration, discovered fragments and substitutions.
---

# ptk-config-authoring

1. Read [docs/configuration.rst](../../../docs/configuration.rst); export `ptk setup config schema -o schema.json` when exact field names are needed.

2. Use `.main.ptk.yml` as the entry point and `*.ptk.yml` fragments. Keep `local.ptk.yml` untracked.

3. Let PTK discover *.ptk.yml and *.ptk.yaml recursively inside the repository. Write every fragment at its full schema path. Never use include directives or merge tags. Maps contribute disjoint fields; duplicate scalar/list definitions are errors. Keep each field in one file, including local and active CI fragments. CLI --set remains an explicit runtime override.

4. Remember that mappings merge deeply and lists replace; use `!append` or `!replace` intentionally.

5. Use `${vars.name}`, `${params.name}`, `${env:NAME:-fallback}` and `${vh.*}`; escape literal references with `$${...}`. `${date.timestamp}` gives local invocation time as `YYYY_MM_DD_HHMM`; `${date.utc.timestamp}` uses UTC. Date components can be combined for custom formats. The instant is shared across steps, variants and local workflow children; discovery fields remain literal.

6. Inspect origins with `ptk setup config show --sources` before changing an unexpected effective value.

7. Export `ptk setup config schema -o schema.json` for editor support. Treat loader directives separately from model fields.

8. Verify with `ptk setup config validate`, then `ptk dry-run JOB` for every affected variant.

9. Avoid unknown keys, unresolved references, duplicate file definitions and unsupported `plugins` expectations.

10. For a new project, obtain the user's config-folder choice, preview `ptk setup init DIRECTORY --config-dir PATH --dry-run`, then run without `--dry-run`. The path is required and relative to the repository root; there is no default. On a terminal, omit the option to prompt. In VMR mode, omit DIRECTORY to initialize all checked-out members lacking `.main.ptk.yml`; configured repositories are skipped. Apply the one folder choice relative to each new member's root. Aliases are made unique, and existing .gitignore content is preserved with missing rules appended. Preflight conflicts in new members stop the batch before writes. Validate new configs and run their hello/build jobs, using repository aliases in a VMR. Retain separate job files and commented examples under the starter's topic folders.

11. Use `param_defaults` for shared defaults on explicitly declared parameters; job defaults win. Use `cx.ptk.yml` for workflows and preserve per-tool requirement inheritance.

A project's root `.main.ptk.yml` requires `repository: {alias: lowercase-name, config_path: relative/directory}`. Use config_path as the default authoring folder and location of the independent maintainer list; configuration discovery spans the repository. Commands use the repository root. In VMR workspaces, invoke `ptk <repository-alias> <command>`. A separate manual workspace marker contains only `virtual_monorepo: true` and optional `members: [nested/repo, other]`; without a list, only direct child directories are checked. It needs no repository metadata. Omit the flag on project entries for automatic detection; explicit `false` keeps a project standalone and excludes it from VMR listings. Keep discovery fields literal and entry-only, never in fragments or CLI overrides. See the `ptk-vmr` skill for Git-pointer membership and bounded discovery.

Start from [examples/authoring/.main.ptk.yml](../../../examples/authoring/.main.ptk.yml) and its fragments for a complete tested configuration. Read [docs/configuration.rst](../../../docs/configuration.rst) for default environment isolation and explicit inheritance.

For version discovery, read [docs/versioning.rst](../../../docs/versioning.rst). Keep `.main.ptk.yml` minimal; use `ptk setup init --config-dir PATH` for starter fragments. Maintain `versioning.ptk.yml`, never commit `.gen.version.ptk.yml`. Use `PTK_VERSION_ALIAS_COMPONENT_NAME` and `${version.projects.alias.value}`; generators consume the run snapshot. Declare VMR version dependencies and their variants explicitly. Do not add bump/tag operations.


To combine existing jobs locally, use [workflow configuration](../../../docs/workflows.rst) and the `ptk-workflow-authoring` skill. Put `workflow.ptk.yml` in the configured folder; workspace-owned workflows belong at the VMR root. Workflows preserve each call's repository settings and never run wholesale on CX. GitHub job/template generation is deferred.

For upload destinations, read [Artifactory destination rules](../../../docs/artifacts.rst) and start from [the destination example](../../../examples/artifacts/config/artifactory_structure.ptk.yaml). The exact filename `artifactory_structure.ptk.yaml` is discovered in the config folder. Configure global base, event route and optional PTK-job suffix; preserve branch slashes. PTK resolves paths only; workflows select files, authenticate and upload. Preview with `ptk artifacts destination --job NAME --event release`; use `--at ISO_TIMESTAMP` for a shared explicit date and `--format github` for step outputs. Never add file-selection or credential fields to this model.

Maintainers are plain login IDs in `maintainers.ptk.yml`: `maintainers: [alice, bob]`.
Match OS usernames locally and triggering GitHub actors on Actions; do not use
Git emails or `PTK_ROLE=maintainer`. Use `ptk setup doctor` to inspect the detected
ID. Init seeds the creator. Configuration writers (shared-config sync, self setup,
editor setup and variant editing) require a listed maintainer and are hidden from
normal users. `command_audience` can add restrictions but cannot relax these defaults.
Keep machine-wide tool installation and personal credential setup available.
