# CANoe TBE — Licensing & Startup

**Source:** Vector CANoe Family 18 Help — Lizenzierung (v18 SP3)

---

## License Types

### Vector License Technology (Standard since v12.0)

- **Software-based licensing** via Vector License Client
- Single-seat licenses (Einzelplatzlizenzen)
- Activation via activation key (delivered by email)
- Supports: Computer, Keyman hardware dongle, Vector network interfaces

### License Carriers

| Carrier | Description |
|---|---|
| **Computer** | Bound to the local machine |
| **Keyman** | Portable USB dongle — can be used on different machines |
| **Network License** | License server (no local carrier needed) |
| **VTP Device** | Vector Tool Platform hardware |

### Network Licenses

- No local license carrier required — licenses reside on a license server
- Configured via: `Options > General > License` or Vector License Client
- Requires network connectivity to the license server
- "Search for network licenses" checkbox must be enabled

---

## Program Start Without Licenses

When no licenses are found at startup, the **License Check Dialog** appears with these options:

| Option | Description |
|---|---|
| **Open License Client** | Opens Vector License Client for activation/management |
| **Use Personal Named User License** | Start with a personal named-user license in a generic user account |
| **Connect to VTP Device** | Connect to a Vector Tool Platform device for hardware-bound licenses |
| **Continue** | Start with limited functionality (View Only mode) |
| **Cancel** | Abort program start |

### View Only Mode

When no valid license is found and the user chooses "Continue":

- CANoe starts with **reduced functionality**
- No measurement start
- No COM automation capabilities
- The version string contains **"View Only"**

---

## TBE Specific Licensing

### License Detection

TBE licenses are detected from:

1. **Local License Client** — activated on the machine
2. **Network License Server** — if configured
3. **VTP Hardware** — Vector Tool Platform devices
4. **LicCfgCANoeTBE.json** — product code mapping

```
C:\ProgramData\Vector\CANoe Family\18 (x64)\LicCfgCANoeTBE.json
{
  "LicenseInformation": [{
    "ProductCode": "55165",
    "ReserveType": "32",
    "Version": "18"
  }]
}
```

### TBE-Only Machines

On machines with only a TBE license:

| Executable | Behavior |
|---|---|
| `CANoeTBE.exe` | Full automation — measurement, COM, test execution |
| `CANoe64.exe` | **View Only** — no measurement, no automation |

### Dual-License Machines

On machines with both Desktop and TBE licenses:

| Executable | License Used |
|---|---|
| `CANoe64.exe` | Desktop license |
| `CANoeTBE.exe` | TBE license |

---

## License Management

### Vector License Client

Access via Start Menu → All Programs → Vector License Client

Actions available:
- **Activate** — Enter activation key
- **Deactivate** — Release license from carrier
- **Reactivate** — Reactivate a deactivated license
- **Update** — Update license to newer product version
- **Repair** — Fix corrupted license data
- **Info** — Display license details in table format

### CANoe License Dialog

In-app license management: Ribbon → Environment → Licensing

- View active licenses
- Search for network licenses
- Configure license server
- Add/remove network types (may trigger dialog at startup)

---

## Legacy Licensing (Pre-v12)

| Version | License Technology |
|---|---|
| ≥ 12.0 | Vector License Technology (standard) |
| ≥ 8.5 SP7 | Vector License Technology (supported) |
| < 12.0 | Hardware dongles (Keyman) or FLEXnet pool licenses |
| ≥ 13.0 | FLEXnet/hardware licenses replaced — migration required |

For migration from old license types, contact Vector Support.

---

## License Options in CANoe

Configuration path: `Options > General > License`

| Option | Description |
|---|---|
| Search for network licenses | Enable/disable network license server search |
| License server address | Address of the network license server |
| View available licenses | Table of all detected local/network licenses |
