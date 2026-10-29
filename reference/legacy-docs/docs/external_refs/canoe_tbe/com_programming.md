# CANoe COM Programming Guide

**Source:** Vector CANoe Family 18 Help — COM Programming (v18 SP3)

---

## Quick Start

### Creating a COM Connection

```python
import win32com.client

# Start CANoe (or connect to running instance)
app = win32com.client.Dispatch("CANoe.Application")

# Write to the output window
app.UI.Write.Output("Hello from Python...")

# Release the object
app = None
```

If CANoe is not running when `Dispatch` or `DispatchEx` is called, the operating system starts it automatically.

### COM ProgIDs

| Product | ProgID |
|---|---|
| CANoe DE / CANoe:lite DE | `CANoe.Application` |
| CANoe4SW DE / CANoe4SW:lite DE | `CANoe4SW.Application` |
| CANalyzer | `CANalyzer.Application` |

---

## Measurement Control

### Start and Stop

```python
app = win32com.client.Dispatch("CANoe.Application")
measurement = app.Measurement

# Start measurement
measurement.Start()

# Check if running
if measurement.Running:
    print("Measurement is active")

# Stop measurement (use StopEx, not deprecated Stop)
measurement.StopEx()

# Wait and ensure stopped
import time

time.sleep(3)
if measurement.Running:
    measurement.StopEx()  # Full stop after deferred stop
```

### Multiple Measurements with Logging Rotation

```python
app = win32com.client.Dispatch("CANoe.Application")
measurement = app.Measurement
logging = app.Configuration.OnlineSetup.LoggingCollection(1)

for count in range(1, 6):
    logging.FullName = f"C:\\logs\\measurement_{count}.asc"
    measurement.Start()
    # ... wait for completion ...
    measurement.StopEx()
```

---

## Configuration Management

### Loading a Configuration

```python
# Load with no auto-save, no user prompts
app.Open(r"C:\project\test.cfg", False, False)

# Parameters:
#   path        - Full path to .cfg file
#   autoSave    - Save active config before loading (True/False)
#   promptUser  - Show dialogs on errors (True/False)
#                 False = fail silently, no UI popups
```

### Creating a New Configuration

```python
app.New()  # Create empty configuration
```

### Creating from YAML (v18+)

```python
app.NewConfigurationFromYaml(
    r"C:\PathToConfiguration\ConfigurationName.cfg",
    r"C:\FolderToYaml\",
    "OptionalScenarioName"
)
```

### Quitting Without Save Prompt

```python
# Clear the modified flag to avoid save prompt
if not measurement.Running:
    app.Configuration.Modified = False
app.Quit()
```

---

## System Variables

### Read and Write

```python
# Access system variable via namespace
sys = app.System
ns = sys.Namespaces("MyNamespace")
var = ns.Variables("MyVariable")

# Read
value = var.Value

# Write
var.Value = 42
```

### Using xc_ce_utils Wrapper

```python
from xc_ce_utils.canoe.canoe_api import CanoeApi

canoe = CanoeApi()
canoe.open(config_path=r"C:\project\test.cfg")

# Read system variable
value = canoe.get_sysvar_value("MyNamespace", "MyVariable")

# Write system variable
canoe.set_sysvar_value("MyNamespace", "MyVariable", 42)
```

---

## Visibility (Headless Mode)

### Setting Visibility via COM

```python
app = win32com.client.Dispatch("CANoe.Application")
app.Visible = False  # Hide — tray icon only
app.Visible = True  # Show main window

# Check current state
if app.Visible:
    print("CANoe window is visible")
```

### Persistent Option
There is also a configuration-level option at:
`Configuration > Options > Appearance > Program > Application Window`

---

## Event Handling

### VBScript Example (Reference)

```vbscript
' Event handler for measurement start
Sub Measurement_OnStart()
    MeasurementIsRunning = True
End Sub

' Event handler for measurement stop
Sub Measurement_OnStop()
    MeasurementIsRunning = False
End Sub

' Event handler for application quit
Sub Application_OnQuit()
    Set App = Nothing
End Sub
```

### Python COM Event Handling

```python
import win32com.client
import pythoncom


class MeasurementEvents:
    def OnInit(self):
        print("Measurement initialized")

    def OnStart(self):
        print("Measurement started")

    def OnStop(self):
        print("Measurement stopped")

    def OnExit(self):
        print("Measurement exited")


# Connect with event handler
app = win32com.client.DispatchWithEvents("CANoe.Application", MeasurementEvents)
```

---

## Bus Access

### Getting Bus Objects

```python
bus_can = app.Bus("CAN")
bus_lin = app.Bus("LIN")
bus_flexray = app.Bus("FlexRay")
bus_ethernet = app.Bus("Ethernet")
bus_afdx = app.Bus("AFDX")

# Default (no parameter) returns CAN bus
bus_default = app.Bus
```

---

## Network Access

### Getting Networks

```python
# All networks of all bus systems
all_networks = app.Networks

# All CAN networks (bus type enum: 1=CAN, 5=LIN, 6=MOST, 7=FlexRay)
can_networks = app.Networks(1)

# Specific network by name
most_ring = app.Networks("MOST Ring")
```

---

## Channel Mapping

### Setting Application Name

```python
# Set channel mapping name (for multi-instance or hardware manager)
app.ChannelMappingName = "CANoe_Instance1"

# Read the current mapping name
name = app.ChannelMappingName
```

This is the COM equivalent of the `/m` command-line parameter.

---

## Performance Tuning

### Logging Threads

```python
# Set max additional threads for logging branches in Measurement Setup
app.Performance.MaxNumMeasurementSetupThreads = 16
```

---

## Tips & Tricks

### 1. Compile CAPL Before Measurement

Before starting a measurement, verify all CAPL files are compiled. Starting measurement with uncompiled CAPL may cause failures.

### 2. Cache Object References

Don't repeatedly traverse the object hierarchy in a loop:

```python
# BAD — traverses hierarchy every iteration
for i in range(100):
    app.UI.Write.Output(f"Line {i}")

# GOOD — cache the Write object
write = app.UI.Write
for i in range(100):
    write.Output(f"Line {i}")
write = None
```

Each property access via COM is a cross-process call — caching references significantly improves performance.

### 3. Use promptUser=False for Automation

Always set `promptUser=False` in `Open()` and `New()` calls for unattended automation:

```python
app.Open(config_path, False, False)  # No save, no prompts
```

### 4. Clean Shutdown

```python
# Always stop measurement first
if app.Measurement.Running:
    app.Measurement.StopEx()
    time.sleep(3)
    if app.Measurement.Running:
        app.Measurement.StopEx()

# Clear modified flag to avoid save dialog
app.Configuration.Modified = False

# Quit
app.Quit()
```

---

## Distributed COM (DCOM) Configuration

For remote COM access (controlling CANoe on another PC):

1. Open `dcomcnfg` (Component Services)
2. Navigate to: Component Services → Computers → My Computer → DCOM Config
3. Find `CANoe.Application`
4. Configure security, identity, and access permissions

Required files for C++ DCOM development are in: `<install_dir>\Exec64\COMdev\`

---

## Reference

- **Type Library:** `<install_dir>\Exec64\COMdev\` contains TLB files for development
- **VBScript samples:** Available in CANoe installation under sample configurations
- **Application Note:** "CANoe/CANalyzer as a COM Server" (Vector documentation)
