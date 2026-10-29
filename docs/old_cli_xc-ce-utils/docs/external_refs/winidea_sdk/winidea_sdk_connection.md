# WinIDEA SDK — Connection & Workspace API

**Module:** `isystem.connect`
**SDK Version:** 9.21.408.1

Reference for `ConnectionMgr`, `CConnectionConfig`, and `CWorkspaceController` — the foundation classes for connecting to winIDEA and managing workspaces.

---

## ConnectionMgr

Manages the connection to a winIDEA instance. Can discover, create, and close winIDEA sessions.

### Constructor

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
```

### Connection Methods

| Method | Description |
|---|---|
| `connect(config)` | Connect to winIDEA using a `CConnectionConfig` |
| `disconnect()` | Disconnect from winIDEA |
| `disconnect_close(save)` | Disconnect and close winIDEA. `save=False` discards changes. |
| `disconnect_keep()` | Disconnect but leave winIDEA running |

### State Query Methods

| Method | Returns | Description |
|---|---|---|
| `isConnected()` | `bool` | True if connection was established (until disconnect) |
| `isAttached()` | `bool` | True if connection is alive (active heartbeat) |
| `isWarning()` | `bool` | True if last operation issued a warning |
| `getLastErrorMsg()` | `str` | Warning/error message from last operation |
| `getWinIDEAVersion()` | `str` | winIDEA version string (winIDEA 9.9+) |

### Discovery Methods

| Method | Description |
|---|---|
| `enumerateWinIDEAInstances(host)` | Lists running winIDEA instances at the specified host |
| `get_installed_winIDEAs()` | Returns information on all installed winIDEAs |
| `isCoreLaunched(core)` | True if winIDEA for the given core is already launched |
| `isStartedFromWinIDEA()` | True if the calling application was launched from winIDEA |

### Multi-Core Methods

| Method | Description |
|---|---|
| `launchCore1(...)` | Opens another winIDEA instance connected to a secondary core |

### Logging

| Method | Description |
|---|---|
| `initLogger(...)` | Initialize the SDK logger |
| `getLogger()` | Get the logger instance |
| `getId()` | Get the ID set by `setLogger()` |

### Utility

| Method | Description |
|---|---|
| `terminate()` | Terminate pending communication (call from another thread) |

### Deprecated Methods

| Method | Replacement |
|---|---|
| `connectMRU()` | `connect(SPConnectionConfig)` |
| `connectMRUEx()` | `connect(SPConnectionConfig)` |
| `findExistingInstance()` | `connect(SPConnectionConfig)` |
| `findOrStartInstance()` | `connect(SPConnectionConfig)` |
| `startNewInstance()` | `connect(SPConnectionConfig)` |
| `getIConnectDllVersion()` | Use constructor with version flag |
| `launchCore()` | Does not work since 9.21.199 |

---

## CConnectionConfig

Configuration object passed to `ConnectionMgr.connect()`. Controls how winIDEA is found, launched, and connected to.

### Core Settings

| Method | Description |
|---|---|
| `exe_dir(path)` | Directory where `winIDEA.exe` is located. Used to start a new instance. |
| `headless(flag)` | Run winIDEA in headless mode (no GUI). Returns `self` for chaining. |
| `workspace(path)` | Set winIDEA workspace path to open on launch. |
| `host(host, port)` | Set PC host and port for remote winIDEA connection. |

### Instance Management

| Method | Description |
|---|---|
| `start(policy)` | How to potentially start a new instance. |
| `start_always()` | Always start a new winIDEA instance. |
| `start_existing()` | Connect to an existing instance only. Never start new. |
| `start_if_required()` | Start a new instance only if no existing match is found. |
| `instanceId(id)` | Set winIDEA instance ID for matching. |

### Startup Options

| Method | Description |
|---|---|
| `waitTime(ms)` | How long SDK waits for newly launched winIDEA (ms). |
| `discoveryTime(ms)` | Timeout for pre-launch instance discovery (ms). |
| `visibility(mode)` | winIDEA window visibility after startup. |
| `cmd_line(params)` | Command line parameters for winIDEA. |
| `native()` | Configure to start native winIDEA (Linux: not via Wine). |

### Discovery

| Method | Description |
|---|---|
| `useIPCDiscovery(flag)` | Use local IPC for instance discovery. |
| `udpDiscoveryPort(port)` | Set UDP discovery port. |

### Getters

| Method | Returns |
|---|---|
| `getWorkspace()` | Workspace path |
| `getWaitTime()` | Startup wait time |
| `getDiscoveryTime()` | Discovery timeout (ms) |
| `getInstanceId()` | Instance ID |
| `getProcessId()` | Process ID (after `findExistingInstance`) |
| `getTCPPort()` | TCP port (after `findExistingInstance`) |
| `getVisibility()` | Window visibility setting |
| `getUdpDiscoveryPort()` | UDP discovery port |
| `getCmdLineParams()` | Command line parameters |
| `get_exe_type()` | Executable type (gui or command) |
| `get_start()` | Start policy |
| `is_native()` | True if native winIDEA will be used |
| `isUseIPCDiscovery()` | True if IPC discovery is enabled |

### Typical Usage

```python
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
conn_cfg.workspace(r"C:\workspaces\tc397.xjrf")

# Headless server mode
cmgr = ic.ConnectionMgr()
cmgr.connect(conn_cfg.headless(True))

# Or with explicit startup control
conn_cfg.start_if_required()
conn_cfg.waitTime(30000)  # 30s
cmgr.connect(conn_cfg)
```

---

## CWorkspaceController

Manages winIDEA workspaces: create, open, save, and close.

### Constructor

```python
ws_ctrl = ic.CWorkspaceController(cmgr)
```

### Methods

| Method | Description | Since |
|---|---|---|
| `create(path, iOPEN, cfg)` | Create a new workspace from `CCfg_debug_basic` | 9.12.288 |
| `open(path)` | Open an existing workspace file | 9.12.288 |
| `save()` | Save the current workspace | 9.12.288 |
| `saveAs(path)` | Save workspace to a new file | 9.12.288 |
| `close()` | Close workspace (prompts to save if changes exist) | 9.12.288 |
| `closeDiscard()` | Close workspace and discard all changes | 9.12.288 |
| `path()` | Returns path of currently opened workspace | 9.12.288 |
| `get_cfg_debug()` | Returns current `CCfg_debug_basic` | 9.21.237 |
| `set_cfg_debug(cfg)` | Sets debug configuration | 9.12.288 |
| `invoke(funcUrl, params)` | Invoke internal winIDEA functions (iSYSTEM support) | 9.12.288 |
| `invoke_T(funcUrl, params)` | Same as `invoke()` but throws on failure | 9.12.288 |
| `invokej(funcUrl, jsonParams)` | Same as `invoke()` with JSON parameters | 9.12.288 |

### `create()` Parameters

| Parameter | Type | Description |
|---|---|---|
| `path` | str | Workspace file path (use `.xjrf` extension) |
| `iOPEN` | str | iOPEN server: `"HASYST"` (BlueBox), `"iopen_GDB"` (GDB), `"HMCD"` (MCD), `"iopen_GDI"` (GDI), `"HRenesas"` (Renesas) |
| `cfg` | `CCfg_debug_basic` | Initial debug configuration |

### Create Workspace Example

```python
debug_cfg = ic.CCfg_debug_basic()
debug_cfg.set_Device("TC397XA")
debug_cfg.set_CreateSMP(True)
debug_cfg.set_UseSymForPgm(False)

ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.create(r"C:\workspace\tc397", "HASYST", debug_cfg)
```

### Open Existing Workspace

```python
ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.open(r"C:\workspace\tc397.xjrf")
```

### Deprecated

| Method | Replacement |
|---|---|
| `newWS()` | `create()` |

---

## Typical Connection Patterns

### Pattern 1: Fresh Workspace (From Scratch)

```python
import isystem.connect as ic

# Connect
cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
cmgr.connect(conn_cfg.headless(True))

# Create workspace
debug_cfg = ic.CCfg_debug_basic()
debug_cfg.set_Device("TC387QP")
debug_cfg.set_CreateSMP(True)

ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.create(r"C:\ws\tc387", "HASYST", debug_cfg)

# Configure emulation and BlueBox
emulation_opt = ic.COptionController(cmgr, "/iOPEN/Emulation")
emulation_opt.set("Debugging.MemorySecurity_Policy", "Reject")

bluebox_opt = ic.COptionController(cmgr, "/iOPEN/BB")
bluebox_opt.set("EE.Emulator", "iC5000")
bluebox_opt.set("Communication.Mode", "USB")
```

### Pattern 2: Existing Workspace

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
cmgr.connect(conn_cfg.headless(True))

ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.open(r"C:\workspace\project.xjrf")
# All device/emulator/BlueBox settings come from the workspace file
```

### Pattern 3: Remote winIDEA

```python
import isystem.connect as ic

cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.host("192.168.1.100", 5000)
conn_cfg.start_existing()  # must already be running
cmgr.connect(conn_cfg)
```
