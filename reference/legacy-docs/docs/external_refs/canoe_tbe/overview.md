# CANoe Test Bench Edition (TBE) — Overview

**Source:** Vector CANoe Family 18 Help (v18 SP3, Build 2024-10-08)

---

## Product Editions

CANoe 18 "Family" ships as two edition types:

| Edition | Executable | Description |
|---|---|---|
| **Desktop Edition (DE)** | `CANoe64.exe` | Full GUI for interactive development and testing of automotive networks |
| **Test Bench Edition (TBE)** | `CANoeTBE.exe` | Fully automated execution in server/bench environments — no interactive GUI required |

Both editions share the same installation folder (`Vector CANoe Family 18\Exec64\`) and the same COM ProgID (`CANoe.Application`).

### Desktop Edition Variants

| Product | COM Name | Description |
|---|---|---|
| **CANoe DE** | `CANoe` | Full automotive network support (CAN, LIN, FlexRay, Ethernet, etc.) |
| **CANoe:lite DE** | `CANoe` | No automotive protocols; Basic CAN, VIO/VT system |
| **CANoe4SW DE** | `CANoe4SW` | Software-in-the-loop only, simulated networks |
| **CANoe4SW:lite DE** | `CANoe4SW` | Minimal SIL variant, no automotive protocols |

### Server / Test Bench Editions

| Product | Description |
|---|---|
| **CANoe SE** | Server Edition — automated execution on Windows with real/simulated networks |
| **CANoe TBE** | Test Bench Edition — same as SE but for bench environments |
| **CANoe4SW SE** | SIL server edition for Windows or Linux |

---

## Installation Paths

### Directory Structure

```
C:\Program Files\Vector CANoe Family 18\
├── Exec64\
│   ├── CANoe64.exe           # Desktop Edition executable
│   ├── CANoeTBE.exe          # Test Bench Edition executable
│   └── COMdev\               # COM development files (headers, TLBs)
├── Help49\                   # Documentation
│   └── CANoeDEFamilyHTML5\
└── ...
```

### Settings Directories

| Directory | Description |
|---|---|
| **Program directory** | Executables, components, read-only INI files |
| **Application data** | Per-machine settings (e.g. `CAN.ini`), component configs |
| **User data** | Per-user configs, example configurations, templates |

Settings folder on the machine (from registry):

```
HKLM\SOFTWARE\Vector\CANoe Test Bench Edition\18.0
  Path         = C:\Program Files\Vector CANoe Family 18\
  Version      = 18.0
  SettingsFolder = C:\ProgramData\Vector\CANoe Family\18 (x64)
```

---

## TBE License Configuration

The TBE license is configured in:

```
C:\ProgramData\Vector\CANoe Family\18 (x64)\LicCfgCANoeTBE.json
```

Content:
```json
{
  "LicenseInformation": [
    {
      "ProductCode": "55165",
      "ReserveType": "32",
      "Version": "18"
    }
  ]
}
```

---

## TBE vs Desktop Licensing

On machines with **only a TBE license**:

- `CANoeTBE.exe` starts with full automation capabilities
- `CANoe64.exe` starts in **"View Only"** mode (no measurement, no COM automation)
- `DispatchEx("CANoe.Application")` launches `CANoe64.exe` → View Only → unusable for automation

On machines with **both Desktop and TBE licenses**:

- Both executables work with full functionality
- Standard COM dispatch (`DispatchEx`) launches `CANoe64.exe` (Desktop)
- TBE must be launched explicitly via subprocess

---

## Registry

### COM Registration

```
HKLM\SOFTWARE\Classes\CANoe.Application
HKLM\SOFTWARE\Classes\CANoe.Application.1
HKLM\SOFTWARE\Classes\CANoe.Server
HKLM\SOFTWARE\Classes\CANoe.Server.1
```

> **Note:** Both `CANoe64.exe` and `CANoeTBE.exe` use the same COM ProgID `CANoe.Application`. The registered COM server always points to `CANoe64.exe`.

### TBE-Specific Registry

```
HKLM\SOFTWARE\Vector\CANoe Test Bench Edition\18.0
  Path            REG_SZ    C:\Program Files\Vector CANoe Family 18\
  SettingsFolder  REG_SZ    C:\ProgramData\Vector\CANoe Family\18 (x64)
  Version         REG_SZ    18.0
```

---

## Feature Availability Matrix (Excerpt)

| Feature | CANoe DE | CANoe:lite DE | CANoe4SW DE | CANoe SE | CANoe4SW SE |
|---|:---:|:---:|:---:|:---:|:---:|
| CAN | Yes | Basic | — | Yes | Yes |
| LIN | Yes | — | — | Yes | Yes |
| FlexRay | Yes | — | — | Yes | Yes |
| Ethernet | Yes | — | — | Yes | Yes |
| Diagnostics | Yes | — | — | Yes | Yes |
| Hardware Channels | Yes | Yes | — | Yes | — |
| Offline Mode | Yes | Yes | — | Yes | Yes |
| Simulation Setup | Yes | Yes | Yes | — | — |
| Test Units | Yes | Yes | Yes | Yes | Yes |
| Test Modules | Yes | — | — | Yes | Yes |
| Application Models | Yes | Yes | Yes | Yes | Yes |
| COM Interface | Yes | Yes | Yes | Yes | Yes |

The full feature matrix is available as PDF in the CANoe installation:
- `CANoeDEFamily_FeatureMatrix_DE.pdf`
- `CANoeLiteDEFamily_FeatureMatrix_DE.pdf`
