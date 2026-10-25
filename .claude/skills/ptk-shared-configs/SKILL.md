---
name: ptk-shared-configs
description: Manage ptk shared pre-commit, Ruff and clang configuration with project
  overlays.
---

# ptk-shared-configs

1. Read `src/ptk/domain/shared_configs.py` and `src/ptk/resources/configs/`.

2. Manage only tools declared under `configs`. Edit overlays rather than generated outputs.

3. For Ruff, extend generated `ruff-base.toml` from project-owned `ruff.toml`; do not set a Ruff overlay.

4. For pre-commit, match repositories by URL and hooks by id; use disable flags intentionally.

5. For clang YAML, inspect map/list/null merge behavior; clang-tidy checks and CheckOptions have special rules.

6. Preview `ptk configs sync --diff`, apply `ptk configs sync`, then run `ptk configs check`.

7. Commit effective files and overlays together so CI and tools see the same configuration.

8. Run the actual affected formatter or linter when available. Keep optional binary-dependent checks explicit.

9. Review generated diffs after upgrading ptk rather than silently accepting new base rules.
