# ALM Utils

**Package:** `xc_ce_utils.alm_utils`
**Purpose:** IBM ELM DNG (DOORS Next Generation) artifact export and transformation

## Overview

Connects to DNG servers, fetches requirements and artifacts from modules, applies configurable name/value transformations, and generates output in multiple formats. Supports multi-component, multi-configuration exports with link resolution across modules.

## Modules

| Module | Description |
|---|---|
| `alm_exporter.py` | `DNGExporter` — main orchestrator; connects to DNG, runs export pipeline |
| `alm_exporter_cli.py` | `xc-ce-dng-export` CLI built with rich-click |
| `config_models.py` | Pydantic v2 models: `DngExporterConfig`, `ExportAdaptionSet`, `ExportNameAdaption`, `ExportValueAdaption` |
| `config_loader.py` | YAML config loading with adaption resolution |
| `dng_export.py` | Pipeline classes: `DNGExport`, `DNGComponent`, `DNGModule` |
| `output_formatter.py` | Multi-format output (RST, CSV, JSON, YAML, Excel, Markdown) |
| `rst_exporter.py` | Sphinx-Needs RST directive rendering (`render_needs_directive()`, `write_module_rst()`) |

## Key Classes

### DNGExporter

Main entry point. Created via factory method then used to run exports:

```python
exporter = DNGExporter.from_config_path("config/dng/export_config.yml")
exporter.run_all_exports()
```

### Pipeline Classes

- `DNGExport` — top-level export definition (components, output format, adaptions)
- `DNGComponent` — DNG component scope (project area, configuration)
- `DNGModule` — single module fetch → enrich → adapt → write lifecycle

### Configuration Models

- `DngExporterConfig` — root Pydantic model for hierarchical YAML config
- `ExportAdaptionSet` — groups of attribute name/value transformations
- `AttributeAdaption` / `ArtifactTypeAdaption` — per-attribute and per-type mapping rules

## Output Formats

RST (Sphinx-Needs), CSV, JSON, YAML, Excel (`.xlsx`), Markdown

## CLI

```powershell
# Registered console script
xc-ce-dng-export export --config config/dng/export_config.yml
xc-ce-dng-export browse --server https://dng.example.com
xc-ce-dng-export lookup --artifact-id 12345
```

## Build Step Type

Registered as `dng_export` via `DngExportStep` in `core_engine/steps/vendor_steps.py`.

## Dependencies

- **External:** `elmclient`, `lxml`, `pydantic`, `pandas`, `markdownify`, `rich_click`
- **Internal:** `xc_ce_utils.auth`

## See Also

- [MCP Servers](mcp.md) — DNG MCP server provides AI-accessible requirement tools
- [Auth](auth.md) — credential management for DNG connections
