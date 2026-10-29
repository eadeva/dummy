# TRESOS Generator

**Package:** `xc_ce_utils.tresos_generator`

EB tresos AUTOSAR project management and configuration generation.

---

## Purpose

Automates Elektrobit tresos Studio project lifecycle: delete workspace projects, import projects, and generate AUTOSAR configurations. Supports hash-based caching for incremental generation and file locking for concurrent access.

---

## Key Functions

| Function | Description |
|---|---|
| `delete_projects(names)` | Remove projects from tresos workspace |
| `import_projects(names)` | Import projects into tresos workspace |
| `generate_projects(names)` | Generate AUTOSAR configurations |
| `has_project_changed(name, path)` | Check if regeneration is needed (hash comparison) |

### Hash-Based Caching

1. Computes SHA-256 of all `.xdm` files in the project
2. Stores hashes in `.tresos_input_hashes.json`
3. On next run, compares current hashes with stored manifest
4. Skips generation if unchanged — significant CI/CD speedup

### File Locking

Uses `FileLock` to prevent concurrent tresos generation processes from conflicting.

---

## Step Types

| Step Type | Description |
|---|---|
| `tresos_configure` | Import and configure tresos projects |
| `tresos_generate` | Generate AUTOSAR configuration code |

---

## Build System Usage

```bash
# Generate AUTOSAR configurations
./build.ps1 -var <variant> autosar_conf
```

---

## See Also

- [Execution Engine](../core_engine/05_building_block_view.md) — build orchestration
- [Global Modules](global_modules.md) — file locking utility
