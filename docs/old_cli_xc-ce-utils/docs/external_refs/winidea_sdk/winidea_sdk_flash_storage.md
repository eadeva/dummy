# WinIDEA SDK — Flash & Storage Device API

**Module:** `isystem.connect`
**SDK Version:** 9.21.408.1

Reference for flash programming, storage device control, download configuration, and the legacy loader controller API.

---

## Modern Flash Workflow (Recommended)

The modern approach uses `CConfigurationController` to set up download files and `CSessionCtrl` to trigger the download.

```text
CConfigurationController
  └── ide_session().SoC(name).program_files()   ← configure HEX/ELF
                                                     to flash

CSessionCtrl
  ├── begin_program()    ← flash code + reset + halt
  └── program_verify()   ← verify flash integrity
```

### Complete Flash Example

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
cmgr.connect(conn_cfg)

# Configure what to flash
cfg_ctrl = ic.CConfigurationController(cmgr)
soc = cfg_ctrl.ide_session().SoC("MCU")
soc.program_files().clear()
soc.program_files().add_file(r"C:\firmware.hex", "HEX", 0)

# Flash and verify
sess_ctrl = ic.CSessionCtrl(cmgr)
sess_ctrl.begin_program()
sess_ctrl.program_verify()

# Check status
for soc_status in sess_ctrl.get_status().SoCs():
    print(soc_status.status_string())  # → 'ATTACHED'
```

---

## CStorageDeviceFactory

Factory for creating storage device controllers (embedded flash, eMMC, SPI, HyperFlash). Used for low-level device operations like erase.

### Storage Device Types

| Constant | Value | Description |
|---|---|---|
| `EStorageDevice_EmbeddedFlashDevice` | 0 | Embedded flash (PFLASH, DFLASH, UCB) |
| `EStorageDevice_EMMCDevice` | 1 | eMMC storage |
| `EStorageDevice_SPIDevice` | 2 | SPI flash |
| `EStorageDevice_HyperFlash` | 3 | HyperFlash |

### Factory Methods

| Method | Description |
|---|---|
| `makeDevice(cmgr, type, deviceName)` | Create controller by device name |
| `makeDevice(cmgr, type, deviceIndex)` | Create controller by device index |
| `getDeviceNames(cmgr, deviceNames)` | Get all enabled storage device names |
| `getDeviceInfo(cmgr, deviceName, elements)` | Get device info (partition-based devices) |
| `terminateDevice(cmgr, type, name/index)` | Terminate device connection (partition-based only) |

### Class Constant

| Constant | Description |
|---|---|
| `DEVICES_OPT_URL` | Option URL for storage devices configuration |

### Factory Example

```python
# Create controller for embedded flash device by index
stor_ctrl = ic.CStorageDeviceFactory.makeDevice(
    cmgr,
    ic.EStorageDevice_EmbeddedFlashDevice,
    device_index,  # e.g. DFLASH index from UMI discovery
)

# Erase the device
stor_ctrl.erase(ic.IConnectUMI.wProgDevice)
```

---

## CStorageDeviceController

Low-level storage device operations. Obtained from `CStorageDeviceFactory.makeDevice()`.

### Methods

| Method | Description |
|---|---|
| `erase(flags)` | Erase the device. Use `ic.IConnectUMI.wProgDevice` for standard erase. |
| `read(...)` | Read data from device |
| `write(...)` | Write data to device |
| `verify(...)` | Verify device content |
| `flush()` | Program the device from intermediate cache |
| `isDeviceEmpty(...)` | Check if device is empty |
| `readHash(...)` | Read hash of device content |
| `readState(...)` | Read the device program state |
| `getLastError()` | Get error description after a failed call |
| `getSecurityModule()` | Get security storage device module |
| `getPartitionConfigurationModule()` | Get partition configuration (partition-based devices) |

### DFLASH Erase Example (TC3xx)

```python
# Discover DFLASH device index via UMI options
umi_opt = ic.COptionController(cmgr, "/iOPEN/Data.UMI.Devices.Devices")
for i in range(umi_opt.size()):
    name = umi_opt.at(i).get("Name")
    if "_DFLASH_" in name:
        dflash_index = i
        break

# Erase DFLASH before programming
dflash_ctrl = ic.CStorageDeviceFactory.makeDevice(
    cmgr,
    ic.EStorageDevice_EmbeddedFlashDevice,
    dflash_index,
)
dflash_ctrl.erase(ic.IConnectUMI.wProgDevice)
```

---

## UMI Device Discovery

UMI (Universal Memory Interface) devices are discovered by iterating the device options. This is how you find PFLASH, DFLASH, and UCB devices for TC3xx targets.

```python
umi_opt = ic.COptionController(cmgr, "/iOPEN/Data.UMI.Devices.Devices")
num_devices = umi_opt.size()

for i in range(num_devices):
    dev = umi_opt.at(i)
    name = dev.get("Name")
    enabled = dev.get("Enabled")
    print(f"Device {i}: {name} (Enabled: {enabled})")
```

### Enable/Disable Devices

```python
dev_opt = umi_opt.at(device_index)
dev_opt.set("Enabled", "true")  # enable
dev_opt.set("Enabled", "false")  # disable

# DFLASH: allow erase
dev_opt.set("AllowErase", "true")
```

### TC3xx Device Naming Convention

| Pattern | Device Type | Typical Flash Operation |
|---|---|---|
| `*_PFLASH_*` | Program Flash | Direct programming (no pre-erase needed) |
| `*_DFLASH_*` | Data Flash (FEE) | Requires explicit erase before programming |
| `*_UCB_*` | User Configuration Block | Disable other devices first, then program |

---

## Legacy API: CLoaderController

> **Deprecated since 9.21.x.** Use `CConfigurationController` + `CSessionCtrl` instead.

Obtained via `CDebugFacade.getLoaderController()`.

### Methods

| Method | Status | Replacement |
|---|---|---|
| `download()` | **Deprecated** | `CSessionCtrl.begin_program()` |
| `downloadWithoutCode()` | **Deprecated** | `CSessionCtrl.begin_reset()` |
| `addToDownloadList(...)` | **Deprecated** | `CConfigurationController/COptionController` |
| `removeFromDownloadList(...)` | **Deprecated** | `CConfigurationController/COptionController` |
| `clearDownloadList(...)` | **Deprecated** | `CConfigurationController/COptionController` |
| `getDownloadList(...)` | **Deprecated** | `CConfigurationController/COptionController` |
| `downloadFromList(...)` | **Deprecated** | Will not be replaced |
| `targetDownload(...)` | — | Downloads a target file without resetting |
| `verifyDownload()` | — | `CSessionCtrl.program_verify()` |

### Download List Types

| Constant | Description |
|---|---|
| `DLIST_PRIMARY` | Main download list (program files) |
| `DLIST_TARGET` | Target download list (target-specific files) |

### Legacy `addToDownloadList()` Signatures

**Overload 1** (simple):
```python
loader.addToDownloadList(listType, fileName, isAbsolutePath, options)
```

**Overload 2** (with config):
```python
loader.addToDownloadList(downloadConfig, listType, fileName, cmdLineOptions)
```

### Legacy `targetDownload()` Signatures

Downloads a file from the target file list **without resetting** the target.

```python
# With CDownloadConfiguration
loader.targetDownload(downloadConfig, fileName, cmdLineOptions)

# Simple (string options)
loader.targetDownload(fileName, isAbsolutePath, options)
```

---

## Legacy API: CDownloadConfiguration

Configuration object for legacy download operations.

### File Format Constants

| Constant | Format |
|---|---|
| `ftELF` | ELF |
| `ftIntelHex` | Intel HEX |
| `ftMotorolaS` | Motorola S-record |
| `ftBinary` | Raw binary |
| `ftTektronix` | Tektronix |
| `ftExtendedTektronix` | Extended Tektronix |
| `ftOMF86` | OMF-86 |
| `ftOMF166` | OMF-166 |
| `ftOMF51` | OMF-51 |
| `ftOMF96` | OMF-96 |
| `ftOMF251` | OMF-251 |
| `ftIEEE695` | IEEE-695 |
| `ftCR16COFF` | CR16 COFF |
| `ftTMSCOFF` | TMS COFF |
| `ftStabs` | Stabs |
| `ftUBROF` | UBROF |
| `ftPE` | PE (Windows executable) |

### Configuration Methods

| Method | Description |
|---|---|
| `setDownloadFileFormat(format)` | Set file format (use constants above) |
| `setCodeOffset(offset)` | Set code load offset |
| `setSymbolsOffset(offset)` | Set symbols load offset |
| `setMemoryArea(area)` | Set target memory area |
| `setUsedInFullDownload(flag)` | Include in full download |
| `setIsProjectOutputFile(flag)` | Mark as project output file |
| `setInProjectTargetDir(flag)` | File is in project target directory |
| `setForceConvert(flag)` | Force file format conversion |
| `setRealTimeAccess(flag)` | Use real-time memory access |
| `setUseAbsolutePath(flag)` | Use absolute path |
| `setTypeEqualByName(flag)` | Type-equal-by-name matching |

### Getter Methods

| Method | Returns |
|---|---|
| `getMemoryArea()` | Memory area |
| `isForceConvert()` | Force convert flag |
| `isRealTimeAccess()` | Real-time access flag |
| `isUseAbsolutePath()` | Absolute path flag |

---

## Legacy API: CDebugFacade

High-level debug facade wrapping multiple controllers. Created from a `ConnectionMgr`.

```python
debug = ic.CDebugFacade(cmgr)
```

### Download-Related Methods

| Method | Description |
|---|---|
| `download()` | Flash program files (deprecated → use `CSessionCtrl.begin_program()`) |
| `getLoaderController()` | Get the `CLoaderController` instance |

### Symbol-Related Methods

| Method | Description |
|---|---|
| `getSymbolAtAddress(...)` | Get symbol name at a memory address |
| `getSymbolInfo(...)` | Get detailed symbol information |

### Execution Control Methods

| Method | Description |
|---|---|
| `run()` | Start/resume target execution |
| `stop()` | Stop target execution |
| `reset()` | Reset target |
| `stepInst()` | Step one instruction |
| `stepHigh()` | Step one high-level statement |
| `stepOverInst()` | Step over one instruction |
| `stepOverHigh()` | Step over one high-level statement |
| `call(function)` | Call a function on the target |
| `gotoAddress(area, address)` | Set PC to address |
| `gotoFunction(function)` | Set PC to function entry |
| `runUntilAddress(...)` | Run until hitting an address |
| `runUntilFunction(...)` | Run until hitting a function |
| `runUntilExpression(...)` | Run until expression is true |
| `runUntilReturn(...)` | Run until function returns |
| `getCPUStatus(...)` | Get CPU execution status |
| `waitUntilStopped(...)` | Wait for target to stop |
| `waitWhileRunning(...)` | Wait while target is running |
| `setSlowRun(flag)` | Enable/disable slow run mode |
| `setPollingEnabled(flag)` | Enable/disable polling |

### Data Access Methods

| Method | Description |
|---|---|
| `evaluate(expression)` | Evaluate an expression on the target |
| `modify(variable, value)` | Modify a variable |
| `readMemory(...)` | Read memory |
| `writeMemory(...)` | Write memory |
| `readRegister(...)` | Read a register |
| `writeRegister(...)` | Write a register |
| `readValue(...)` | Read typed value from memory |
| `writeValue(...)` | Write typed value to memory |
| `getCPUInfo(...)` | Get CPU information |
| `getMemoryAreaBytesPerMAU(area)` | Get bytes per MAU for a memory area |

### Address Resolution Methods

| Method | Description |
|---|---|
| `getAddressOfSourceLine(...)` | Get address for a source line |
| `getSourceLineAtAddress(...)` | Get source line for an address |
| `getFunctionAddress(name)` | Get address of a function |
| `getLabelAddress(name)` | Get address of a label |
| `getVariableAddress(name)` | Get address of a variable |
| `getExpressionAddress(expr)` | Evaluate address expression |
| `getCodeArea(...)` | Get code area bounds |

### Breakpoint Methods

| Method | Description |
|---|---|
| `setBP(...)` | Set software breakpoint |
| `deleteBP(...)` | Delete software breakpoint |
| `deleteAll()` | Delete all software breakpoints |
| `setEnabled(...)` | Enable/disable a breakpoint |
| `setEnabledAll(flag)` | Enable/disable all breakpoints |
| `setHWBP(...)` | Set hardware breakpoint |
| `deleteHWBP(...)` | Delete hardware breakpoint |
| `deleteAllHWBP()` | Delete all hardware breakpoints |
| `setHWEnabled(...)` | Enable/disable a hardware breakpoint |
| `setHWEnabledAll(flag)` | Enable/disable all hardware breakpoints |
| `reapplyAll()` | Reapply all breakpoints |

### Sub-Controller Access

| Method | Returns |
|---|---|
| `getAddressController()` | Address controller |
| `getBreakpointController()` | Breakpoint controller |
| `getDataController()` | Data controller |
| `getExecutionController()` | Execution controller |
| `getLoaderController()` | Loader controller (deprecated) |

---

## Migration Guide: Legacy → Modern API

| Legacy Pattern | Modern Replacement |
|---|---|
| `debug.getLoaderController().clearDownloadList(...)` | `cfg_ctrl.ide_session().SoC(name).program_files().clear()` |
| `debug.getLoaderController().addToDownloadList(...)` | `soc.program_files().add_file(path, type, offset)` |
| `debug.getLoaderController().download()` | `sess_ctrl.begin_program()` |
| `debug.getLoaderController().downloadWithoutCode()` | `sess_ctrl.begin_reset()` |
| `debug.getLoaderController().verifyDownload()` | `sess_ctrl.program_verify()` |
| `debug.download()` | `sess_ctrl.begin_program()` |

### Legacy (Deprecated)

```python
debug = ic.CDebugFacade(cmgr)
loader = debug.getLoaderController()
loader.clearDownloadList(ic.CLoaderController.DLIST_PRIMARY)
loader.addToDownloadList(
    ic.CLoaderController.DLIST_PRIMARY, r"C:\firmware.hex", True, ""
)
loader.download()
loader.verifyDownload()
```

### Modern (Recommended)

```python
cfg_ctrl = ic.CConfigurationController(cmgr)
soc = cfg_ctrl.ide_session().SoC("MCU")
soc.program_files().clear()
soc.program_files().add_file(r"C:\firmware.hex", "HEX", 0)

sess_ctrl = ic.CSessionCtrl(cmgr)
sess_ctrl.begin_program()
sess_ctrl.program_verify()
```
