# CANoe Command-Line Parameters

**Source:** Vector CANoe Family 18 Help — Kommandozeilenparameter (v18 SP3)

---

## CANoe64.exe (Desktop Edition)

Standard command-line syntax: `CANoe64.exe [/option [value]] [config.cfg]`

### Parameters

| Parameter | Products | Description |
|---|---|---|
| `/a` | CANoe DE, CANoe:lite DE, CANoe4SW DE, CANoe4SW:lite DE | Start measurement automatically on launch |
| `/f "path"` | CANoe DE, CANoe:lite DE, CANoe4SW DE, CANoe4SW:lite DE | Load the specified configuration file |
| `/m name` | CANoe DE, CANoe:lite DE | Set the application name (for Vector Hardware Manager channel mapping). Required when running multiple instances on one PC |
| `/n ["net1 net2"]` | CANoe DE, CANoe:lite DE | Add prefix to Ethernet network names (uses `/m` name as prefix). Without specific networks: all Ethernet networks get prefixed |
| `/r` | CANoe DE, CANoe:lite DE, CANoe4SW DE, CANoe4SW:lite DE | Automatically load the last-used configuration on startup |
| `/c address:port` | CANoe DE, CANoe:lite DE | Start in distributed mode with a fixed remote address |
| `/limitto:variant` | CANoe DE, CANoe:lite DE | Limit the program to a specific variant: `pex` (PEX mode) or `run` (Run mode) |

### Examples

```batch
:: Load a specific configuration
CANoe64.exe /f "D:\CANSystemDemo\CANSystemDemo.CFG"

:: Load config and start measurement automatically
CANoe64.exe /f "D:\project\test.cfg" /a

:: Start with application name for multi-instance
CANoe64.exe /m MasterCANoe

:: Start with Ethernet network prefixing
CANoe64.exe /m MasterCANoe /n "Ethernet1 Ethernet2"

:: Start in distributed mode
CANoe64.exe /c 192.168.0.2:2809

:: Limit to PEX variant
CANoe64.exe /limitto:pex
```

---

## CANoeTBE.exe (Test Bench Edition)

The TBE executable supports a different set of command-line parameters.

### Known Parameters

| Parameter | Description |
|---|---|
| `<config.cfg>` | Path to configuration file (positional argument) |
| `--invisible` | Suppress the GUI (headless mode). The application still runs and the COM interface is accessible |

### Examples

```batch
:: Launch TBE with a config file
CANoeTBE.exe "D:\project\test.cfg"

:: Launch TBE in headless mode
CANoeTBE.exe --invisible "D:\project\test.cfg"
```

### Differences from Desktop Edition

| Aspect | CANoe64.exe (DE) | CANoeTBE.exe (TBE) |
|---|---|---|
| CLI style | Windows-style (`/a`, `/f`) | GNU-style (`--invisible`) |
| Auto-measurement | `/a` flag | Not available via CLI — use COM: `Measurement.Start()` |
| Config loading | `/f "path"` | Positional: `CANoeTBE.exe "path"` |
| Headless mode | `Visible = False` via COM only | `--invisible` flag + `Visible = False` via COM |
| Application name | `/m name` | Not available — single-instance only |

---

## Disclaimer Dialog

### Behavior

When CANoe DE is started via COM scripting (e.g. `CreateObject("CANoe.Application")`), the standard disclaimer dialog is **not displayed** — the COM interface bypasses it.

When CANoeTBE is started via subprocess (not COM), it may show a disclaimer dialog on first launch that requires user acknowledgment before the COM server registers itself.

### Controlling the Disclaimer (VBScript/COM)

The `CANutil.ToolInfo` COM object provides control over the disclaimer:

```vbscript
' get the ToolInfo object
Set tool = CreateObject("CANutil.ToolInfo")

' show disclaimer (language, strict, beta, education)
Dim language, strict, beta, education
language  = 1    ' 1 = English, 0 = German
strict    = 1    ' 1 = strict mode (must accept)
beta      = 0    ' 1 = beta disclaimer
education = 0    ' 1 = education disclaimer

If tool.ShowDisclaimer(language, strict, beta, education) <> 1 Then
    WScript.Quit
End If

' release the ToolInfo object
Set tool = Nothing
```

### Python Equivalent

```python
import win32com.client

tool = win32com.client.Dispatch("CANutil.ToolInfo")
# ShowDisclaimer(language, strict, beta, education)
# Returns 1 if accepted, other values if rejected
result = tool.ShowDisclaimer(1, 1, 0, 0)
if result != 1:
    raise RuntimeError("CANoe disclaimer was not accepted")
tool = None
```

### Notes on TBE Disclaimer

- The `--invisible` flag suppresses the GUI window but does **not** suppress the disclaimer dialog
- When launching TBE via subprocess, the disclaimer dialog may block COM registration until accepted
- On headless/CI machines, the disclaimer must be accepted at least once interactively before automation works without it
- After first acceptance, the disclaimer may not reappear on subsequent launches (persisted in user settings)

---

## COM Launch vs Subprocess Launch

### COM Launch (Desktop Edition)
```python
# Standard COM dispatch — launches CANoe64.exe
app = win32com.client.DispatchEx("CANoe.Application")
# Disclaimer is NOT shown (COM bypasses it)
# Works only if a Desktop license is available
```

### Subprocess Launch (TBE)
```python
# Launch TBE executable manually
subprocess.Popen(["CANoeTBE.exe", "--invisible", "config.cfg"])
# Then connect via COM (retry loop):
app = win32com.client.GetActiveObject("CANoe.Application")
# Disclaimer MAY be shown (blocks COM for ~30s on first launch)
```

---

## Distributed Mode

CANoe supports distributed mode for multi-PC test setups:

```batch
CANoe64.exe /c 192.168.0.2:2809
```

This starts CANoe as a participant in a distributed CANoe system, connecting to the coordinator at the specified address and CORBA naming service port.

---

## Multiple Instances

When running multiple CANoe instances on the same PC:

1. Each instance must have a unique application name: `/m InstanceName`
2. Ethernet networks should be prefixed to avoid conflicts: `/n`
3. Hardware channel mapping uses the application name set by `/m`

```batch
:: Instance 1
CANoe64.exe /m "CANoe_Instance1" /f "config1.cfg"

:: Instance 2
CANoe64.exe /m "CANoe_Instance2" /f "config2.cfg"
```
