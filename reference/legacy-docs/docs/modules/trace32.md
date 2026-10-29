# Trace32

**Package:** `xc_ce_utils.trace32`

Python wrapper for the Lauterbach TRACE32 hardware debugger C API.

---

## Trace32Api Class

Wraps the TRACE32 Remote API (`t32api64` DLL/SO) via ctypes for programmatic control of PowerView instances.

```python
from xc_ce_utils.trace32.trace32Api import Trace32Api

t32 = Trace32Api(cmm_path="scripts/tc3xx")
t32.start_power_view(architecture="tc", start_cmm_file="init.cmm")
t32.connect()
t32.execute_cmm("flash_firmware.cmm")
t32.disconnect()
```

### Key Operations

| Operation | Description |
|---|---|
| Flash binary/hex | Program firmware to ECU flash memory |
| Run CMM scripts | Execute PRACTICE `.cmm` automation scripts |
| Load ELF | Load debug symbols from ELF files |
| Erase flash | Erase ECU flash memory regions |
| Read/write variables | Access target memory |
| Execution control | go, break, step |

---

## State Enums

| Enum | Values |
|---|---|
| `PracticeInterpreterState` | `NOT_RUNNING`, `RUNNING`, `DIALOG_OPEN`, `UNKNOWN` |
| `MessageLineState` | `OK`, `ERROR`, `ERROR_INFO` |
| `Trace32State` | `DOWN`, `NOACCESS`, `HALTED`, `RUNNING`, `UNKNOWN` |

---

## Supported Architectures

| Key | Target | Executable |
|---|---|---|
| `tc` | TriCore | `t32mtc` |
| `arm` | ARM 32-bit | `t32marm` |
| `arm64` | ARM 64-bit | `t32marm64` |
| `renesas` | Renesas V850 | `t32mv800` |
| `ppc` | PowerPC 32-bit | `t32mppc` |
| `ppc64` | PowerPC 64-bit | `t32mppc64` |

---

## Step Types

| Step Type | Description |
|---|---|
| `t32_setup` | Configure and start PowerView |
| `t32_get_state` | Query debugger state |
| `t32_run_cmm_script` | Execute a CMM script |
| `t32_run_cmd` | Execute a TRACE32 command |
| `t32_erase_flash` | Erase flash memory |
| `t32_flash_binary` | Flash a binary file |
| `t32_flash_hex` | Flash an Intel HEX file |
| `t32_load_elf` | Load ELF debug symbols |
| `t32_close` | Disconnect and close |

---

## Configuration

Target architecture definitions in `config/` within the trace32 package. TRACE32 installation path from `TOOL_LAUTERBACH_DEBUGGER_PATH` environment variable.

---

## See Also

- [Power Supply](powersupply.md) — ECU power cycling before flash
- [COM I/O Handler](com_io_handler.md) — serial communication
