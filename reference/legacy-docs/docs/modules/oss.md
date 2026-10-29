# OSS

**Package:** `xc_ce_utils.oss`

Open source compliance scanning via FossID.

---

## Key Components

### CLI Interface

Click-based CLI with the `oss()` command group:

```bash
python -m xc_ce_utils.oss.fossidoss projects list
python -m xc_ce_utils.oss.fossidoss scans create --project-code PROJ --scan-code SCAN_v1
```

### `fossidprojects.py`

FossID project CRUD operations (create, list, delete projects).

### `fossidscans.py`

Scan execution and status management (create scans, check status, retrieve results).

### `fossid_script_api.py`

Low-level FossID REST API wrapper.

### `sw_source_extractor.py`

Extracts `.c`, `.h`, `.cpp`, `.py`, `.sh`, `.ps1` source files for scanning, excluding configured folders, and packages them into a zip archive.

```bash
python -m xc_ce_utils.oss.sw_source_extractor config/oss_config.json /source /output
```

---

## Step Type

| Step Type | Description |
|---|---|
| `oss` | Run OSS compliance scan |

---

## Configuration

### oss_config.json

```json
{
  "SW_FOLDER": "/path/to/source",
  "EXCLUDE_FOLDERS": ["build", "_build", "test", ".git"],
  "ADDITIONAL_FOLDERS": ["third_party/libs"]
}
```

### Environment Variables

| Variable | Description |
|---|---|
| `FOSSID_USER` | FossID username |
| `FOSSID_TOKEN` | FossID API token |
| `FOSSID_URL` | FossID server URL (optional, has default) |

---

## See Also

- [JSON Utils](json_utils.md) — JSON config loading
- [Auth](auth.md) — credential management
