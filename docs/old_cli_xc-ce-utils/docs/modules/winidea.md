# WinIDEA

**Package:** `xc_ce_utils.winidea`

Python wrapper for the iSYSTEM winIDEA debugging and flashing environment, using the `isystem.connect` SDK.

---

## Architecture

```text
WinIdeaApi  (generic, device-family-agnostic)
└── WinIdeaTC3xxApi  (Infineon AURIX TC3xx specialization)
```

The generic base class handles connection management, session configuration, and download-and-verify. The TC3xx subclass adds PFLASH/DFLASH/UCB device discovery and region-specific flashing logic.

---

## WinIdeaApi Class

Base class wrapping `isystem.connect` for programmatic control of winIDEA instances.

```python
from xc_ce_utils.winidea.winidea_api import WinIdeaApi

wi = WinIdeaApi(
    device="TC387QP",
    emulator_type="iC5000",
    com_mode="USB",
    winidea_dir=r"C:\iSYSTEM\winIDEA",
    workspace_dir=r"C:\workspace\tc387",
)
wi.connect(headless=True)
wi.program_and_verify("Flash firmware")
wi.reset_target()
wi.disconnect()
```

### Constructor Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `device` | str | Yes | Target device (e.g. `"TC387QP"`, `"TC397XA"`) |
| `emulator_type` | str | Yes | Debug probe type (e.g. `"iC5000"`, `"iC5500"`) |
| `com_mode` | str | Yes | Communication mode (`"USB"`, `"ETH"`) |
| `winidea_dir` | str | Yes | Path to winIDEA installation directory |
| `workspace_dir` | str | Yes | Path to winIDEA workspace directory |
| `log_file` | str | No | Path for log file output |
| `sym_path` | str | No | ELF symbol file path |

### Key Methods

| Method | Description |
|---|---|
| `connect(headless=True)` | Lazy-import `isystem.connect`, open connection to winIDEA |
| `configure_session()` | Apply device, emulator, and communication settings |
| `program_and_verify(description)` | Execute download-and-verify via `CFlashController` |
| `set_device_enabled(device_opt, enabled)` | Enable/disable a download file device (static) |
| `reset_target()` | Perform target reset via `CExecutionController` |
| `disconnect()` | Close connection and release resources |
| `is_connected` (property) | Check if connection is active |

---

## WinIdeaTC3xxApi Class

Infineon AURIX TC3xx specialization with PFLASH/DFLASH/UCB device handling.

```python
from xc_ce_utils.winidea.winidea_tc3xx_api import WinIdeaTC3xxApi

wi = WinIdeaTC3xxApi(
    device="TC397XA",
    emulator_type="iC5000",
    com_mode="USB",
    winidea_dir=r"C:\iSYSTEM\winIDEA",
    workspace_dir=r"C:\workspace\tc397",
)
wi.connect()
wi.discover_devices()
wi.flash_pflash("firmware.hex", sym_path="firmware.elf")
wi.flash_dflash("fee_data.hex")
wi.flash_ucb("ucb_config.hex")
wi.reset_target()
wi.disconnect()
```

### TC3xx-Specific Methods

| Method | Description |
|---|---|
| `discover_devices()` | Scan UMI download files for `_PFLASH_`, `_DFLASH_`, `_UCB_` devices |
| `flash_pflash(hex_path, sym_path=None)` | Enable PFLASH device, set hex/sym paths, program and verify |
| `flash_dflash(hex_path)` | Enable DFLASH device, erase first, then program and verify |
| `flash_ucb(hex_path)` | Disable all non-UCB devices, enable UCB, program and verify |

### Device Discovery

`discover_devices()` iterates the UMI download file table and identifies devices by naming convention:

| Device Type | UMI Name Pattern | Notes |
|---|---|---|
| PFLASH | `*_PFLASH_*` | Program flash — main firmware storage |
| DFLASH | `*_DFLASH_*` | Data flash (FEE) — requires erase before programming |
| UCB | `*_UCB_*` | User Configuration Block — disables other devices first |

### Flash Region Differences

| Region | Erase Before Flash | Other Devices | Typical Content |
|---|---|---|---|
| PFLASH | No (handled by winIDEA) | Left as-is | Firmware binary |
| DFLASH | Yes (explicit erase) | Left as-is | FEE/NvM calibration data |
| UCB | No | Disabled first | Security/boot configuration |

---

## Step Types

| Step Type | Description |
|---|---|
| `winidea_setup` | Connect to winIDEA, discover TC3xx devices (**game_stopper**) |
| `winidea_flash_pflash` | Flash PFLASH region |
| `winidea_flash_dflash` | Flash DFLASH region (includes erase) |
| `winidea_flash_ucb` | Flash UCB (disables other devices first) |
| `winidea_reset` | Reset target |
| `winidea_close` | Disconnect and release resources |

---

## Configuration

### YAML Example

```yaml
winidea_init:
  type: winidea_setup
  game_stopper: true
  parameters:
    WINIDEA_ID: wi_tc397
    device: TC397XA
    emulator_type: iC5000
    com_mode: USB
    winidea_dir: C:\iSYSTEM\winIDEA
    workspace_dir: ${REPO_ROOT}\config\winidea\tc397
    sym_path: ${BIN_DIR}\firmware.elf

flash_firmware:
  type: winidea_flash_pflash
  parameters:
    WINIDEA_ID: wi_tc397
    hex_file: ${BIN_DIR}\firmware.hex

flash_fee_data:
  type: winidea_flash_dflash
  parameters:
    WINIDEA_ID: wi_tc397
    hex_file: ${BIN_DIR}\fee_data.hex

flash_ucb_config:
  type: winidea_flash_ucb
  parameters:
    WINIDEA_ID: wi_tc397
    hex_file: ${BIN_DIR}\ucb_config.hex

reset_after_flash:
  type: winidea_reset
  parameters:
    WINIDEA_ID: wi_tc397

winidea_teardown:
  type: winidea_close
  parameters:
    WINIDEA_ID: wi_tc397
```

### Step Parameters

#### winidea_setup

| Parameter | Type | Required | Description |
|---|---|---|---|
| `WINIDEA_ID` | str | Yes | Instance identifier for the resource pool |
| `device` | str | Yes | Target device (e.g. `"TC387QP"`, `"TC397XA"`) |
| `emulator_type` | str | Yes | Debug probe type (e.g. `"iC5000"`, `"iC5500"`) |
| `com_mode` | str | Yes | Communication mode (`"USB"`, `"ETH"`) |
| `winidea_dir` | str | Yes | Path to winIDEA installation |
| `workspace_dir` | str | Yes | Path to winIDEA workspace directory |
| `sym_path` | str | No | ELF symbol file path |

#### winidea_flash_pflash / winidea_flash_dflash / winidea_flash_ucb

| Parameter | Type | Required | Description |
|---|---|---|---|
| `WINIDEA_ID` | str | Yes | Instance identifier (must match setup) |
| `hex_file` | str | Yes | Path to HEX file to program |

#### winidea_reset / winidea_close

| Parameter | Type | Required | Description |
|---|---|---|---|
| `WINIDEA_ID` | str | Yes | Instance identifier (must match setup) |

---

## Resource Pool

WinIDEA instances are stored in `self.resources["winideas"]` keyed by `WINIDEA_ID`. The `ExecutionEngine` initializes this pool and releases all connections in `_release_resources()`.

Multiple WinIDEA instances can coexist (e.g. multi-target setups) by using different `WINIDEA_ID` values.

---

## Dependencies

- **isystem.connect** — iSYSTEM Python SDK (lazy-imported at runtime to avoid hard dependency)
- winIDEA installation on the host machine

---

## iSYSTEM SDK Reference

Detailed API documentation for the `isystem.connect` SDK classes used by this module:

- [Connection & Workspace API](../external_refs/winidea_sdk/winidea_sdk_connection.md)
- [Configuration API](../external_refs/winidea_sdk/winidea_sdk_configuration.md)
- [Session Control API](../external_refs/winidea_sdk/winidea_sdk_session_control.md)
- [SoC, Core & Process Control API](../external_refs/winidea_sdk/winidea_sdk_soc_core_control.md)
- [Flash & Storage Device API](../external_refs/winidea_sdk/winidea_sdk_flash_storage.md)

---

## See Also

- [Trace32](trace32.md) — Lauterbach TRACE32 debugger integration
- [Power Supply](powersupply.md) — ECU power cycling before flash
- [COM I/O Handler](com_io_handler.md) — Serial communication
