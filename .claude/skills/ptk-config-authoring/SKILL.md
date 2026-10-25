---
name: ptk-config-authoring
description: Create or change ptk YAML configuration, includes, layers and substitutions.
---

# ptk-config-authoring

1. Read `docs/configuration.rst` and the models in `src/ptk/domain/config/model.py`.

2. Use `main.ptk.yml` as the entry point and `*.ptk.yml` fragments. Keep `local.ptk.yml` untracked.

3. Preserve merge order: included files, CI overlay, local overlay, command-line overrides.

4. Remember that mappings merge deeply and lists replace; use `!append` or `!replace` intentionally.

5. Use `${vars.name}`, `${params.name}`, `${env:NAME:-fallback}` and `${vh.*}`; escape literal references with `$${...}`.

6. Inspect origins with `ptk config show --sources` before changing an unexpected effective value.

7. Export `ptk config schema -o schema.json` for editor support. Treat loader directives separately from model fields.

8. Verify with `ptk config validate`, then `ptk dry-run ACTION` for every affected variant.

9. Avoid unknown keys, unresolved references, recursive includes and unsupported `plugins` expectations.
