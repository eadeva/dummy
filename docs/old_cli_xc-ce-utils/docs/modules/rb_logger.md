# RB Logger

**Package:** `xc_ce_utils.rb_logger`

Singleton logging framework with custom log levels, colored console output, and thread-aware context filtering.

---

## Quick Start

```python
from xc_ce_utils import logger

logger.info("General information")
logger.progress("Installing dependencies...")
logger.success("Build completed")
logger.error("Something went wrong")
```

---

## RBLogger Class

Singleton logger obtained via `from xc_ce_utils import logger` (pre-initialized) or `RBLogger()`.

### Custom Log Levels

| Level | Number | Color |
|---|---|---|
| DEBUG | 10 | Black |
| INFO | 20 | White |
| NOTE | 25 | Bold White |
| PROGRESS | 35 | Cyan |
| SUCCESS | 36 | Green |
| PHASE | 38 | Bold Blue |
| WARNING | 30 | Yellow |
| ERROR | 40 | Red |
| CRITICAL | 50 | Bold Red |

### Filters

- **`OriginalCallerFilter`** — reports the actual calling module, not the logger module
- **`VariantAliasFilter`** — adds variant alias to log records
- **`ThreadAffinityFilter`** — thread-aware context tracking
- **`ContextFilter`** — context stack prefixes like `[SET:flash][STEP:t32_connect]`

### File Logging

```python
logger.file_scope(log_file="build.log")  # context manager for file logging
logger.add_file_logger("errors", "errors.log", level=logging.ERROR)
```

### Phase Headers

```python
from xc_ce_utils.rb_logger import log_phase_header

log_phase_header("BUILD PHASE")
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `LOG_LEVEL` | Console level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_LINE_LENGTH` | Console line width for phase headers |
| `POWERSHELL_LOGGING_ACTIVE` | Suppress phase headers when `true` |

---

## See Also

- [RB Timer](rb_timer.md) — performance timing with logger integration
