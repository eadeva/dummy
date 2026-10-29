# Timers & Threads

Backed by `RBTimer`; instances live in `self.resources["timers"]`. Threads owned by non-blocking steps live in `self.resources["threads"]`.

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping, not flat siblings
of `type`.
```

## `timer_start`

- **Source:** [`timer_steps.py`](../../../../xc_ce_utils/core_engine/steps/timer_steps.py)
- **Notes:** `threshold` (seconds, optional) is set here — not on `timer_stop`.

```yaml
start_phase_timer:
  type: timer_start
  params:
    id: phase_a
    threshold: 60
```

## `timer_stop`

```yaml
stop_phase_timer:
  type: timer_stop
  params:
    id: phase_a
```

## `timer_checkpoint`

```yaml
ckpt_compile_done:
  type: timer_checkpoint
  params:
    id: phase_a
    checkpoint_id: compile_done
```

## `wait_idle`

- **Behavior:** `time.sleep(wait_time)`. Takes **only** `wait_time` — no `id` field.

```yaml
settle:
  type: wait_idle
  params:
    wait_time: 2
```

## `thread_stop`

- **Source:** [`thread_steps.py`](../../../../xc_ce_utils/core_engine/steps/thread_steps.py)
- **Behavior:** Signals the named non-blocking thread to stop and joins with a 5 s timeout.

```yaml
stop_logger:
  type: thread_stop
  params:
    id: com_logger
```

## Category index

| Step type | Description |
|---|---|
| `timer_start` | Start a named timer |
| `timer_stop` | Stop the timer (optional `threshold`) |
| `timer_checkpoint` | Record a labelled checkpoint within a timer |
| `wait_idle` | Sleep for `wait_time` seconds |
| `thread_stop` | Cooperatively stop a non-blocking thread |
