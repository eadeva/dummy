---
name: ptk-config-authoring
description: Create or change ptk YAML configuration, includes, layers and substitutions.
---

# ptk-config-authoring

1. Read `docs/configuration.rst` and the models in `src/ptk/domain/config/model.py`.

2. Use `.main.ptk.yml` as the entry point and `*.ptk.yml` fragments. Keep `local.ptk.yml` untracked.

3. Preserve merge order: automatic tool/versioning files, main/includes, CX overlay, local overlay, CLI overrides. Entry includes use repository.config_path; fragment includes use the fragment directory.

4. Remember that mappings merge deeply and lists replace; use `!append` or `!replace` intentionally.

5. Use `${vars.name}`, `${params.name}`, `${env:NAME:-fallback}` and `${vh.*}`; escape literal references with `$${...}`.

6. Inspect origins with `ptk setup config show --sources` before changing an unexpected effective value.

7. Export `ptk setup config schema -o schema.json` for editor support. Treat loader directives separately from model fields.

8. Verify with `ptk setup config validate`, then `ptk dry-run ACTION` for every affected variant.

9. Avoid unknown keys, unresolved references, recursive includes and unsupported `plugins` expectations.

10. For a new project, obtain the user's config-folder choice, preview `ptk setup init DIRECTORY --config-dir PATH --dry-run`, then run without `--dry-run`. The path is required and relative to the repository root; there is no default. On a terminal, omit the option to prompt. In VMR mode, omit DIRECTORY to initialize all checked-out members lacking `.main.ptk.yml`; configured repositories are skipped. Apply the one folder choice relative to each new member's root. Aliases are made unique, and existing .gitignore content is preserved with missing rules appended. Preflight conflicts in new members stop the batch before writes. Validate new configs and run their hello/build actions, using repository aliases in a VMR. Retain separate action files and commented examples under the starter's topic folders.

11. Use `param_defaults` for shared defaults on explicitly declared parameters; action defaults win. Use `cx.ptk.yml` for workflows and preserve per-tool requirement inheritance.

A project's root `.main.ptk.yml` requires `repository: {alias: lowercase-name, config_path: relative/directory}`. Entry includes and automatic tool/CX/local/maintainer files use that directory; fragment includes stay fragment-relative and commands use the repository root. In VMR workspaces, invoke `ptk <repository-alias> <command>`. A separate manual workspace marker contains only `virtual_monorepo: true` and optional `members: [nested/repo, other]`; without a list, only direct child directories are checked. It needs no repository metadata. Omit the flag on project entries for automatic detection; explicit `false` keeps a project standalone and excludes it from VMR listings. Keep discovery fields literal and entry-only, never in includes, overlays or CLI overrides. See the `ptk-vmr` skill for Git-pointer membership and bounded discovery.

Start from `examples/authoring/.main.ptk.yml` and its fragments for a complete tested configuration. Read `docs/configuration.rst` for default environment isolation and explicit inheritance.

For version discovery, read `docs/versioning.rst` and exercise `tests/test_versioning.py`. Keep `.main.ptk.yml` minimal; use `ptk setup init --config-dir PATH` for starter fragments. Maintain `versioning.ptk.yml`, never commit `.gen.version.ptk.yml`. Use `PTK_VERSION_ALIAS_COMPONENT_NAME` and `${version.projects.alias.value}`; generators consume the run snapshot. Declare VMR version dependencies and their variants explicitly. Do not add bump/tag operations.
