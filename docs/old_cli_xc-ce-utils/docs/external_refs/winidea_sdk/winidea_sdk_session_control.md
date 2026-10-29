# WinIDEA SDK — Session Control API

**Module:** `isystem.connect`
**SDK Version:** 9.21.408.1

Reference for the `CSessionCtrl` class — the primary interface for managing debug sessions, programming targets, and controlling SoCs.

---

## Overview

`CSessionCtrl` is the main entry point for all session lifecycle operations.
A debug session progresses through distinct phases:

```text
                    ┌─ begin_prepare ──► DETACHED (session ready, no SoC interaction)
                    │
ConnectionMgr ──►   ├─ begin_attach  ──► ATTACHED (connect to running target, no reset)
  (connected)       │
                    ├─ begin_reset   ──► ATTACHED (reset + halt at reset vector, no code download)
                    │
                    └─ begin_program ──► ATTACHED (reset + download code + halt at reset vector)

                                    ... use SoC/Core/Process controls ...

                              end() ──► session ended, all SoCs detached
```

---

## Constructor

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
cmgr.connect(conn_cfg)

sess_ctrl = ic.CSessionCtrl(cmgr)
```

| Parameter | Type | Description |
|---|---|---|
| `cmgr` | `ConnectionMgr` | Active connection manager instance |

---

## Session Lifecycle Methods

### `begin_prepare()`

Initializes a new debug session **without** attaching to any SoC.

Sets up the Blue Box and the debug session, stopping just before any interaction with the target hardware. Allows preparing the environment without affecting the target.

```python
sess_ctrl.begin_prepare()
sess_ctrl.get_status().SoCs()[0].status_string()  # → 'DETACHED'
```

**Raises:** `TException` on connection issues or misconfiguration.

**Since:** 9.21.45

---

### `begin_attach()`

Starts a new debug session and attaches to all SoCs that are configured to attach on session start.

Connects to an **already running** target without resetting or programming it.

```python
sess_ctrl.begin_attach()
sess_ctrl.get_status().SoCs()[0].status_string()  # → 'ATTACHED'
```

**Raises:** `TException` on connection issues or misconfiguration.

**Since:** 9.21.45

---

### `begin_reset()`

Initializes a new debug session and starts emulation (HAR) on all SoCs.

Resets the target SoCs and halts execution at the reset vector, **without performing any code programming**. Symbol files configured for applications are loaded.

```python
sess_ctrl.begin_reset()
sess_ctrl.get_status().SoCs()[0].status_string()  # → 'ATTACHED'
```

**Raises:** `TException` on connection/target/initialization errors.

**Since:** 9.21.45

> **Note:** This replaces the deprecated `CLoaderController.downloadWithoutCode()`.

---

### `begin_program()`

Initializes a new debug session, starts emulation (HAR) on all SoCs, and programs them with the target code.

Downloads the executable code (program files configured for the SoC) to the target SoCs and halts execution at the reset vector.

```python
sess_ctrl.begin_program()
sess_ctrl.get_status().SoCs()[0].status_string()  # → 'ATTACHED'
```

**Raises:** `TException` on connection/target/programming errors.

**Since:** 9.21.45

> **Note:** This replaces the deprecated `CLoaderController.download()`.

---

### `end()`

Ends the debug session and detaches from all SoCs.

```python
sess_ctrl.begin_prepare()
# ... do work ...
sess_ctrl.end()
len(sess_ctrl.get_status().SoCs())  # → 0
```

**Since:** 9.21.45

---

### `program_verify()`

Performs post-download verification to ensure data integrity and correctness.

Checks the validity of the downloaded data (checksum verification, completeness). Call after `begin_program()`.

```python
sess_ctrl.begin_program()
sess_ctrl.program_verify()
```

**Raises:**
- `IOException` on file read / I/O errors.
- `IllegalStateException` if data is corrupted or incomplete.

**Since:** 9.21.152

---

## SoC and Core Access

### `get_SoC(strSoC="")`

Retrieves a control object (`CSoCCtrl`) for the specified SoC.

| Parameter | Type | Description |
|---|---|---|
| `strSoC` | str | SoC name as configured in winIDEA. Empty string for the default (only) SoC. |

```python
sess_ctrl.begin_attach()
soc_ctrl = sess_ctrl.get_SoC("")  # default SoC
soc_ctrl = sess_ctrl.get_SoC("MCU")  # by name
```

**Returns:** `CSoCCtrl`

**Since:** 9.21.45

---

### `get_topology()`

Retrieves the current session topology: SoCs, their devices, cores, and processes.

```python
sess_ctrl.begin_prepare()
topo = sess_ctrl.get_topology()

# SoC info
topo.SoCs()[0].name()  # → 'MCU'
topo.SoCs()[0].device()  # → 'TC397XA'

# Core info
topo.SoCs()[0].cores()[0].name()  # → 'CORE0'

# Process info
topo.processes()[0].URL()  # → 'App/CORE0'
```

**Since:** 9.21.175

---

### `get_status()`

Returns the current state of the debug session — connected SoCs, their states, and status details.

```python
status = sess_ctrl.get_status()
for soc in status.SoCs():
    print(soc.status_string())  # 'DETACHED', 'ATTACHED', 'RESET', etc.
```

**Since:** 9.21.175

---

### `get_core_SMP_bindings(dwSoCIndex=0)`

Retrieves a union of SMP and non-SMP core bindings for the specified SoC.

| Parameter | Type | Description |
|---|---|---|
| `dwSoCIndex` | int | SoC index (default: 0) |

**Returns:** Vector of `SPSessionTopology_CoreBinding`.

**Since:** 9.21.175

---

## Process Control

### `get_process(strProcessURL)`

Retrieves a `CProcessCtrl` instance for the specified process URL.

```python
sess_ctrl.begin_attach()
url = sess_ctrl.get_topology().processes()[0].URL()  # → 'App/CORE0'
proc = sess_ctrl.get_process(url)
```

**Since:** 9.21.45

---

### `process_attach()`

Attaches to the specified process, loads its symbol files, and creates a working image.

**Returns:** `str` — URL of the attached process.

**Since:** 9.21.45

---

### `process_focus(strProcessURL)`

Focuses on the specified process by its URL, making it the current target for debugging operations.

```python
sess_ctrl.process_focus("App/CORE0")
```

**Since:** 9.21.45

---

## Multi-Instance Control

### `instance_attach(strName)` / `instance_attach(dwCoreIndex)`

Attaches to a winIDEA instance by core name or core index. May launch a new winIDEA instance if needed.

```python
# By name
cmgr1 = sess_ctrl.instance_attach("CORE0")
cmgr1.isAttached()  # → True

# By index
cmgr1 = sess_ctrl.instance_attach(0)
```

**Returns:** `ConnectionMgr` for the instance.

**Since:** 9.21.175

---

### `instance_is_attached(dwCoreIndex)`

Checks if the winIDEA instance controlling the specified core index is currently attached.

| Parameter | Type | Description |
|---|---|---|
| `dwCoreIndex` | int | Core index |

**Returns:** `bool`

**Since:** 9.21.175

---

## Typical Workflow: Flash and Verify

```python
import isystem.connect as ic

# 1. Connect
cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
cmgr.connect(conn_cfg.headless(True))

# 2. Configure program files
cfg_ctrl = ic.CConfigurationController(cmgr)
soc_cfg = cfg_ctrl.ide_session().SoC("MCU")
soc_cfg.program_files().clear()
soc_cfg.program_files().add_file(r"C:\firmware.hex", "HEX", 0)

# 3. Program and verify
sess_ctrl = ic.CSessionCtrl(cmgr)
sess_ctrl.begin_program()
sess_ctrl.program_verify()

# 4. Check status
for soc in sess_ctrl.get_status().SoCs():
    assert soc.status_string() == "ATTACHED"

# 5. Reset and end
sess_ctrl.begin_reset()
sess_ctrl.end()

# 6. Disconnect
cmgr.disconnect_close(False)
```
