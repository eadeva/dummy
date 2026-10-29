# WinIDEA SDK — Configuration API

**Module:** `isystem.connect`
**SDK Version:** 9.21.408.1

Reference for the configuration hierarchy: `CConfigurationController`, option controllers, and file configuration classes used to set up the debug session before triggering a download.

---

## Configuration Hierarchy

```text
CConfigurationController
├── bb_HW()              → BlueBox hardware options
├── bb_SoC(nSoC)         → BlueBox SoC options (per SoC index)
├── ide_session()         → COptionSessionCfg
│   ├── .SoC(name)        → COptionSoCCfg
│   │   ├── .program_files()   → COptionFilesCfg  (HEX/ELF to flash)
│   │   ├── .memory_spaces()   → SoC memory space config
│   │   └── .add_SMP(...)      → SMP core binding
│   ├── .app(name)        → COptionAppCfg
│   │   └── .symbol_files()    → COptionFilesCfg  (ELF symbols)
│   ├── .apps()           → list of all applications
│   ├── .SoCs()           → list of all SoCs
│   └── .add_app(name)    → create new application
├── ide_SoCs()            → SoCs configuration node
├── ide_SoC(name)         → Single SoC config (COptionSoCCfg)
├── ide_SoC_files(name)   → COptionFilesCfg for SoC program files
├── ide_SoC_memory_spaces(name) → Memory space configuration
├── ide_apps()            → Applications configuration node
├── ide_app(name)         → Single app config (COptionAppCfg)
├── ide_app_files(name)   → COptionFilesCfg for app symbol files
├── ide_opt()             → IDE options
├── ide_ws()              → Workspace config
├── ide_ws_info()         → Workspace info (read-only)
├── ide_license()         → Workspace license
├── ide_license_TLM()     → TLM license
├── ide_test()            → iTest configuration
├── doc(name)             → Document config
├── doc_an_triggers()     → Analyzer triggers
├── doc_an_trig_processes()  → Trigger processes
├── doc_an_trig_process_profiler_code()
├── doc_an_trig_process_profiler_data()
├── doc_an_trig_process_profiler_OS()
├── plugin_config()       → Plugin configuration
└── prototype()           → Prototype configuration
```

---

## CConfigurationController

Main entry point for all winIDEA configuration. Created from a `ConnectionMgr`.

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
cmgr.connect(conn_cfg)

cfg_ctrl = ic.CConfigurationController(cmgr)
```

### Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `bb_HW()` | `COptionController` | BlueBox hardware configuration | 9.21.194 |
| `bb_SoC(nSoC=0)` | `COptionController` | BlueBox SoC configuration by index | 9.21.194 |
| `ide_session()` | `COptionSessionCfg` | Debug session configuration | 9.21.268 |
| `ide_SoCs()` | `COptionController` | All SoCs configuration | 9.21.25 |
| `ide_SoC(name)` | `COptionSoCCfg` | Named SoC configuration | 9.21.157 |
| `ide_SoC_files(name)` | `COptionFilesCfg` | SoC program files list | 9.21.157 |
| `ide_SoC_memory_spaces(name)` | `COptionController` | SoC memory spaces | 9.21.405 |
| `ide_apps()` | `COptionController` | All applications configuration | 9.21.25 |
| `ide_app(name)` | `COptionAppCfg` | Named application configuration | 9.21.157 |
| `ide_app_files(name)` | `COptionFilesCfg` | Application symbol files | 9.21.157 |
| `ide_opt()` | `COptionController` | IDE options | 9.21.25 |
| `ide_ws()` | `COptionController` | Workspace configuration | 9.21.25 |
| `ide_ws_info()` | `COptionController` | Workspace info (read-only) | 9.21.188 |
| `ide_license()` | `COptionController` | Workspace license | 9.21.288 |
| `ide_license_TLM()` | `COptionController` | TLM license | 9.21.288 |
| `ide_test()` | `COptionController` | iTest configuration | 9.21.25 |

---

## COptionSessionCfg

Returned by `cfg_ctrl.ide_session()`. Access to SoCs and applications within the session.

### Session-Specific Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `SoC(name)` | `COptionSoCCfg` | Get SoC configuration by name | 9.21.157 |
| `SoCs()` | `COptionController` | List all SoCs | 9.21.157 |
| `app(name)` | `COptionAppCfg` | Get application by name | 9.21.157 |
| `apps()` | `COptionAppsCfg` | List all applications | 9.21.157 |
| `add_app(name)` | `COptionAppCfg` | Add a new application | 9.21.157 |

### Inherited (from COptionController)

| Method | Description |
|---|---|
| `URL()` | Full option URL |
| `get(option)` | Get string value |
| `set(option, value)` | Set string value |
| `get_bool(option)` / `set_bool(option, value)` | Bool access |
| `get_int(option)` / `set_int(option, value)` | Int access |
| `set_multi(params)` | Set multiple values at once |
| `size()` | Array element count |
| `at(index)` | Element by index |
| `find(option, value)` | Find element by option value |
| `add()` / `remove(index)` / `clear()` | Array manipulation |

---

## COptionSoCCfg

Configuration for a single SoC within the session. Returned by `session.SoC(name)` or `cfg_ctrl.ide_SoC(name)`.

### SoC-Specific Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `program_files()` | `COptionFilesCfg` | Program files to download to this SoC | 9.21.157 |
| `memory_spaces()` | `COptionController` | Memory space configuration | 9.21.405 |
| `add_SMP(name, cores)` | `COptionController` | Add SMP core binding | 9.21.157 |
| `add_memory_space(name, location, app)` | `COptionController` | Add a memory space | 9.21.157 |

### `program_files()` Usage

```python
session = cfg_ctrl.ide_session()
soc = session.SoC("MCU")

# Clear existing and add new program file
soc.program_files().clear()
soc.program_files().add_file(r"C:\firmware.hex", "HEX", 0)
```

### `add_SMP()` Usage

```python
soc = session.SoC("MCU")
soc.add_SMP("TriCore_SMP", "CORE0,CORE1,CORE2")
```

### `add_memory_space()` Usage

```python
soc = session.SoC("MCU")
soc.add_memory_space("PSPR0", "CORE0", "App")
```

---

## COptionAppCfg

Configuration for a single application. Returned by `session.app(name)` or `cfg_ctrl.ide_app(name)`.

### App-Specific Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `symbol_files()` | `COptionFilesCfg` | Symbol files for this application | 9.21.157 |

### `symbol_files()` Usage

```python
app = cfg_ctrl.ide_app("App")

# Clear existing and add ELF symbols
app.symbol_files().clear()
app.symbol_files().add_file(r"C:\firmware.elf", "ELF", 0)
```

---

## COptionFilesCfg

Manages a list of files (program files or symbol files). Returned by `soc.program_files()`, `app.symbol_files()`, `cfg_ctrl.ide_SoC_files(name)`, or `cfg_ctrl.ide_app_files(name)`.

### Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `add_file(path, type, offset)` | `COptionController` | Add a file to the list | 9.21.157 |
| `size()` | `int` | Number of files in the list | 9.21.17 |
| `at(index)` | `COptionController` | Get file at index | 9.21.25 |
| `clear()` | — | Remove all files | 9.21.45 |
| `add()` | `COptionController` | Add an empty element | 9.21.25 |
| `remove(index)` | — | Remove file at index | 9.21.17 |
| `find(option, value)` | `COptionController` | Find file by option | 9.21.17 |

### `add_file()` Parameters

| Parameter | Type | Description |
|---|---|---|
| `path` | str | File path (absolute or relative to workspace) |
| `type` | str | File type: `BIN`, `HEX`, `S37`, `UBROF`, `OMF51`, `SIT`, `IEEE-695`, `ELF`, `TMSCOFF`, `Stabs`, `PE` |
| `offset` | int | Load offset (typically 0) |

### Example: Configure Program Files and Symbol Files

```python
cfg_ctrl = ic.CConfigurationController(cmgr)
session = cfg_ctrl.ide_session()

# Program files for the SoC
soc = session.SoC("MCU")
soc.program_files().clear()
soc.program_files().add_file(r"C:\build\firmware.hex", "HEX", 0)

# Symbol files for the application
app = session.app("App")
app.symbol_files().clear()
app.symbol_files().add_file(r"C:\build\firmware.elf", "ELF", 0)
```

---

## COptionController

Generic option node used throughout the configuration tree. All typed config classes (`COptionSessionCfg`, `COptionSoCCfg`, `COptionAppCfg`, `COptionFilesCfg`) inherit from this.

### Methods

| Method | Returns | Description | Since |
|---|---|---|---|
| `URL()` | `str` | Full option URL for this node | 9.21.17 |
| `get(option)` | `str` | Get string value | 9.21.17 |
| `set(option, value)` | — | Set string value | 9.21.17 |
| `get_bool(option)` | `bool` | Get boolean value | 9.21.17 |
| `set_bool(option, value)` | — | Set boolean value | 9.21.17 |
| `get_int(option)` | `int` | Get integer value | 9.21.17 |
| `set_int(option, value)` | — | Set integer value | 9.21.17 |
| `get_uint(option)` | `int` | Get unsigned integer value | 9.21.17 |
| `set_uint(option, value)` | — | Set unsigned integer value | 9.21.17 |
| `set_multi(params)` | — | Set multiple option values (dict or `StrStrMap`) | 9.21.17 |
| `opt(option)` | `COptionController` | Navigate to a child option node | 9.21.25 |
| `size()` | `int` | Array element count | 9.21.17 |
| `at(index)` | `COptionController` | Element by index | 9.21.25 |
| `find(option, value)` | `COptionController` | Find element by option value | 9.21.17 |
| `index_of(option, value)` | `int` | Find element index (-1 if not found) | 9.21.17 |
| `add()` | `COptionController` | Add element to array | 9.21.25 |
| `remove(index)` | — | Remove element at index | 9.21.17 |
| `clear()` | — | Remove all elements | 9.21.45 |

### `set_multi()` Example

```python
app_opt = cfg_ctrl.ide_app("App")
app_opt.set_multi({"Name": "MyApp", "SymbolFiles.DefaultFile": "0"})
```

---

## CCfg_debug_basic

Initial debug configuration passed to `CWorkspaceController.create()`.

### Setter Methods

| Method | Description |
|---|---|
| `set_Device(device)` | **Required.** Target device (e.g. `"TC387QP"`). |
| `set_DeviceName(name)` | User-friendly SoC name (optional; uses manufacturer name if unset). |
| `set_AppName(name)` | Application name (defaults to `"App"`). |
| `set_PgmPath(path)` | Program file (HEX or ELF for flash programming). |
| `set_SymPath(path)` | Symbol file (ELF for debug symbols). |
| `set_UseSymForPgm(flag)` | Use same file for both symbols and programming. |
| `set_CreateSMP(flag)` | Enable SMP configuration. |
| `set_PresetPC(mode)` | PC preset mode (`EPresetPC_Address` or `EPresetPC_EntryPoint`). |
| `set_Probe(probe)` | Probe name (required when multiple probes possible). |
| `set_ReplaceDir(rules)` | Source file path remapping rules. |

### Getter Methods

| Method | Returns |
|---|---|
| `get_Device()` | Device name |
| `get_DeviceName()` | User SoC name |
| `get_AppName()` | Application name |
| `get_PgmPath()` | Program file path |
| `get_SymPath()` | Symbol file path |
| `get_UseSymForPgm()` | Use-sym-for-pgm flag |
| `get_CreateSMP()` | SMP flag |
| `get_PresetPC()` | PC preset mode |
| `get_Probe()` | Probe name |
| `get_ReplaceDir()` | Path remapping rules |

### Usage

```python
debug_cfg = ic.CCfg_debug_basic()
debug_cfg.set_Device("TC387QP")
debug_cfg.set_UseSymForPgm(False)
debug_cfg.set_CreateSMP(True)
debug_cfg.set_SymPath(r"C:\build\firmware.elf")

workspace_ctrl = ic.CWorkspaceController(cmgr)
workspace_ctrl.create(r"C:\ws\tc387", "HASYST", debug_cfg)
```

---

## Typical Configuration Workflow

```python
import isystem.connect as ic

# 1. Connect
cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
cmgr.connect(conn_cfg.headless(True))

# 2. Create workspace with basic debug config
debug_cfg = ic.CCfg_debug_basic()
debug_cfg.set_Device("TC397XA")
debug_cfg.set_CreateSMP(True)

ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.create(r"C:\workspace\tc397", "HASYST", debug_cfg)

# 3. Fine-tune via CConfigurationController
cfg_ctrl = ic.CConfigurationController(cmgr)

# 3a. Set emulation options
emulation_opt = ic.COptionController(cmgr, "/iOPEN/Emulation")
emulation_opt.set("Debugging.MemorySecurity_Policy", "Reject")

# 3b. Set BlueBox options
bluebox_opt = ic.COptionController(cmgr, "/iOPEN/BB")
bluebox_opt.set("EE.Emulator", "iC5000")
bluebox_opt.set("Communication.Mode", "USB")

# 4. Configure program files
session = cfg_ctrl.ide_session()
soc = session.SoC("MCU")
soc.program_files().clear()
soc.program_files().add_file(r"C:\firmware.hex", "HEX", 0)

# 5. Configure symbol files
app = session.app("App")
app.symbol_files().clear()
app.symbol_files().add_file(r"C:\firmware.elf", "ELF", 0)

# 6. Create session controller and flash
sess_ctrl = ic.CSessionCtrl(cmgr)
sess_ctrl.begin_program()
sess_ctrl.program_verify()

# 7. Cleanup
sess_ctrl.end()
cmgr.disconnect_close(False)
```
