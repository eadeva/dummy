# Power Supply

**Package:** `xc_ce_utils.powersupply`

Controls Voltcraft programmable power supplies via COM port for automated ECU power cycling.

---

## PowerSupply Class

```python
from xc_ce_utils.powersupply import PowerSupply

psu = PowerSupply(
    id="ecu_main",
    port="COM3",
    off_voltage=0.5,
    on_voltage=11.5,
    max_current_off_state=0.1,
    min_current_normal_operation=1.5,
)
```

### Methods

| Method | Description |
|---|---|
| `turn_on()` | Power on, wait for normal operation |
| `turn_off()` | Power off, wait for shutdown |
| `read_power_supply_values()` | Read current voltage and current |
| `is_normal_operation()` | Check if ECU is booted (current >= threshold) |

### Implementation

Internally invokes `python -m voltcraft` (third-party package) as a subprocess to communicate with the Voltcraft hardware via serial.

```bash
python -m voltcraft COM3 on
python -m voltcraft COM3 off
python -m voltcraft COM3 read  # returns (voltage, current)
```

---

## Step Types

| Step Type | Description |
|---|---|
| `voltcraft_init` | Initialise power supply connection |
| `voltcraft_power_on` | Turn on power supply |
| `voltcraft_power_off` | Turn off power supply |
| `voltcraft_power_reset` | Power cycle (off -> delay -> on) |

---

## Usage in Test Sequences

```python
# Power cycle before flashing
psu.turn_off()
time.sleep(2)  # capacitor discharge
psu.turn_on()  # waits for min_current_normal_operation
```

---

## See Also

- [Trace32](trace32.md) — ECU flashing after power cycle
- [COM I/O Handler](com_io_handler.md) — serial communication
