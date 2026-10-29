# Git Hooks

**Package:** `xc_ce_utils.git_hooks`

Git hook installation and commit validation enforcement.

---

## Key Components

### `hooks_setup.py`

Main hook installation logic.

```python
from xc_ce_utils.git_hooks import configure_git_hooks

configure_git_hooks(jira_project_key="XCCE")
```

### Installed Hooks

| Hook | Purpose |
| --- | --- |
| `pre-commit` | Pre-commit checks |
| `commit-msg` | Validates work item / JIRA references in commit messages |
| `prepare-commit-msg` | Prepares commit message template |

### Bundled Check Entry Points

These checks are invoked through local pre-commit hooks using:

`xc-ce-utils _pre-commit-check <check-name> [args...]`

| Check name | Hook ID(s) / command | Notes |
| --- | --- | --- |
| `task_id_prefix` | `xc-ce-task-id-prefix` | Injects task/work-item ID prefix into commit messages |
| `commit_msg_format` | `xc-ce-commit-msg-format` | Validates commit message format |
| `branch_name` | `xc-ce-branch-name` | Validates branch naming policy |
| `clang_check` | `xc-ce-clang-format` / `xc-ce-clang-tidy` | `format` + `tidy` modes |
| `inventory_check` | `xc-ce-inventory-suite` (`inventory_check all`) | Grouped inventory checks (coverage, metadata, memmaps, tidy-threshold) with per-check config |

### Enforcement

- **Work item references** — commit messages must include JIRA/RTC ticket IDs
- **User info** — auto-detects name/email from Active Directory (Windows) or `getent` (Linux)
- **Commit message formatting** — enforces project-specific patterns

---

## User Info Retrieval

Automatically configures `git user.name` and `git user.email`:

1. **Windows:** Active Directory lookup via PowerShell `DirectorySearcher`
2. **Linux:** `getent passwd` GECOS field
3. **Fallback:** existing `git config --global` values

---

## Installation Trigger

Hooks are installed during:

- `./build.ps1 config refresh-hooks` (hook-only local refresh, no committed config regeneration)
- `./build.ps1 config force-setup` (forced developer-safe re-setup)
- `./build.ps1 config-devops hooks-setup` (maintainer full hooks setup, regenerates committed pre-commit/ruff files)
- `./build.ps1 config-devops full-setup` (maintainer full environment setup)

The pre-commit framework installs hooks into `.git/hooks/`.

---

## See Also

- [VS Code Configurator](vs_code_configurator.md) — triggers hook installation
