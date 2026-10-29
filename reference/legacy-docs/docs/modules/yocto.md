# Yocto

**Package:** `xc_ce_utils.yocto`
**Purpose:** Yocto/Linux BSP tooling for embedded Linux ECU platforms

## Overview

Collection of utilities for embedded Linux platforms targeting NXP S32G-based systems (VPC-P, VCU-P). Provides device tree patching, TFTP/WIC flash script generation, metafile and RCON binary creation, CVE tracking, delivery packaging, and automated flash testing. Primarily consumed by the [SW Container Generator](sw_container_generator.md) pipeline.

## Sub-packages

| Sub-package | Module | Description |
|---|---|---|
| `rcon_bin_generator/` | `rcon_bin_generator.py` | EEPROM RCON binary generation from hex content |
| `metafile_generator/` | `metafile_generator.py` | Binary metafile generation with composite parameter blocks |
| `metafile_csv_generator/` | `metafile_csv_generator.py` | CSV metadata generation with automatic binary file splitting |
| `devicetree_patcher/` | `devicetree_patcher.py` | Linux device tree binary patching (ramdisk, ATF memory, SerDes/PCIe) |
| `tftp_flash_script_generator/` | `tftp_flash_script_generator.py` | TFTP flash script generation for U-Boot flashing |
| `wic_flasher/` | `wic_flasher.py` | Remote `.wic` image flashing via SSH/paramiko |
| `cve_handler/` | `cve_summary_parser.py`, `cve_excel_formatter.py` | Yocto CVE summary parsing and Excel report generation |
| `delivery_zipper/` | `delivery_zipper.py` | Packages Yocto build artifacts (images, SDK, CVE logs) into delivery ZIPs |
| `automated_tester/` | `automated_tester.py` | GUI-based flash test automation with Artifactory integration |

## Key Functions

```python
# RCON
generate_rcon_file(
    hex_content, output_path, little_endian=False, endiannes_block_size=4
)

# Metafile
generate_metafile(config_path, ...)

# Device tree
process_dtb_file(dtb_path, ramdisk_info, atf_memory, serdes_nodes, pcie_nodes)

# TFTP flash scripts
generate_tftp_task()
generate_check_success()

# WIC flashing
run_ssh_command(ssh_connection, command)

# CSV metadata
process_files(split_config, files, output_path, created_files)
```

## Install Extras

Sub-packages have optional pip extras defined in `pyproject.toml`:

```
yocto-wic-flasher
yocto-tftp-flash-script-generator
yocto-rcon-bin-generator
yocto-metafile-generator
yocto-metafile-csv-generator
yocto-devicetree-patcher
```

## Dependencies

- **External:** `paramiko` (SSH), `crcmod`, `pyelftools`
- **Internal:** `xc_ce_utils.binary_handling.bin_splittler`, `xc_ce_utils.artifactory_utils`, `xc_ce_utils.json_utils`, `xc_ce_utils.auth`

## See Also

- [SW Container Generator](sw_container_generator.md) — primary consumer of yocto sub-packages
- [Binary Handling](binary_handling.md) — binary splitting used by metafile CSV generator
