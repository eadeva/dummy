# Vector Generation

**Package:** `xc_ce_utils.vector_generation`
**Purpose:** Vector DaVinci Configurator integration for AUTOSAR MCAL code generation

## Overview

Manages Vector DaVinci Configurator `.dpa` project files for AUTOSAR MCAL (Microcontroller Abstraction Layer) code generation. Supports incremental generation with hash-based change detection, file locking for concurrent builds, and configurable module filtering. Provides both GUI-based manual configuration and automated headless generation modes.

## Module

| Module | Description |
|---|---|
| `vector_davinci_handler.py` | `VectorDaVinciHandler` — main handler for DaVinci Configurator/Developer |

## VectorDaVinciHandler

```python
handler = VectorDaVinciHandler(
    dpa_file="path/to/project.dpa",
    artifact_vector="path/to/DaVinciConfigurator",
    variant="hardware/arm_v8/oem_a",
    force_gen=False,
    vector_config=config_dict,
)
```

### Methods

| Method | Description |
|---|---|
| `configure(verbose)` | Launch DaVinci Configurator GUI for interactive configuration |
| `generate(module_list, modules_to_exclude, force_gen, skip_mcal, only_mcal, log_folder)` | Automated MCAL code generation |

### Features

- **Hash-based caching** — Configurable hash algorithm (`sha256`/`md5`) detects input changes to skip unnecessary regeneration
- **CDD module collapse** — Modules listed in `cdd_modules` are generated as a single DaVinci target: `Cdd`
- **Extended hash dependencies** — `vector.extra_hash_inputs` can add extra files (for non-MCAL modules) to smart-cache hashing
- **File locking** — Uses `filelock.FileLock` for safe concurrent builds
- **Generation timestamp stripping** — Removes timestamps from generated files for reproducible builds
- **State tracking** — `STATE_RUNNING`, `STATE_SUCCESSFUL`, `STATE_FAILED`

### Vector Config Keys

```yaml
dpa: path/to/project.dpa
generation_folder: path/to/generation/folder

# Any of these modules will be generated as DaVinci module "Cdd"
cdd_modules:
    - ModuleA
    - ModuleB

vector:
    # Module-specific extra inputs for hash-based regeneration checks
    # Relative paths are resolved from workspace root
    # Missing files are logged as warnings and ignored
    extra_hash_inputs:
        ModuleX:
            - path/to/header1.h
            - path/to/header2.h

tresos:
    executable_rel_path: ThirdParty/Mcal_Tc3xx/Supply/tresos/bin/tresos_cmd.bat
    mcal_modules:
        - Spi
```

Notes:
- `vector.extra_hash_inputs` currently applies to non-MCAL modules only.
- If any module in `cdd_modules` changes, the collapsed `Cdd` target is regenerated.

## Build Step Types

Registered in `core_engine/steps/vendor_steps.py`:

| Step Type | Class | Description |
|---|---|---|
| `vector_davinci_configure` | `VectorDavinciConfigureStep` | Opens DaVinci Configurator GUI |
| `vector_davinci_generate` | `VectorDavinciGenerateStep` | Automated code generation |

### Generation Step Parameters

| Parameter | Description |
|---|---|
| `skip_mcal` | Skip MCAL module generation |
| `only_mcal` | Generate only MCAL modules |
| `module_to_generate` | Specific module list to generate |
| `modules_to_exclude` | Modules to exclude from generation |

## Dependencies

- **External:** `rich_click`, `filelock`
- **Internal:** `xc_ce_utils.conf_file_loader`, `xc_ce_utils.core_engine.domain.exceptions`

## See Also

- [Tresos Generator](tresos_generator.md) — EB tresos code generation (complementary MCAL tool)
