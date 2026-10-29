# WinIDEA SDK — SoC, Core & Process Control API

**Module:** `isystem.connect`
**SDK Version:** 9.21.408.1

Reference for `CSoCCtrl`, `CCoreCtrl`, and `CProcessCtrl` — runtime control of the target hardware after a debug session has been started.

---

## CSoCCtrl

Controls a single System on Chip within an active debug session. Obtained via `CSessionCtrl.get_SoC()`.

```python
sess_ctrl.begin_reset()
soc = sess_ctrl.get_SoC("")  # default SoC
# or
soc = sess_ctrl.get_SoC("MCU")  # by name
```

### Attach / Detach

| Method | Description | Since |
|---|---|---|
| `attach()` | Attach to the SoC (within an active session) | 9.21.169 |
| `detach()` | Detach from the SoC (within an active session) | 9.21.169 |

```python
sess_ctrl.begin_reset()
soc = sess_ctrl.get_SoC("")
soc.detach()
# ... do other work ...
soc.attach()
```

### SMP Core Focus

For multi-core SoCs (e.g. Infineon AURIX TriCore), these methods control which core is the focused/active core in an SMP binding.

| Method | Description | Since |
|---|---|---|
| `SMP_get_focused_core(dwCoreIndex)` | Get the currently focused core index in an SMP process | 9.21.169 |
| `SMP_set_focused_core(dwCoreIndex)` | Set the focused core in an SMP process | 9.21.169 |

```python
soc = sess_ctrl.get_SoC("")
focused = soc.SMP_get_focused_core(0)  # → 0
soc.SMP_set_focused_core(1)  # switch to CORE1
```

**Raises:** `TException` if `dwCoreIndex` is not in the current process's SMP binding.

### Core Access

| Method | Returns | Description | Since |
|---|---|---|---|
| `get_core(dwCoreIndex)` | `CCoreCtrl` | Get control object for a specific core | 9.21.169 |

```python
core0 = soc.get_core(0)
core1 = soc.get_core(1)
```

### Bus Memory Access

Direct memory access via the SoC bus — useful for reading/writing memory, filling regions, or loading binary files.

| Method | Description | Since |
|---|---|---|
| `bus_read(bus, address, numMAUs)` | Read data from memory via specified bus | 9.21.169 |
| `bus_write(bus, address, data)` | Write data to memory via specified bus | 9.21.169 |
| `bus_fill(bus, address, numMAUs, pattern)` | Fill memory region with repeating pattern | 9.21.169 |
| `bus_write_file(bus, address, path)` | Write file content to memory | 9.21.152 |

#### Parameters

| Parameter | Type | Description |
|---|---|---|
| `bus` | `uint8_t` | Bus index (typically 0) |
| `address` | `int` | Memory address |
| `numMAUs` | `int` | Number of Memory Access Units to read/write/fill |
| `data` / `pattern` | `VectorBYTE` | Byte data (use `ic.VectorBYTE([...])`) |
| `path` | `str` | File path (for `bus_write_file`) |

#### Read / Write Example

```python
soc = sess_ctrl.get_SoC("")

# Write
data = ic.VectorBYTE([0xDE, 0xAD, 0xBE, 0xEF])
soc.bus_write(0, 0x20000000, data)

# Read back
result = soc.bus_read(0, 0x20000000, 4)
print([hex(b) for b in result])  # ['0xde', '0xad', '0xbe', '0xef']
```

#### Fill Example

```python
pattern = ic.VectorBYTE([0xFF])
soc.bus_fill(0, 0x20000000, 1024, pattern)  # fill 1KB with 0xFF
```

#### Write File Example

```python
soc.bus_write_file(0, 0x20000000, "image.bin")
```

### Batch Memory Access

| Method | Description | Since |
|---|---|---|
| `access_batch(batch)` | Perform a batch memory access operation | 9.21.174 |

```python
batch = ic.CAccessBatch()
# ... configure batch items ...
result = soc.access_batch(batch)
```

---

## CCoreCtrl

Controls a single core within an SoC. Obtained via `CSoCCtrl.get_core()`.

```python
core0 = soc.get_core(0)
```

### Memory Access

Per-core memory access using memory areas (not buses).

| Method | Description | Since |
|---|---|---|
| `memory_read(area, address, numMAUs)` | Read data from core-local memory | 9.21.125 |
| `memory_write(area, address, data)` | Write data to core-local memory | 9.21.125 |
| `memory_fill(area, address, numMAUs, pattern)` | Fill core-local memory with pattern | 9.21.125 |

#### Parameters

| Parameter | Type | Description |
|---|---|---|
| `area` | `uint8_t` | Memory area index (typically 0) |
| `address` | `int` | Memory address |
| `numMAUs` | `int` | Number of Memory Access Units |
| `data` / `pattern` | `VectorBYTE` | Byte data |

#### Example

```python
core0 = soc.get_core(0)

# Write to core-local memory
data = ic.VectorBYTE([1, 2, 3, 4])
core0.memory_write(0, 0x200000A0, data)

# Read back
result = core0.memory_read(0, 0x200000A0, 4)
print([b for b in result])  # [1, 2, 3, 4]

# Fill
pattern = ic.VectorBYTE([0x00])
core0.memory_fill(0, 0x200000A0, 256, pattern)
```

### Core Observation

| Method | Description | Since |
|---|---|---|
| `observe(enable)` | Enable or disable core observation within an active debug session | 9.21.125 |

---

## CProcessCtrl

Controls a debug process (an application running on a core). Obtained via `CSessionCtrl.get_process()`.

```python
url = sess_ctrl.get_topology().processes()[0].URL()  # → 'App/CORE0'
proc = sess_ctrl.get_process(url)
```

> Process control provides access to execution and data controllers for the specific process. See `CDebugFacade` for higher-level debug operations.

---

## Topology Objects

The session topology (from `CSessionCtrl.get_topology()`) provides structured information about the hardware setup.

### SoC Topology

```python
topo = sess_ctrl.get_topology()
for soc in topo.SoCs():
    print(f"SoC: {soc.name()}, Device: {soc.device()}")
    for core in soc.cores():
        print(f"  Core: {core.name()}")
```

### Process Topology

```python
for proc in topo.processes():
    print(f"Process URL: {proc.URL()}")
```

### Session Status

```python
status = sess_ctrl.get_status()
for soc in status.SoCs():
    print(f"SoC status: {soc.status_string()}")
    # Possible values: 'DETACHED', 'ATTACHED', 'RESET', etc.
```

---

## Multi-Core Workflow Example (TriCore)

```python
import isystem.connect as ic

# Connect and start session
cmgr = ic.ConnectionMgr()
conn_cfg = ic.CConnectionConfig()
conn_cfg.exe_dir(r"C:\iSYSTEM\winIDEA")
cmgr.connect(conn_cfg.headless(True))

ws_ctrl = ic.CWorkspaceController(cmgr)
ws_ctrl.open(r"C:\workspace\tc397.xjrf")

sess_ctrl = ic.CSessionCtrl(cmgr)
sess_ctrl.begin_reset()

# Get SoC and inspect topology
soc = sess_ctrl.get_SoC("")
topo = sess_ctrl.get_topology()
num_cores = len(topo.SoCs()[0].cores())
print(f"Number of cores: {num_cores}")

# Access individual cores
for i in range(num_cores):
    core = soc.get_core(i)
    print(f"Core {i}: accessible")

# Switch SMP focus
soc.SMP_set_focused_core(0)  # Focus on CORE0
# ... debug CORE0 ...

soc.SMP_set_focused_core(1)  # Switch to CORE1
# ... debug CORE1 ...

# Read memory from CORE0
core0 = soc.get_core(0)
data = core0.memory_read(0, 0x70000000, 16)

# Cleanup
sess_ctrl.end()
cmgr.disconnect_close(False)
```
