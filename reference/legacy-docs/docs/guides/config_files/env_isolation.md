# `env/env_isolation.yml` â€” Environment Variable Isolation

`ENV_ISOLATION` controls which **host environment variables** and **PATH entries** are visible to the child processes that execute build steps. The default (`enabled: true`) is to **strip** everything except a small, explicit allow-list â€” this prevents host-machine drift from affecting CI-reproducible builds.

## Schema

```yaml
enabled: true                          # Default true. Set false to inherit full host env.

# Environment variables that must pass through unmodified
bypass_env_vars:
  - HOME
  - USERPROFILE
  - APPDATA
  - LOCALAPPDATA
  - PROGRAMFILES
  - PROGRAMFILES(X86)
  - SYSTEMROOT
  - PROGRAMDATA
  - PATHEXT
  - TEMP
  - TMP
  - COMSPEC
  - GIT_*                              # Trailing wildcard supported
  - CI
  - GITHUB_*
  - ARTIFACTORY_*

# PATH entries that must remain on the child PATH
bypass_path_elements:
  - "%SYSTEMROOT%\\system32"
  - "%SYSTEMROOT%"
  - "%SYSTEMROOT%\\System32\\Wbem"
  - "%PROGRAMFILES%\\Git\\cmd"
  - "%LOCALAPPDATA%\\Programs\\Python\\Python312"
  - "C:\\tools\\*"                     # Globs supported

# Optional additions per-action
per_action:
  build:
    bypass_env_vars: [MY_PROJECT_DEBUG]
  doc:
    bypass_env_vars: [SPHINX_OPTS]
```

## Field Reference

| Field | Required | Description |
|---|---|---|
| `enabled` | no | `true` (default) enables isolation; `false` passes the full host environment to children. |
| `bypass_env_vars` | no | List of variable names (literal or `*`-wildcard) to keep on the child env. |
| `bypass_path_elements` | no | List of PATH entries to keep. Each entry may contain environment-variable references and `*` globs. |
| `per_action` | no | Action-specific additions deep-merged on top of the global lists when that action runs. |

## How Isolation Works

`ExecutionEngine` builds a clean dict for every child process:

1. Start from an **empty** environment.
2. Copy variables from `os.environ` whose names match `bypass_env_vars` (literal or wildcard).
3. Build a fresh PATH from `bypass_path_elements`, expanding environment-variable references and `*` globs.
4. Add tool-specific environment variables installed via Toolbase, Conan, or Artefact downloads.
5. Add step-defined `env:` overrides last.

Setting `enabled: false` skips steps 1â€“3 and passes `os.environ.copy()` straight through.

## Bypass-Pattern Matching

| Pattern | Matches |
|---|---|
| `HOME` | exact match |
| `GIT_*` | any variable starting with `GIT_` |
| `*PROXY` | any variable ending with `PROXY` |
| `*` (alone, not recommended) | every variable |

PATH entries support `*` globs on path segments. Existence is checked at expansion time; missing paths are silently dropped.

## When to Edit This File

- Add a new corporate proxy variable to `bypass_env_vars` when a step starts failing because it cannot reach Artifactory.
- Add a new tool's install directory to `bypass_path_elements` if you depend on it from `shell` steps.
- Add a per-action exception in `per_action` when only one action needs a specific variable (preferable to broadening the global list).

## Minimal Example

```yaml
enabled: true
bypass_env_vars:
  - HOME
  - USERPROFILE
  - PATHEXT
bypass_path_elements:
  - "%SYSTEMROOT%\\system32"
  - "%SYSTEMROOT%"
```

## See Also

- [main_conf.yml](main_conf.md) â€” `ENV_ISOLATION` field
- [Step Reference](../../core_engine/reference/step_reference.md) â€” `shell` step `env:` override
