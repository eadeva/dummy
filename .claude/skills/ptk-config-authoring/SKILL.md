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

10. For a new project, preview `ptk setup init DIRECTORY --dry-run`, then run `ptk setup init DIRECTORY`. Existing configuration is refused and existing .gitignore content is preserved with missing ignore rules appended. Run `ptk setup config validate` and `ptk hello` in the new directory.

11. Use `param_defaults` for shared defaults on explicitly declared parameters; action defaults win. Use `cx.ptk.yml` for workflows and preserve per-tool requirement inheritance.

The root `.main.ptk.yml` requires `repository: {alias: lowercase-name, config_path: relative/directory}`. Entry includes and automatic tool/CX/local/maintainer files use that directory; fragment includes stay fragment-relative and commands use the repository root. In `.repo` VMR workspaces, invoke `ptk <repository-alias> <command>`.

Start from `examples/authoring/.main.ptk.yml` and its fragments for a complete tested configuration. Read `docs/configuration.rst` for default environment isolation and explicit inheritance.

For version discovery, read `docs/versioning.rst` and exercise `tests/test_versioning.py`. Keep `.main.ptk.yml` minimal; use `ptk setup init --config-dir PATH` for starter fragments. Maintain `versioning.ptk.yml`, never commit `.gen.version.ptk.yml`. Use `PTK_VERSION_ALIAS_COMPONENT_NAME` and `${version.projects.alias.value}`; generators consume the run snapshot. Declare VMR version dependencies and their variants explicitly. Do not add bump/tag operations.
