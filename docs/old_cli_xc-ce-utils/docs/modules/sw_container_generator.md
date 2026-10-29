# SW Container Generator

**Package:** `xc_ce_utils.sw_container_generator`
**Purpose:** ECU software container packaging for automotive flash delivery

## Overview

Orchestrates the full firmware container build pipeline: downloads artifacts from Artifactory, applies binary conversions (BIN/HEX/SREC, padding, signing, CRC), generates RCON and metafiles, creates ECU-MEM XML descriptors validated against XSD, and packages everything into ZIP containers. Includes tkinter GUIs for interactive configuration.

## Modules

| Module | Description |
|---|---|
| `sw_container_generator.py` | Main orchestrator — `process_container_file()`, `execute_script()` |
| `sw_container_xml_generator.py` | ECU-MEM XML generation + XSD validation |
| `sw_container_packager.py` | ZIP packaging |
| `version_finder.py` | Artifactory version discovery |
| `pipeline_config_generator.py` | CI/CD pipeline config generation |
| `gui_sw_container_generator.py` | `RBSWContainerGeneratorGUI` — tkinter GUI |
| `gui_sw_container_configurator.py` | Generic container config GUI |
| `gui_generic_config_window.py` | Reusable tkinter config window |
| `sw_container.xsd` | XML Schema for container validation |

## Pipeline

1. **Download** — Fetch binary artifacts from Artifactory (via `version_finder.py`)
2. **Convert** — Apply binary operations: format conversion, padding, signing, CRC (via `binary_handling`)
3. **Generate** — Create RCON binaries, metafiles, device tree patches (via `yocto` sub-packages)
4. **Validate** — Generate ECU-MEM XML and validate against `sw_container.xsd`
5. **Package** — ZIP the container folder

## Key Functions

```python
process_container_file(file, file_path, global_variables, intermediate_files_to_remove)
generate_xml(project_info, submitter_info, sessions_config, container_path, controller)
validate_xml_against_schema(sw_container_xml_path)
zip_folder(container_folder_path, output_path)
find_versions(config_data, container)
```

## Binary Operations Pipeline

The orchestrator processes each container file through configured operations:

- `rcon_gen` — RCON binary generation
- `metafile_gen` — Metafile binary generation
- `bin_convert` / `hex_convert` — Format conversions
- `padding` — Block-size alignment
- `signing` — ECU-PKI binary signing

## GUI Mode

```python
gui = RBSWContainerGeneratorGUI(config_json="container_config.json")
```

Provides interactive selection of container configurations, version discovery, and generation triggers.

## Dependencies

- **External:** `lxml`
- **Internal:** `xc_ce_utils.binary_handling`, `xc_ce_utils.artifactory_utils`, `xc_ce_utils.json_utils`, `xc_ce_utils.yocto` (tftp, metafile, devicetree, rcon sub-packages)

## See Also

- [Binary Handling](binary_handling.md) — conversion, signing, CRC operations
- [Yocto](yocto.md) — RCON, metafile, devicetree, TFTP generators
- [Artifactory Utils](artifactory_utils.md) — artifact download
