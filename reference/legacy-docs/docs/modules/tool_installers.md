# Tool Installers Module

**Package:** `xc_ce_utils.tool_installers`
**Purpose:** Automated installation of development tools across Windows and Linux

---

## Overview

The `tool_installers` package provides platform-aware tool installation. The APIs are primarily **function-based**, with one exception (`ArtifactoryInstaller`).

| Module | API | Platform | Description |
|---|---|---|---|
| `artifactory_installer.py` | `ArtifactoryInstaller` class | Windows + Linux | Batch tool installs from Artifactory, `.env` file generation, PATH management |
| `toolbase_installer.py` | `install_tools()` function | Windows only | XML-based Bosch Toolbase installation (`TBExCmd`/`TBUpdate`), version requirement checks |
| `linux_package_installer.py` | `install_tools_from_json()` function | Linux only | `apt`-based package installation from a JSON config file |

**Platform dispatch:** Windows uses `toolbase_installer` + `artifactory_installer`; Linux uses `linux_package_installer` + `artifactory_installer`.

Called during the core engine setup phase via `EnvironmentSetup.install_tool_requires`.

---

## ArtifactoryInstaller (Class)

The one class-based API. Downloads tool archives from Artifactory, extracts them, and generates a `.env` file with the resulting paths.

```python
from xc_ce_utils.tool_installers.artifactory_installer import ArtifactoryInstaller
from pathlib import Path

installer = ArtifactoryInstaller(
    artifactory_url="https://rb-artifactory.bosch.com/artifactory",
    install_root=Path("C:/tools"),
)

# Install tools defined in config, generate .env file
installer.install_tools(tools_config=tool_definitions, env_file=Path(".env"))
```

**Key features:**
- Batch installation from Artifactory repositories
- Generates `.env` file with `TOOL_NAME_HOME` variables and PATH entries
- Manages install directories and version folders

---

## toolbase_installer (Function-based)

Installs tools from the Bosch Toolbase server on Windows. Reads tool definitions from an XML configuration, checks installed versions against requirements, and invokes `TBExCmd`/`TBUpdate` for missing or outdated tools.

```python
from xc_ce_utils.tool_installers.toolbase_installer import install_tools
from pathlib import Path

# Install tools defined in XML config
install_tools(
    tools_xml=Path("config/tools/toolbase_tools.xml"),
    tb_home=Path(os.environ["TB_HOMEDIR"]),
)
```

**Prerequisites:**
- `TB_HOMEDIR` environment variable set
- `TBExCmd` / `TBUpdate` available (Bosch Toolbase client)

---

## linux_package_installer (Function-based)

Installs system packages via `apt` on Linux. Reads a JSON config listing required packages and versions.

```python
from xc_ce_utils.tool_installers.linux_package_installer import install_tools_from_json
from pathlib import Path

# Install packages defined in JSON config
install_tools_from_json(config_path=Path("config/tools/linux_packages.json"))
```

**JSON config example:**

```json
{
  "packages": [
    {"name": "cmake", "version": "3.25.*"},
    {"name": "ninja-build"},
    {"name": "gcc-multilib"}
  ]
}
```

---

## Integration Points

| Consumer | Usage |
|---|---|
| `EnvironmentSetup.install_tool_requires` | Core engine entry point â€” selects installers based on detected platform |
| `artifactory_utils/` | `ArtifactoryInstaller` uses `ArtifactoryDownloader` internally |
| CI/CD workflows | Tool setup step before build execution |

---

## Configuration

Tool definitions live under `config/tools/` (or equivalent paths in `main_conf.yml`):

- **Toolbase tools (Windows):** XML file with tool names, required versions, and Toolbase IDs
- **Linux packages:** JSON file listing `apt` packages
- **Artifactory tools:** Defined in `main_conf.yml` under `tool_requires` with repository paths and version patterns

## Integration Points

The Tool Installers module integrates with:

- **Builder System**: Automatic tool setup before builds
- **Environment Management**: Environment variable configuration
- **Configuration System**: Tool version requirements from config files
- **Logging System**: Installation progress and error reporting

## Advanced Features

### Batch Installation

Install multiple tools with single command:

```yaml
# batch_install.yml
tools:
  - name: "cmake"
    version: "3.25.0"
  - name: "conan"
    version: "2.9.2"
  - name: "python"
    version: "3.11.4"
  - name: "git"
    version: "2.41.0"
```

```python
installer.install_batch("batch_install.yml")
```

### Custom Installers

Support for custom tool installers:

```python
class CustomToolInstaller(ToolInstaller):
    def install_custom_tool(self, config):
        # Custom installation logic
        pass


# Register custom installer
installer.register_installer("custom_tool", CustomToolInstaller)
```

### Offline Installation

Support for offline environments:

```python
# Download installers for offline use
installer.download_offline_packages(
    ["cmake-3.25.0", "conan-2.9.2", "python-3.11.4"], offline_cache_dir="offline_cache"
)

# Install from offline cache
installer.install_offline("cmake", "3.25.0", offline_cache_dir)
```

## Security Considerations

1. **Checksum Verification**: Always verify downloaded files
2. **Signed Installers**: Use digitally signed installers when available
3. **Secure Downloads**: Use HTTPS for all downloads
4. **Permission Management**: Install with minimal required permissions
5. **Sandboxing**: Isolate installation processes when possible

## Troubleshooting

Common issues and solutions:

- **Download Failures**: Check network connectivity and proxy settings
- **Permission Errors**: Run with appropriate administrative privileges
- **Checksum Mismatches**: Re-download files or check for corruption
- **Version Conflicts**: Use version switching or separate installation paths
- **Environment Issues**: Verify PATH and environment variable configuration

## API Reference

### Toolbase Installer Module

Function-based API for Windows Toolbase tool management.

```{eval-rst}
.. automodule:: xc_ce_utils.tool_installers.toolbase_installer
   :members:
   :undoc-members:
```

### Linux Package Installer Module

Function-based API for Linux package management (apt/yum).

```{eval-rst}
.. automodule:: xc_ce_utils.tool_installers.linux_package_installer
   :members:
   :undoc-members:
```

### Artifactory Installer

Class-based installer for Artifactory-hosted tools.

```{eval-rst}
.. autoclass:: xc_ce_utils.tool_installers.artifactory_installer.ArtifactoryInstaller
   :members:
   :undoc-members:
   :show-inheritance:
```

---

## Used By

### Core Modules

- [Execution Engine](../core_engine/05_building_block_view.md): Automatic tool setup before builds
- **environment setup**: Tool path configuration

### Workflows

- **setup-ci action**: CI environment tool installation
- **variant-dispatcher workflow**: Tool verification before builds

---

## See Also

### Related Modules

- [Execution Engine](../core_engine/05_building_block_view.md): Build orchestration
- [global_modules](./global_modules.md): Utility functions used by installers
- [artifactory_utils](./artifactory_utils.md): Tool download from Artifactory

### Documentation

- [Getting Started](../guides/getting_started.md)
- [Configuration Guide](../guides/config_guide.md)
