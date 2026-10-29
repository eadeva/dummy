# CANoe COM Interface Reference

**Source:** Vector CANoe Family 18 Help — COM Interface (v18 SP3)

---

## Overview

The COM Interface allows controlling CANoe from external programs. Supported languages include VBScript, JScript, Perl, VBA, Visual Basic, Delphi, C/C++, and **Python** (via `win32com.client`).

### COM ProgIDs

| Product | ProgID |
|---|---|
| CANoe / CANoe DE | `CANoe.Application` |
| CANoe:lite DE | `CANoe.Application` |
| CANoe4SW DE | `CANoe4SW.Application` |
| CANoe4SW:lite DE | `CANoe4SW.Application` |
| CANalyzer | `CANalyzer.Application` |

### Connection Methods (Python)

```python
import win32com.client

# Method 1: DispatchEx — creates new instance (launches CANoe64.exe)
app = win32com.client.DispatchEx("CANoe.Application")

# Method 2: GetActiveObject — connects to already-running instance
app = win32com.client.GetActiveObject("CANoe.Application")

# Method 3: Dispatch — may connect to running or create new
app = win32com.client.Dispatch("CANoe.Application")

# Method 4: GetObject — connect via file moniker (config file)
app = win32com.client.GetObject(r"C:\path\to\config.cfg")
```

---

## Application Object

The `Application` object is the root of the COM object hierarchy. All other objects are accessed from it.

### Properties

| Property | Type | R/W | Description |
|---|---|---|---|
| `Bus([type])` | Bus | R | Returns a Bus object. Type: "CAN", "LIN", "FlexRay", "Ethernet", "AFDX" |
| `CAPL` | CAPL | R | Returns the CAPL object |
| `ChannelMappingName` | STRING | R/W | Application name for hardware channel mapping |
| `Configuration` | Configuration | R | Returns the Configuration object |
| `Environment` | Environment | R | Returns the Environment object (CANoe DE only) |
| `FullName` | STRING | R/W | Complete path to the application |
| `Measurement` | Measurement | R | Returns the Measurement object |
| `Name` | STRING | R | Application name (e.g. "Vector CANoe DE") |
| `Networks([bustype\|network])` | Networks/Network | R | Returns network collection or specific network |
| `Path` | STRING | R | Installation path |
| `Performance` | Performance | R | Performance settings |
| `Simulation` | Simulation | R | Returns the Simulation object |
| `System` | System | R | Returns the System object (system variables) |
| `UI` | UI | R | Returns the UI object (Write window, etc.) |
| `Version` | Version | R | Returns the Version object |
| **`Visible`** | **BOOL** | **R/W** | **Controls main window visibility** |

### Methods

| Method | Parameters | Description |
|---|---|---|
| `New([autoSave, promptUser])` | autoSave: BOOL, promptUser: BOOL | Creates a new configuration |
| `NewConfigurationFromYaml(configurationPath, pathToYamlFolder[, scenarioName])` | path, yamlFolder, scenarioName | Creates config from YAML (v18+) |
| `Open(path[, autoSave[, promptUser]])` | path: STRING, autoSave: BOOL, promptUser: BOOL | Loads a configuration |
| `Quit` | — | Quits the application |

### Events

| Event | Parameters | Description |
|---|---|---|
| `OnOpen(fullname)` | fullname: STRING | Fired when a configuration is opened |
| `OnQuit` | — | Fired when the application quits |

### Visible Property (Headless Mode)

The `Visible` property controls whether the main window is shown or hidden (tray icon only):

```python
app = win32com.client.Dispatch("CANoe.Application")
app.Visible = False  # Hide the window (headless)
app.Visible = True  # Show the window
```

> **Note:** There is also a persistent option under `Configuration > Options > Appearance > Program > Application Window` that controls the initial visibility.

### Open Method — suppressing prompts

The `promptUser` parameter is critical for unattended automation:

```python
# Load config without user prompts (fail silently on errors)
app.Open(r"C:\path\config.cfg", False, False)
```

- `autoSave=False`: Don't auto-save the previous configuration
- `promptUser=False`: Never show user dialogs — fail silently instead

---

## Measurement Object

`Application.Measurement` — controls measurement start/stop.

### Properties

| Property | Type | R/W | Description |
|---|---|---|---|
| `AnimationDelay` | INT | R/W | Animation delay in offline mode |
| `MeasurementIndex` | INT | R/W | Measurement index for next run |
| `Running` | BOOL | R | Whether measurement is currently running |

### Methods

| Method | Description |
|---|---|
| `Animate` | Start measurement in animation mode |
| `Break` | Interrupt playback in offline mode |
| `Reset` | Reset measurement in offline mode |
| `Start` | Start the measurement |
| `Stop` | **Deprecated** — use `StopEx` instead |
| `StopEx` | Stop the measurement (correlates to clicking Stop button) |
| `Step` | Process one measurement event (single step) |

### Events

| Event | Description |
|---|---|
| `OnExit` | Measurement exited |
| `OnInit` | Measurement initialized |
| `OnStart` | Measurement started |
| `OnStop` | Measurement stopped |

### Measurement Control (Python)

```python
# Start measurement
app.Measurement.Start()

# Wait for completion / check state
while app.Measurement.Running:
    time.sleep(1)

# Stop with deferred-stop support
app.Measurement.StopEx()
time.sleep(3)
if app.Measurement.Running:
    app.Measurement.StopEx()  # Full stop
```

---

## Configuration Object

`Application.Configuration` — access to all configuration sub-objects.

### Key Sub-Objects

| Property | Type | Description |
|---|---|---|
| `CommunicationSetup` | CommunicationSetup | Application models, data sources |
| `DatabaseSetup` | DatabaseSetup | Database files |
| `DiagnosticsSetup` | DiagnosticsSetup | Diagnostic descriptions |
| `GeneralSetup` | GeneralSetup | CAN controllers, XCP/CCP, measurement groups |
| `MeasurementSetup` | MeasurementSetup | Bus statistics, logging, offline mode |
| `SimulationSetup` | SimulationSetup | Buses, channels, nodes, replay |
| `TestConfigurations` | TestConfigurations | vTESTstudio test configurations |
| `TestSetup` | TestSetup | Test environments, test modules |
| `Modified` | BOOL (R/W) | Whether the config has been modified |

### Saving Configuration

```python
# Clear the modified/dirty flag without saving
app.Configuration.Modified = False

# Then quit without save prompt
app.Quit()
```

---

## System Object (System Variables)

`Application.System` — access to system variables.

### Hierarchy

```
System
└── Namespaces
    └── Namespace
        └── Variables
            └── Variable
                └── Encodings
```

### Accessing System Variables

```python
sys = app.System
ns = sys.Namespaces("MyNamespace")
var = ns.Variables("MyVariable")

# Read value
value = var.Value

# Write value
var.Value = 42
```

---

## Environment Object

`Application.Environment` — access to environment variables.

### Hierarchy

```
Environment
└── EnvironmentGroup
    └── EnvironmentVariable
        └── EnvironmentInfo
             └── EnvironmentArray
```

---

## COM Object Hierarchy (Top Level)

```
Application
├── Bus          → Channels, Databases, Generators, Signal, etc.
├── CAPL         → CAPLFunction, CompileResult
├── Configuration
│   ├── CommunicationSetup (ApplicationModels, DataSources)
│   ├── DatabaseSetup (Databases)
│   ├── DiagnosticsSetup (DiagDescriptions)
│   ├── GeneralSetup (CANController, CCP/XCP)
│   ├── MeasurementSetup (BusStatistics, Logging, Offline)
│   ├── SimulationSetup (Buses, Nodes, ReplayCollection)
│   ├── TestConfigurations
│   └── TestSetup (TestEnvironments, TestModules)
├── Environment  → EnvironmentGroup → EnvironmentVariable
├── Measurement  → Start/Stop/Running
├── Networks     → Network → Devices, Diagnostic
├── Performance
├── Simulation
├── System       → Namespaces → Namespace → Variables → Variable
├── UI           → Write (Output window)
└── Version
```
