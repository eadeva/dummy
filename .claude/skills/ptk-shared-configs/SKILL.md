---
name: ptk-shared-configs
description: Manage ptk shared pre-commit, Ruff and clang configuration with project
  overlays.
---

# ptk-shared-configs

1. Read [docs/configuration.rst](../../../docs/configuration.rst); inspect available configuration fields with `ptk maintainer config schema` and preview effective files with `ptk maintainer sync configs --diff`.

2. Manage only tools declared under `configs`. Edit overlays rather than generated outputs.

3. For Ruff, extend generated `ruff-base.toml` from project-owned `ruff.toml`; do not set a Ruff overlay.

4. For pre-commit, match repositories by URL and hooks by id; use disable flags intentionally.

5. For clang YAML, inspect map/list/null merge behavior; clang-tidy checks and CheckOptions have special rules.

6. Preview `ptk maintainer sync configs --diff`, apply `ptk maintainer sync configs`, then run `ptk maintainer sync configs --check`.

7. Commit effective files and overlays together so CI and tools see the same configuration.

8. Run the actual affected formatter or linter when available. Keep optional binary-dependent checks explicit.

9. Review generated diffs after upgrading ptk rather than silently accepting new base rules.

10. With `configs.pre-commit.enabled: true`, commit the generated configuration
    before developers run jobs. Local jobs automatically install/repair the hooks;
    workflows check each participating repository before starting jobs. This works
    for normal users and does not synchronize configuration. Help, previews, CI,
    and disabled entries do not install hooks. Diagnose with `self-service doctor`.

11. Preserve existing hooks and custom Git settings. Resolve `core.hooksPath`,
    hook-file symlink or `.legacy` backup conflicts with the maintainer; do not
    blindly remove them. Use the same relative config path across linked worktrees.
    Enforce checks in CI because local hook installation cannot prevent bypass.

`maintainer sync configs` (including `--diff`) requires a login ID
listed in the configuration folder's `maintainers.ptk.yml`. `validate --generated`
checks generated configuration without writing and is available to normal users. Verify identity with `self-service doctor`; do not suggest
`PTK_ROLE=maintainer` as a workaround. See the maintainer section of the
[configuration guide](../../../docs/configuration.rst).
