# Serial / COM

Ports live in `self.resources["com_ports"]`. Backed by `com_io_handler.SerialPort`.

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping, not flat siblings
of `type`.
```

## `com_init`

- **Source:** [`com_steps.py`](../../../../xc_ce_utils/core_engine/steps/com_steps.py)

```yaml
com_open:
  type: com_init
  params:
    port: COM3
```

## `com_interrupt_boot`

```yaml
boot_interrupt:
  type: com_interrupt_boot
  params:
    port: COM3
    cmd: " "
    expected_str: "boot prompt>"
    timeout: 10
```

## `com_read`

```yaml
com_read_window:
  type: com_read
  params:
    port: COM3
    timeout: 5
```

## `com_scan`

- **Behavior:** Live scan with timeout. `expected_strs` maps checkpoint names to
  `{search_string, threshold?}`.

```yaml
scan_for_ok:
  type: com_scan
  params:
    port: COM3
    expected_strs:
      ok:
        search_string: "READY"
        threshold: 1
    order_relevant: true
    timeout: 30
```

## `com_scan_queue`

- **Behavior:** Same matching, but consumes already-buffered data.

```yaml
scan_buffered:
  type: com_scan_queue
  params:
    port: COM3
    expected_strs:
      boot:
        search_string: "BOOT v"
        threshold: 1
    order_relevant: false
```

## `com_send_cmd`

```yaml
com_send:
  type: com_send_cmd
  params:
    port: COM3
    cmd: "version\r\n"
```

## `com_close`

```yaml
com_quit:
  type: com_close
  params:
    port: COM3
```

## Category index

| Step type | Description |
|---|---|
| `com_init` | Open a serial port |
| `com_interrupt_boot` | Send key, wait for boot prompt |
| `com_read` | Read until idle / timeout |
| `com_scan` | Live scan for expected strings |
| `com_scan_queue` | Scan already-buffered output |
| `com_send_cmd` | Send a command |
| `com_close` | Close the serial port |
