# Global Modules

**Package:** `xc_ce_utils.global_modules`

Foundational utility functions and shared components used across the XC-CE Utils engine.

---

## Key Submodules

### `aux_helper.py`

Common utility functions:

| Function | Description |
|---|---|
| `run_command(cmd, ...)` | Subprocess wrapper with logging, realtime output, and return code |
| `load_environment_variables_from_env_file(path)` | Load `.env` file into `os.environ` |
| `is_running_in_ci()` | Detect CI/CD environment (GitHub Actions, Azure DevOps) |
| `export_to_github_env(key, value)` | Write to `$GITHUB_ENV` for Actions |
| `ZipfileLongPaths` | `ZipFile` subclass handling Windows >260 char paths |

### `global_defs.py`

Engine-wide constants (paths, defaults, version info).

### `rb_file_lock.py`

Cross-process file locking:

```python
from xc_ce_utils.global_modules.rb_file_lock import FileLock

with FileLock("/path/to/resource.lock", timeout=30):
    # critical section
    pass
```

### `find_regex_files_in_path.py`

Regex-based recursive file finder.

### `file_empty_line_remover.py`

Utility to clean up excessive empty lines in generated files.

---

## See Also

- [RB Logger](rb_logger.md) — logging (separate top-level module)
- [RB Timer](rb_timer.md) — timing (separate top-level module)
- [JSON Utils](json_utils.md) — JSON handling (separate top-level module)
