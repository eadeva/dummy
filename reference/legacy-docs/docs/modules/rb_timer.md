# RB Timer

**Package:** `xc_ce_utils.rb_timer`

High-precision performance timing with named checkpoints and threshold monitoring.

---

## RBTimer Class

```python
from xc_ce_utils.rb_timer import RBTimer

timer = RBTimer(timer_id="build", threshold=300, threshold_unit="s")
```

### Methods

| Method | Description |
|---|---|
| `start()` | Start the timer (auto-started on creation) |
| `stop()` | Stop the timer |
| `reset()` | Reset for new measurement |
| `add_checkpoint(id, threshold)` | Add a named timing checkpoint |
| `get_elapsed_time(id, unit, decimals)` | Get elapsed time for checkpoint or total |
| `get_elapsed_time_string()` | Formatted elapsed time (auto-selects units) |
| `get_report_table()` | Table of all checkpoints with threshold status |

### Auto Unit Selection

Automatically picks the most readable unit:

- `< 1 ms` -> microseconds (us)
- `< 1 s` -> milliseconds (ms)
- `>= 1 s` -> seconds (s)

### Threshold Monitoring

```python
timer = RBTimer(timer_id="test", threshold=10, threshold_unit="s")
run_tests()
timer.add_checkpoint("unit_tests", threshold=5)
timer.stop()

if timer.threshold_exceeded:
    logger.warning("Exceeded time limit")
```

### Report Output

```python
report = timer.get_report_table()
# [["Checkpoint", "Elapsed Time", "Threshold"],
#  ["configure", "1.23s", "OK"],
#  ["compile", "45.67s", "EXCEEDED"],
#  ["END", "55.80s", "OK"]]
```

---

## Exceptions

- **`RBTimerException`** — raised for invalid operations (e.g., accessing non-existent checkpoint)

---

## See Also

- [RB Logger](rb_logger.md) — logging integration
- [Execution Engine](../core_engine/05_building_block_view.md) — uses timer for build step timing
