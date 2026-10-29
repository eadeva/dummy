# ELF Utils

**Package:** `xc_ce_utils.elf_utils`
**Purpose:** ELF/DWARF debug information extraction and source path utilities

## Overview

Provides tools for extracting debug information from ELF files using the DWARF standard. The primary use case is automatic source path remapping for CI-built binaries that are debugged on local developer machines (where the source checkout path differs from the build machine).

Works with any compiler that emits DWARF debug info (GCC, TASKING, Clang, IAR, etc.).

## Modules

| Module | Description |
|---|---|
| `elf_utils.py` | Core ELF/DWARF extraction: `get_elf_build_root()`, `compute_source_remap()` |

## Key Functions

```python
from xc_ce_utils.elf_utils import get_elf_build_root, compute_source_remap

# Extract the build-machine project root from DWARF DW_AT_comp_dir
# Strips everything from "_build" marker onwards
root = get_elf_build_root("path/to/firmware.elf")
# → "C:/jenkins/workspace/gw_2wp"

# Auto-compute source remap rule (ELF root → cwd)
remap = compute_source_remap("path/to/firmware.elf")
# → "C:/jenkins/workspace/gw_2wp=C:/git/2WP/gw_2wp"  (or None if already matching)
```

## How It Works

1. Reads the first `DW_AT_comp_dir` attribute from DWARF compilation unit headers
2. Splits the path at the `_build` directory marker (xc-ce-utils build convention)
3. Everything before `_build` is the project root on the **build machine**
4. Maps it to the current working directory (the local repo checkout)

## Dependencies

- **pyelftools** ≥ 0.32 (optional, installed via `pip install xc-ce-utils[elf-utils]`)

## Integration

Used by `xc_ce_utils.winidea` via the `source_remap_auto: true` parameter in WinIDEA session configuration to automatically fix source paths when debugging CI-produced ELF files locally.

```yaml
# winidea.yml
configure_session:
  step_type: winidea_configure_session
  parameters:
    symbol_files:
      App: _bin/pl9/build/GW_2WP.elf
    source_remap_auto: true  # ← uses elf_utils under the hood
```

## See Also

- [WinIDEA](winidea.md) — primary consumer (source path remapping)
- [Binary Handling](binary_handling.md) — related binary-format utilities
