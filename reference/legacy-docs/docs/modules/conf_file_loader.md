# Configuration File Loader

**Package:** `xc_ce_utils.conf_file_loader`

Loads YAML/JSON configuration files with variable substitution, environment expansion, and recursive file inclusion.

---

## ConfigLoader Class

Main class for loading and processing configuration files.

- **Variable substitution:** `{{ var }}` syntax replaced from a provided variables dict
- **Environment expansion:** `$ENV{VAR}` replaced from OS environment variables
- **Nested operators:** `$OP{...}` expressions resolve from innermost to outermost
- **Version conversion:** `$VERSION_HEX{version}` converts resolved version text to fixed-width hexadecimal
- **Checked paths:** `$PATH{...}` and `$PATH_ABSOLUTE{...}` normalize and validate paths
- **Recursive file inclusion:** any value ending `.yml`, `.yaml`, or `.json` auto-loads that file in-place
- **Multi-format:** supports YAML and JSON transparently
- **UTF-8 BOM:** automatically strips BOM markers

```python
from xc_ce_utils.conf_file_loader import ConfigLoader

loader = ConfigLoader(variables={"PROJECT": "my_project", "VERSION": "1.0"})
config = loader.load_file("config/main_conf.yml")
```

---

## Standalone Functions

- `load_yaml(file_path)` — load a YAML file directly (no substitution)
- `dump_yaml(data, file_path)` — write data to a YAML file

---

## Standalone CLI

```bash
python -m xc_ce_utils.conf_file_loader -i input.yml -o output.yml -v KEY=VALUE
```

---

## Variable Syntax

| Syntax | Source | Example |
|---|---|---|
| `{{ VAR }}` | Variables dict | `{{ PROJECT }}` → `my_project` |
| `$ENV{VAR}` | OS environment | `$ENV{USER}` → `john` |
| `$VAR{VAR}` | Runtime global variables | `$VAR{artifact}` → `report.json` |
| `$VERSION_HEX{version}` | Resolved version text | `$VERSION_HEX{1.2.3}` → `0x0001000000020003` |
| `$PATH{path}` | Existing host-normalized path | Relative input remains relative |
| `$PATH_ABSOLUTE{path}` | Existing absolute host-normalized path | Relative input resolves from the working directory |
| `$LITERAL{value}` | Plain string | Prevents YAML/JSON auto-inclusion |
| `path/to/file.yml` | File inclusion | Value auto-loaded recursively |

---

## Usage Examples

### Fixed-Width Version Hexadecimal

```yaml
version: $VERSION_HEX{1.2.3}
dependency_version: $VERSION_HEX{$ENV{ARTIFACT_FBL_VERSION}}
component_version: $VERSION_HEX{$ENV{MAJOR}.$ENV{MINOR}.$ENV{BUGFIX}}
```

`VERSION_HEX` converts its resolved body; it does not interpret the body as an
environment-variable name. The numeric `major.minor.bugfix` release prefix is encoded as an unsigned
16-bit major, unsigned 32-bit minor, and unsigned 16-bit bugfix component.
Prerelease and build suffixes are ignored. Values that exceed their component
width or do not start with a numeric release triplet cause configuration
loading to fail.

### Nested Operators and Checked Paths

```yaml
artifact_dir: $PATH_ABSOLUTE{$ENV{ARTIFACT_DIR}}
artifact_file: $PATH_ABSOLUTE{$ENV{ARTIFACT_DIR}/firmware.bin}
relative_tool: $PATH{tools/generator.exe}
config_text: $LITERAL{$ENV{CONFIG_DIR}/settings.json}
```

Operators use balanced braces and resolve from innermost to outermost. Both
path operators normalize `/` and `\` for the host OS and fail if the complete
path inside the braces does not exist. `PATH` preserves relative input;
`PATH_ABSOLUTE` resolves relative input against the current working directory.

General config discovery remains permissive for missing `ENV` and `VAR` values
because earlier action steps may produce them. Leaf-step and lazy phase-file
loading are strict: missing values, unknown operators, malformed braces,
invalid versions, and missing paths fail when the owning step is constructed.

### Variable Substitution

```yaml
# config.yml
project: {{ PROJECT }}
build_dir: _build/{{ PROJECT }}
```

```python
loader = ConfigLoader(variables={"PROJECT": "xc_ce_utils"})
config = loader.load_file("config.yml")
# build_dir → "_build/xc_ce_utils"
```

### Recursive File Inclusion

```yaml
# main_conf.yml
base: config/base.yml        # auto-loaded
project: config/project.json  # auto-loaded
```

### Dumping Configuration

```python
loader.dump_file({"version": "2.0"}, "output.yml")
```

---

## See Also

- [JSON Utils](json_utils.md) — lower-level JSON loading
- [Global Modules](global_modules.md) — environment variable utilities
