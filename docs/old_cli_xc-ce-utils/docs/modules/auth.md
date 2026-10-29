# Auth

**Package:** `xc_ce_utils.auth`

Centralised credential management for all authenticated service access.

---

## RBCredentialsManager

Singleton obtained via `get_credentials_manager()`.

```python
from xc_ce_utils.auth import get_credentials_manager

mgr = get_credentials_manager()
user, pwd = mgr.get_credentials("https://rb-artifactory.bosch.com/...")
```

### Credential Resolution Order

1. **Per-process session cache** (hostname-keyed) — never prompts twice per session
2. **Environment variables** — `TECHNICAL_USER_NAME` / `TECHNICAL_USER_PASSWORD` (CI)
3. **System keyring** — OS credential store
4. **Interactive prompt** — terminal `getpass`, or `tkinter` dialog in frozen exe

### Keyring API

| Method | Description |
|---|---|
| `store_credential(service, id, password)` | Store in system keyring |
| `get_credential(service, id)` | Retrieve from system keyring |
| `delete_credential(service, id)` | Remove from system keyring |

---

## CredentialDiscovery

Scans project configuration files to determine which credentials are needed before prompting.

---

## CLI Commands

```bash
creds check   # verify stored credentials
creds new     # store new credentials
creds renew   # update existing credentials
```

---

## CI Auto-Detection

When running in CI (`is_running_in_ci()`), the manager:
- Uses `TECHNICAL_USER_*` environment variables exclusively
- Raises hard errors instead of prompting interactively

---

## Frozen-Exe Support

In PyInstaller bundles, `getpass` is replaced by a `tkinter` GUI dialog for credential input.

---

## See Also

- [Global Modules](global_modules.md) — `is_running_in_ci()` utility
