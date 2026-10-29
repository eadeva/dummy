# CANoe TBE — Automation

**Source:** xc_ce_utils implementation + Vector Tool Manager

---

## Installation Selection

Select and activate the required CANoe installation manually with Vector Tool Manager before
running XC-CE actions. XC-CE does not scan installation folders or select a version.

---

## Launch Flow

`CanoeApi.open()` initializes COM and launches the application registered for the
`CANoe.Application` ProgID:

```python
app = win32com.client.DispatchEx("CANoe.Application")
```

It then applies headless visibility, logs the actual version, and loads the requested `.cfg` file.
Failure to create the COM object raises `ConnectionError`.

---

## Process Management

Normal launch does not kill existing processes. `quit()` retains its force-kill fallback when a
COM-controlled instance does not close normally.

---

## Headless Automation

### Configuration (YAML)

```yaml
open_canoe:
  type: canoe_open
  parameters:
    CANOE_ID: CANOE1
    config_path: "${CONFIG_PATH}"
    headless: true               # Suppress GUI
```

### Behavior

| Setting | Behavior |
|---|---|
| `headless: false` | Normal GUI window |
| `headless: true` | Set COM `Visible = False` after launch |

### CI/CD Considerations

- TBE is designed for automated test benches and CI/CD pipelines
- The first launch on a new machine may show a disclaimer dialog that requires interactive acceptance
- After the first acceptance, subsequent launches proceed without the disclaimer
- For fully unattended setup, accept the disclaimer once via RDP or local console session

---

## Error Handling

### Common Issues

| Error | Cause | Solution |
|---|---|---|
| `ConnectionError: Could not launch CANoe` | COM server is unavailable or misregistered | Activate the required CANoe installation in Vector Tool Manager and retry |
| Wrong CANoe version starts | Different installation owns `CANoe.Application` | Change the active installation in Vector Tool Manager |
| Automation is unavailable | Selected installation or license lacks automation support | Verify the selected product and license in Vector tools |
