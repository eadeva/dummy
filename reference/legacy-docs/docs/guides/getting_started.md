# Getting Started

```{note}
**Audience:** developers using a project that already contains wrapper scripts that download/install `xc-ce-utils` and run it (e.g. `gw_2wp`). If you're setting up a *new* project repo from scratch, see [Project Onboarding](integration.md) instead.
```

A quick walkthrough from a fresh clone to a working build, plus a reference for the day-to-day CLI, VS Code integration, credential management, and troubleshooting.

---

## Prerequisites

- **Windows** with PowerShell 5.1+ or **Linux** with bash
- **Git Bash** on Windows
- Network access to the configured Artifactory (first run downloads the pinned `xc-ce-utils` executable)

---

## 1. Get the tool

XC-CE Utils is consumed by a project repository. Each project repo ships a thin wrapper (`build.ps1` / `build.sh`) that bootstraps a pinned `xc-ce-utils` executable into a per-project, per-major-version folder under `<user_home>/.<project_name>_xc-ce-utils_<major_version>.x/`.

```powershell
cd <your-project-repo>
.\build.ps1 --help
```

On first run the wrapper:

1. Reads the required version from `config/main_conf.yml` (`XC_CE_UTILS_VERSION`).
2. Downloads the matching pre-built executable from Artifactory (BITS or WebRequest).
3. Extracts it into the project folder above and adds it to `PATH` for the current session.
4. Forwards all arguments to the XC-CE Utils CLI.

Subsequent runs skip the download â€” the installed version is cached and reused. A mutex-based lock prevents parallel installation collisions in CI. Credentials are read from the system keyring (Windows Credential Manager / GNOME Keyring) or prompted interactively.

To pin a different version for local testing:

```powershell
$env:XC_CE_UTILS_VERSION_OVERRIDE = "4.13.0"
.\build.ps1 --help
```

### Entry points

| Entry point | When to use | What it does |
|---|---|---|
| `build.ps1` / `build.sh` | **Most users** | Wrapper â€” auto-installs `xc-ce-utils` and forwards arguments to the CLI |
| `xc-ce-utils.exe` | CI / pre-installed | Standalone PyInstaller executable â€” same CLI, no Python required for the XC-CE CLI itself |
| `python -m xc_ce_utils` | Contributors | Direct Python module entry for working on `xc-ce-utils` itself |

For Conan-enabled projects, Conan commands are executed via `uvx --from conan==2.12.0 conan ...` by default, so `uvx` must be available in `PATH`.

---

## 2. Build a variant

```powershell
# List available variant aliases
.\build.ps1 --help

# Build one (when the configured action is called `build`)
.\build.ps1 -var <alias> build

# Clean rebuild
.\build.ps1 -var <alias> -rb build
```

Outputs:

| Folder | Contents |
|---|---|
| `_bin/<variant>/<action>/` | Build artefacts |
| `_build/<variant>/<action>/` | Build intermediates |
| `_log/<variant>/<action>/` | Step logs (JSON Lines + text) |
| `_reports/<variant>/<action>/` | JUnit reports, SCA/SFA outputs, deploy manifests |

---

## 3. Run a custom action

XC-CE Utils allows custom actions configured over YAML/JSON files. Actions can be grouped and have project-specific names. For example:

```powershell
.\build.ps1 -var <alias> test
.\build.ps1 -var <alias> open helix_qac
.\build.ps1 -var <alias> <action_group> <action_name>
```

### Global CLI options

| Option | Description |
|---|---|
| `--variant`, `-var <alias>` | Variant alias, path, index, or comma/space-separated list |
| `--all-variants`, `-all` | Execute for every variant in the matrix |
| `--adv-help`, `-ah` | Generate and open the interactive Advanced Help documentation page and exit |
| `--clean`, `-c` | Delete build folders and stop |
| `--rebuild`, `-rb` | Clean, then build from scratch |
| `--no-cache`, `-nc` | Disable all caching (ccache, Bazel remote, Conan) |
| `--force-gen`, `-fg` | Force code generation, ignoring generator caches |
| `--verbose`, `-v` | Increase verbosity (`-v` = DEBUG, `-vv` = TRACE) |
| `--ignore-locks`, `-i` | Resolve Conan dependencies freshly (skip lock files) |
| `--version` | Show `xc-ce-utils` version and exit |

### Variant selection patterns

```powershell
.\build.ps1 -var v1 build                      # by alias
.\build.ps1 -var platform/arm_v8/oem_a build   # by full path
.\build.ps1 -var 1,2,3 build                   # by index list
.\build.ps1 -all build                         # every variant in the matrix
```

### From / to phase range

Actions define a step pipeline; you can constrain execution to a subset:

```powershell
.\build.ps1 -var <alias> build --from configure --to configure
.\build.ps1 -var <alias> build --from compile --to test
```

### Action-specific options

Some actions expose additional options that are **generated dynamically** from the action's step pipeline â€” they appear in `--help` only when the action contains the relevant step types:

- `--build-type <Debug|Release|RelWithDebInfo|Developer>`
- `--create-baseline` â€” capture build output as a reference baseline
- `--ccache` / `--no-ccache` â€” toggle compiler cache (CMake/Make actions)

---

## 4. Built-in command groups

### 4.1 `config` â€” configuration and setup utilities

```powershell
.\build.ps1 config --help
```

#### Clean older setup folders and tool versions

When the `xc-ce-utils` major version changes, the project setup folder path changes too (`<user_home>/.<project_name>_xc-ce-utils_<major_version>.x/`).

The same command also scans installed `xc-ce-utils` tool versions (`C:\tools\xc-ce-utils` on Windows, `~/.local/share/xc-ce-utils` on Linux) and removes only versions that are older than the currently running version.

Delete old versions with:

```powershell
.\build.ps1 config clean-older-versions
```

#### Clear the Conan cache

Frees disk space (only relevant if the project uses Conan):

```powershell
.\build.ps1 config conan-cache-cleanup
```

#### Dump the resolved configuration

Writes the fully-resolved configuration to JSON for debugging:

```powershell
.\build.ps1 config dump-config
```

#### Force a clean setup

Recreates the project setup folder from scratch:

```powershell
.\build.ps1 config force-setup
```

`config force-setup` runs only developer-safe setup behavior (no maintainer-only regeneration steps).

#### Refresh Bazel cache setup

Refresh local Bazel disk cache and project-local remote cache files:

```powershell
.\build.ps1 config refresh-bazel-cache
```

#### Validate the configuration

Validates YAML structure and schema without executing any action â€” useful when editing configuration:

```powershell
.\build.ps1 config validate
.\build.ps1 config validate config/main_conf.yml
```

#### Credentials configuration commands

Credentials are stored via the system keyring (Windows Credential Manager / GNOME Keyring) under `<user>@<service_name>` (e.g. `ade7pl@rb-artifactory.com`).

Use the `config creds` subcommand group:

```powershell
# Check, validate and prompt for missing credentials
.\build.ps1 config creds check

# Store/set a new credential
.\build.ps1 config creds new --service <service_name> --username <username>

# Clear or renew active credentials
.\build.ps1 config creds renew
```

#### VS Code configuration commands

Use the `config vs-code` subcommand group:

```powershell
.\build.ps1 config vs-code check-extensions
.\build.ps1 config vs-code devmate-setup
```

### 4.2 `config-devops` â€” maintainer-only setup and regeneration

```powershell
.\build.ps1 config-devops --help
```

Use this group for maintainer-only setup/regeneration operations:

```powershell
.\build.ps1 config-devops full-setup
.\build.ps1 config-devops clang-setup
.\build.ps1 config-devops hooks-setup
.\build.ps1 config-devops vs-code regen-ws-conf
.\build.ps1 config-devops vs-code regen-copilot
.\build.ps1 config-devops vs-code regen-mcp-json
```

```{warning}
`config-devops` commands are maintainer-only because they regenerate committed workspace files or run maintainer setup behavior.
```

The maintainer commands generate:

- `.vscode/tasks.json` â€” build / clean / rebuild tasks for every variant Ã— action combination
- `.vscode/settings.json` â€” editor settings, include paths, C/C++ configuration
- `.github/copilot-instructions.md` â€” GitHub Copilot project context as well as configured prompts, templates and agents
- MCP server entries for AI assistants

Run a task with **Ctrl+Shift+P â†’ Tasks: Run Task** or via the **Terminal â†’ Run Task** menu.

## 5. MCP servers (AI assistants)

XC-CE Utils ships Model Context Protocol servers that expose enterprise systems to AI assistants:

```powershell
python -m xc_ce_utils _mcp --list           # list servers
python -m xc_ce_utils _mcp <server-name>    # launch (typically invoked by VS Code)
```

Available servers: **RTC**, **DNG**, **Docupedia**, **Jira**, **Artifactory**, **DiaBrain**.

---

## 6. Variant management at a glance

Variants represent different build configurations â€” hardware platforms, customers, feature sets â€” and are defined in `config/project/project_conf.yml` under `VARIANT_MATRIX`. Each variant has:

- **Dimension values** â€” e.g. `platform: arm_v8`, `customer: oem_a`
- **Alias** â€” short identifier used on the CLI (e.g. `v1`)
- **Settings** â€” Conan-style settings such as `os`, `compiler`, `build_type` (used by Conan-based projects; ignored otherwise)
- **Requires** â€” dependencies that may resolve to **Conan packages**, **Artifactory artefacts**, or **Toolbase tools** (see the [Configuration Guide](config_guide.md))
- **Options** â€” feature flags and build options
- **Version overrides** â€” per-variant version information

For the full matrix specification and dimension-expansion mechanics see [Variant Matrix](../core_engine/reference/variant_matrix.md).

---

## 8. Troubleshooting

**Configuration errors on startup**
- Ensure `config/main_conf.yml` exists and contains the `ACTIONS` and `PROJECT_CONFIG` keys.
- Run `.\build.ps1 config validate` to check syntax.

**Variant not found**
- Run `.\build.ps1 --help` to list valid aliases.
- Check `config/project/project_conf.yml` â†’ `VARIANT_MATRIX`.

**Conan dependency failures (Conan-based projects only)**
- Verify uvx availability: `uvx --version`
- Verify Conan runtime path: `uvx --from conan==2.12.0 conan --version`
- Try `.\build.ps1 -var <alias> -i build` to ignore lock files and resolve fresh.
- Verify Artifactory credentials with `.\build.ps1 creds check`.

**Build output not where you expected**
- Binaries: `_bin/<variant>/<action>/`
- Intermediates: `_build/<variant>/<action>/`
- Logs: `_log/<variant>/<action>/`

**VS Code configuration not generated**
- Run `.\build.ps1 config vs-code refresh-extensions` for local extension setup.
- Run `.\build.ps1 config-devops vs-code regen-ws-conf` to regenerate shared `.vscode` files.
- Run `.\build.ps1 config-devops vs-code regen-copilot` and `.\build.ps1 config-devops vs-code regen-mcp-json` for Copilot/MCP assets.
- Check write permissions on the `.vscode` directory.

### Getting help

```powershell
.\build.ps1 --help           # general help
.\build.ps1 build --help     # action-specific help (dynamic)
```

---

## 9. Where to go next

| If you want toâ€¦ | Read |
|---|---|
| Understand the config files | [Config Guide](config_guide.md) |
| Add a new build/test/deploy action | [Extending Steps](extending_steps.md) |
| Understand how variants and the matrix work | [Variant Matrix](../core_engine/reference/variant_matrix.md) |
| Look up a step type | [Step Reference](../core_engine/reference/step_reference.md) |
| Set up CI/CD | [CI/CD Workflows](../workflows/index.md) |
| Look up a term | [Glossary](../glossary.md) |
| Onboard a *new* project repo | [Project Onboarding](integration.md) |
