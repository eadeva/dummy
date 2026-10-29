# COM I/O Handler

**Package:** `xc_ce_utils.com_io_handler`

Serial COM port communication for embedded target interaction.

---

## Purpose

Provides thread-safe serial communication via RS-232 COM ports using PySerial. Used for console communication with embedded targets during automated testing.

---

## SerialPort Class

Main class for COM port operations.

```python
from xc_ce_utils.com_io_handler.com_io_handler import SerialPort

port = SerialPort(port_number=3, baud_rate=115200, timeout=1)
port.write_to_port("get_status")
response = port.read_from_port()
port.close_port()
```

### Methods

| Method | Description |
|---|---|
| `open()` | Open the serial connection |
| `read_from_port()` | Read a line from the serial port |
| `write_to_port(data)` | Write a string to the serial port |
| `read_from_queue(timeout)` | Read from internal buffered queue |
| `close_port()` | Close the serial connection |
| `scan()` | Scan for available COM ports |

### Features

- **Thread-safe I/O queue** — background reader thread with internal queue
- **XON/XOFF flow control** — software flow control enabled by default
- **Configurable parameters** — baud rate, timeout, port number
- **UTF-8 encoding** with error handling
- Fixed: 8 data bits, no parity, 1 stop bit

---

## See Also

- [Power Supply](powersupply.md) — COM-based power supply control
- [Trace32](trace32.md) — hardware debugger integration
