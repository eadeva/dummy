---
name: ptk-shared-configs
description: Manage pinned external configuration bases and project-owned overlays.
---

# ptk-shared-configs

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [external configuration ownership](../../../docs/guides/shared-configs.rst) and inspect the runtime schema with `ptk maintainer config schema`.
2. Declare a general `source.repository` and `source.revision` plus per-group `files` mappings with `source` and `destination`. PTK ships no bases. Use an explicit version tag or full commit hash, never an invented repository or floating branch.
3. External destinations are unchanged copies. Never edit them in the consuming project. Inspect their provenance and content hashes in `.ptk-configs.lock.json` inside the project’s `repository.config_path` directory.
4. For pre-commit/clang customization, author a project-owned `overlay` and a separate generated `output`. Never merge into the base. Preserve native merge semantics.
5. For Ruff, author project-owned `ruff.toml` with native `extend` pointing to the external copy. Ruff has no overlay/generation mode.
6. Preview `ptk maintainer sync configs --diff`, apply `ptk maintainer sync configs`, then run offline `ptk validate --generated`. There is no configs.sync step; jobs must not synchronize policy.
7. Commit the source mapping, bases, lock, overlays and generated results together. Change revision explicitly to upgrade; a locked tag does not follow tag movement. Resolve modified-file conflicts through review, never force overwrite.
8. Files remain writable. Offline checks compare contents/executable bits; use `ptk maintainer configs-report` to export effective deviations and modified base filenames. The lock is provenance, not independent authentication.
9. Removing mappings leaves files untouched. Review obsolete files and run affected linters/formatters. Commit or push only within authorized scope.

10. With `configs.pre-commit.enabled: true`, commit the generated configuration
    before developers run jobs. Local jobs automatically install/repair the hooks;
    workflows check each participating repository before starting jobs. This works
    for normal users and does not synchronize configuration. Help, previews, CX,
    and disabled entries do not install hooks. Diagnose with `ptk self-service doctor`.

11. Preserve existing hooks and custom Git settings. Resolve `core.hooksPath`,
    hook-file symlink or `.legacy` backup conflicts with the maintainer; do not
    blindly remove them. Use the same relative config path across linked worktrees.
    Enforce checks in CX because local hook installation cannot prevent bypass.

`maintainer sync configs` (including `--diff`) requires a login ID
listed in the configuration folder's `maintainers.ptk.yml`. `validate --generated`
checks generated configuration without writing and is available to normal users. Verify identity with `self-service doctor`; do not suggest
`PTK_ROLE=maintainer` as a workaround. See the maintainer section of the
[configuration guide](../../../docs/guides/configuration.rst).
