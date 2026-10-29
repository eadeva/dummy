# Power Supplies

Generic factory step set; instances live in `self.resources["power_supplies"]`. Factory `_create_power_supply(ps_type, params)` supports `voltcraft`, `vector_vh`, `vector_vh_canoe`, `nano_car`.

```{note}
**Shape: PARAMS-DICT.** All fields below (including the supply-kind selector) are nested under a
`params:` mapping — there is no naming collision with the outer step `type:` since the supply kind
is one level deeper, at `params.type`.
```

## `power_supply_init`

- **Source:** [`powersupply_steps.py`](../../../../xc_ce_utils/core_engine/steps/powersupply_steps.py)

```yaml
ps_init:
  type: power_supply_init
  params:
    type: vector_vh_canoe
    id: bench_ps
    port: COM7
    dll_path: "C:/Vector/VH/vh.dll"
    off_voltage: 0.0
    on_voltage: 13.5
    max_current_off_state: 0.05
    min_current_normal_operation: 0.2
    settle_time: 0.3
```

## `power_supply_on` / `power_supply_off`

```yaml
ps_on:
  type: power_supply_on
  params:
    id: bench_ps
ps_off:
  type: power_supply_off
  params:
    id: bench_ps
```

## `power_supply_reset`

```yaml
ps_cycle:
  type: power_supply_reset
  params:
    id: bench_ps
    reset_delay: 3.5
```

## `power_supply_set_voltage`

```yaml
ps_voltage:
  type: power_supply_set_voltage
  params:
    id: bench_ps
    voltage: 12.0
```

## Legacy Voltcraft steps

Equivalent to the generic power supply with `params.type: voltcraft`. Kept for backward-compatibility.

| Step | Source |
|---|---|
| `voltcraft_init` | [`voltcraft_steps.py`](../../../../xc_ce_utils/core_engine/steps/voltcraft_steps.py) |
| `voltcraft_power_on` | same |
| `voltcraft_power_off` | same |
| `voltcraft_power_reset` | same |

```yaml
vc_init:
  type: voltcraft_init
  params:
    id: bench_ps
    port: COM5
    off_voltage: 0.0
    on_voltage: 13.5
    max_current_off_state: 0.1
    min_current_normal_operation: 0.5
vc_reset:
  type: voltcraft_power_reset
  params:
    id: bench_ps
```

## Category index

| Step type | Description |
|---|---|
| `power_supply_init` | Initialise a programmable PSU |
| `power_supply_on` | Power the rail on |
| `power_supply_off` | Power the rail off |
| `power_supply_reset` | Off → wait → on |
| `power_supply_set_voltage` | Change rail voltage |
| `voltcraft_init` | Initialise a Voltcraft PSU (legacy) |
| `voltcraft_power_on` | Voltcraft on (legacy) |
| `voltcraft_power_off` | Voltcraft off (legacy) |
| `voltcraft_power_reset` | Voltcraft cycle (legacy) |
